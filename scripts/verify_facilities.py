#!/usr/bin/env python3
"""
verify_facilities.py — cross-check facilities.json coordinates against EPA ECHO

Queries the EPA ECHO (Enforcement and Compliance History Online) facility
search API for each named facility in facilities.json, finds the closest
EPA-registered match, and flags any facility whose curated coordinates
differ from the EPA record by more than a configurable threshold.

Usage:
    python3 scripts/verify_facilities.py                  # check all, 500 m threshold
    python3 scripts/verify_facilities.py --threshold 250  # tighter: flag > 250 m off
    python3 scripts/verify_facilities.py --output verification_report.md
    python3 scripts/verify_facilities.py --facility "LANXESS"  # single facility

Output (stdout):
    OK       — within threshold; EPA coordinates match ours
    MISMATCH — outside threshold; shows both coordinate pairs and distance
    NOT FOUND — no EPA ECHO record found under that name or state

Requires: requests  (pip install requests)

Notes:
    - Warehouses and traffic corridors are skipped (not EPA-registered point sources).
    - ECHO API rate-limits aggressively; a 0.5 s delay is inserted between calls.
    - Some facilities (e.g. older Superfund sites) may not appear in ECHO even if
      they exist. NOT FOUND does not necessarily mean coordinates are wrong.
    - API endpoint: https://echo.epa.gov/rest/services/EWFacility/
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip install requests first")

ECHO_URL = (
    "https://echo.epa.gov/rest/services/EWFacility/"
    "echo_rest_fac.get_facs_via_query"
)
FACILITIES = Path(__file__).parent.parent / "facilities.json"

# Categories that have no useful EPA ECHO registration
SKIP_CATEGORIES = {"warehouse", "corridor"}


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in metres between two lat/lon points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# EPA ECHO queries
# ---------------------------------------------------------------------------

def echo_search(name: str, state: str, retries: int = 2) -> list[dict]:
    """
    Search EPA ECHO for facilities matching *name* in *state*.

    Returns a list of facility dicts (FacName, FacLat, FacLong, …).
    Returns [] on network error after retrying.
    """
    for attempt in range(retries + 1):
        try:
            resp = requests.get(ECHO_URL, params={
                "output":      "JSON",
                "p_fn":        name,
                "p_st":        state,
                "responseset": "10",
            }, timeout=15)
            resp.raise_for_status()
            return resp.json().get("Results", {}).get("Facilities", [])
        except requests.RequestException as exc:
            if attempt == retries:
                print(f"    ECHO error ({name}): {exc}")
                return []
            time.sleep(1.0)
    return []


def best_echo_match(
    hits: list[dict],
    our_lat: float,
    our_lon: float,
) -> tuple[dict | None, float]:
    """
    Find the ECHO facility record closest to our curated coordinates.

    Returns (best_hit, distance_in_metres). distance is inf if no valid hit.
    """
    best, best_dist = None, float("inf")
    for hit in hits:
        try:
            lat = float(hit.get("FacLat") or 0)
            lon = float(hit.get("FacLong") or 0)
        except (TypeError, ValueError):
            continue
        if lat == 0.0 and lon == 0.0:
            continue
        dist = haversine(our_lat, our_lon, lat, lon)
        if dist < best_dist:
            best, best_dist = hit, dist
    return best, best_dist


# ---------------------------------------------------------------------------
# Verification logic
# ---------------------------------------------------------------------------

def verify_one(
    name: str,
    state: str,
    our_lat: float,
    our_lon: float,
    threshold: int,
) -> dict:
    """Verify a single facility. Returns a result dict."""
    hits = echo_search(name, state)
    time.sleep(0.5)

    # Fallback: try first two words of the name (e.g. "Kuehne Chemical" → "Kuehne")
    if not hits:
        short = " ".join(name.split()[:2])
        if short != name:
            hits = echo_search(short, state)
            time.sleep(0.5)

    if not hits:
        return {
            "name": name, "state": state,
            "our_lat": our_lat, "our_lon": our_lon,
            "status": "NOT_FOUND",
            "distance_m": None, "echo_lat": None, "echo_lon": None,
            "echo_name": None,
        }

    match, dist = best_echo_match(hits, our_lat, our_lon)
    if match is None:
        return {
            "name": name, "state": state,
            "our_lat": our_lat, "our_lon": our_lon,
            "status": "NOT_FOUND",
            "distance_m": None, "echo_lat": None, "echo_lon": None,
            "echo_name": None,
        }

    return {
        "name": name, "state": state,
        "our_lat": our_lat, "our_lon": our_lon,
        "status": "OK" if dist <= threshold else "MISMATCH",
        "distance_m": round(dist),
        "echo_lat":  float(match.get("FacLat", 0)),
        "echo_lon":  float(match.get("FacLong", 0)),
        "echo_name": match.get("FacName"),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_summary(results: list[dict], threshold: int) -> None:
    ok      = [r for r in results if r["status"] == "OK"]
    bad     = [r for r in results if r["status"] == "MISMATCH"]
    missing = [r for r in results if r["status"] == "NOT_FOUND"]

    print(f"\n=== Verification summary (threshold: {threshold} m) ===")
    print(f"  OK (within {threshold} m):  {len(ok)}")
    print(f"  MISMATCH:                   {len(bad)}")
    print(f"  NOT FOUND in EPA ECHO:      {len(missing)}")

    if bad:
        print(f"\n--- Mismatches ---")
        for r in sorted(bad, key=lambda x: x["distance_m"], reverse=True):
            print(f"  {r['name']} ({r['state']}): {r['distance_m']} m off")
            print(f"    Ours:  lon={r['our_lon']}, lat={r['our_lat']}")
            print(f"    ECHO:  lon={r['echo_lon']}, lat={r['echo_lat']}")
            print(f"    Match: {r['echo_name']}")

    if missing:
        print(f"\n--- Not found in EPA ECHO ---")
        for r in missing:
            print(f"  {r['name']} ({r['state']})")


def write_markdown_report(path: str, results: list[dict], threshold: int) -> None:
    ok      = [r for r in results if r["status"] == "OK"]
    bad     = [r for r in results if r["status"] == "MISMATCH"]
    missing = [r for r in results if r["status"] == "NOT_FOUND"]

    lines = [
        "# Facility Coordinate Verification Report",
        "",
        f"**Source:** EPA ECHO Facility Search API  ",
        f"**Mismatch threshold:** {threshold} m  ",
        "",
        "| Status | Count |",
        "|--------|-------|",
        f"| ✅ OK (≤ {threshold} m) | {len(ok)} |",
        f"| ⚠️ Mismatch | {len(bad)} |",
        f"| ❌ Not found in EPA ECHO | {len(missing)} |",
        "",
    ]

    if bad:
        lines += ["## Mismatches", ""]
        for r in sorted(bad, key=lambda x: x["distance_m"], reverse=True):
            lines += [
                f"### {r['name']} ({r['state']})",
                f"- **Distance off:** {r['distance_m']} m",
                f"- **Our coordinates:** `[{r['our_lon']}, {r['our_lat']}]`",
                f"- **EPA ECHO match:** `[{r['echo_lon']}, {r['echo_lat']}]`"
                f" — *{r['echo_name']}*",
                "",
            ]

    if missing:
        lines += [
            "## Not Found in EPA ECHO",
            "",
            "_These facilities returned no ECHO results. Coordinates may still be"
            " correct — verify manually via [EPA FRS](https://www.epa.gov/frs) or"
            " [EPA TRI Explorer](https://www.epa.gov/toxics-release-inventory-tri-program)._",
            "",
        ]
        for r in missing:
            lines += [f"- {r['name']} ({r['state']})"]
        lines += [""]

    if ok:
        lines += ["## Verified Facilities", ""]
        for r in sorted(ok, key=lambda x: x["distance_m"]):
            lines += [
                f"- **{r['name']}** ({r['state']}) — {r['distance_m']} m from ECHO record"
            ]

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify facilities.json coordinates against EPA ECHO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--threshold", type=int, default=500,
        help="Distance in metres beyond which a facility is flagged (default: 500)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Write a Markdown verification report to this file",
    )
    parser.add_argument(
        "--facility", type=str, default=None,
        help="Check only the facility whose name contains this string (case-insensitive)",
    )
    args = parser.parse_args()

    with open(FACILITIES) as f:
        data = json.load(f)

    features = data.get("features", [])
    print(f"Loaded {len(features)} features from {FACILITIES.name}")

    results: list[dict] = []

    for feat in features:
        props = feat.get("properties", {})
        category = props.get("category", "facility")
        name = props.get("name", "")
        state = props.get("state", "DE")

        if category in SKIP_CATEGORIES:
            continue

        if args.facility and args.facility.lower() not in name.lower():
            continue

        try:
            coords = feat.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                continue
            our_lon, our_lat = float(coords[0]), float(coords[1])
        except (ValueError, TypeError):
            print(f"  Skipping '{name}': malformed coordinates {coords!r}")
            continue

        print(f"Checking: {name} ({state})...")
        result = verify_one(name, state, our_lat, our_lon, args.threshold)
        results.append(result)

        icon = {"OK": "✅", "MISMATCH": "⚠️", "NOT_FOUND": "❌"}.get(result["status"], "?")
        if result["distance_m"] is not None:
            print(f"  {icon} {result['status']} — {result['distance_m']} m")
        else:
            print(f"  {icon} {result['status']}")

    if not results:
        print("No facilities matched the filter.")
        return

    print_summary(results, args.threshold)

    if args.output:
        write_markdown_report(args.output, results, args.threshold)
        print(f"\nReport written to {args.output}")


if __name__ == "__main__":
    main()
