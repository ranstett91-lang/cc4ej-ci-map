#!/usr/bin/env python3
"""
fetch_echo_history.py — build echo_facility_history.json from EPA ECHO.

Pulls per-facility enforcement/compliance history from EPA's ECHO
(Enforcement and Compliance History Online) REST services for Delaware
and the cross-state Claymont airshed counties already covered by the
TRI fetcher. Produces annual counts of inspections, formal enforcement
actions, informal actions, and significant noncompliance quarters per
ECHO facility — a very different signal from TRI's self-reported
pounds released.

Output shape:
    {
      "_meta": {
        "source": "EPA ECHO (Enforcement & Compliance History Online)",
        "endpoint": "https://echodata.epa.gov/echo/...",
        "states": ["DE","PA","NJ","MD"],
        "counties_focus": {...},
        "years": [2001, ..., 2025],
        "retrieved_utc": "...",
        "note": "Annual counts by ECHO FRS_ID. Inspections, enforcement actions, SNC quarters."
      },
      "facilities": {
        "110000432123": {
          "name": "...",
          "lat":  39.80, "lon": -75.43,
          "programs": ["AIR","NPDES","RCRA"],
          "years": {
            "2018": {"insp": 2, "formal": 1, "informal": 3, "snc_q": 2, "penalty_usd": 45000},
            ...
          }
        }, ...
      }
    }

The map joins these to facilities.json by lat/lon + name overlap at
render time, same pattern as facilities_tri.json.

Usage:
    python3 scripts/fetch_echo_history.py             # full pull
    python3 scripts/fetch_echo_history.py --dry-run
    python3 scripts/fetch_echo_history.py --states DE

Requires: requests  (pip3 install requests)

Network note: ECHO's data services endpoints are public (no key) but
rate-limited; this script sleeps 0.3s between calls.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests first")

OUT = Path(__file__).parent.parent / "echo_facility_history.json"

# ECHO's unified facility search endpoint (CSV output = smallest payload
# and stable column names across releases).
ECHO_BASE = "https://echodata.epa.gov/echo"

# Keep the same focus counties as the TRI fetcher so the two files join
# cleanly. See scripts/fetch_tri_history.py for the airshed rationale.
FOCUS_COUNTIES = {
    "DE": None,
    "PA": {"DELAWARE"},
    "NJ": {"SALEM", "GLOUCESTER"},
    "MD": {"CECIL", "KENT", "QUEEN ANNE'S", "CAROLINE", "TALBOT",
           "DORCHESTER", "WICOMICO", "WORCESTER", "SOMERSET"},
}

FIRST_YEAR = 2001  # ECHO's detailed history goes back ~25 years for most programs


def fetch_facilities(state: str) -> list[dict]:
    """Query ECHO's facility endpoint for all active/inactive sites in *state*.

    We request a handful of columns only — FAC_NAME, lat/lon, program
    flags, aggregated counts — to keep CSV rows small. ECHO returns ~1
    row per FRS_ID regardless of how many programs the facility is in.
    """
    url = f"{ECHO_BASE}/echo_rest_services.get_download"
    params = {
        "output": "CSV",
        "p_st": state,
        "qcolumns": (
            "1,4,5,6,12,13,14,17,22,23,27,28,"   # name, addr, FIPS, lat/lon
            "85,86,87,88,"                       # 5-yr insp/enf/qtrs-in-snc/qtrs-in-noncomp
            "100,101,102,103"                    # cumulative penalties/total_enf etc.
        ),
    }
    print(f"  ECHO facilities for {state}: GET {url}")
    try:
        r = requests.get(url, params=params, timeout=180)
    except requests.RequestException as e:
        print(f"    request error: {e}; skipping")
        return []
    if r.status_code != 200:
        print(f"    HTTP {r.status_code}: {r.text[:200]!r}")
        return []
    lines = r.text.splitlines()
    if not lines:
        return []
    import csv
    reader = csv.DictReader(lines)
    return list(reader)


def fetch_history(frs_id: str) -> list[dict]:
    """Per-facility annual history via EFFACTS (enforcement & compliance)."""
    url = f"{ECHO_BASE}/eff_rest_services.get_compliance_summary"
    try:
        r = requests.get(url, params={"p_id": frs_id, "output": "JSON"}, timeout=60)
    except requests.RequestException as e:
        return []
    if r.status_code != 200:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    # Normalize: compliance_summary returns {"Results": {"ComplianceSummary": [...]}}
    if isinstance(data, dict):
        summary = data.get("Results", {}).get("ComplianceSummary", [])
        if isinstance(summary, list):
            return summary
    return []


def _in_focus(row: dict, state: str) -> bool:
    counties = FOCUS_COUNTIES.get(state)
    if counties is None:
        return True
    county = (row.get("FAC_COUNTY") or row.get("County") or "").upper()
    return county in counties


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def build(states: list[str]) -> dict:
    by_fac: dict[str, dict] = {}
    year_set: set[int] = set()

    for st in states:
        print(f"\n=== {st} ===")
        facs = fetch_facilities(st)
        kept = 0
        for f in facs:
            if not _in_focus(f, st):
                continue
            frs = (f.get("REGISTRY_ID") or f.get("FRS_ID") or "").strip()
            if not frs:
                continue
            programs = []
            for k, label in [("AIR_FLAG", "AIR"), ("NPDES_FLAG", "NPDES"),
                             ("RCRA_FLAG", "RCRA"), ("SDWIS_FLAG", "SDWIS"),
                             ("TRI_FLAG", "TRI"), ("GHG_FLAG", "GHG")]:
                if (f.get(k) or "").strip().upper() in ("Y", "1", "TRUE"):
                    programs.append(label)
            by_fac[frs] = {
                "name": (f.get("FAC_NAME") or "").strip(),
                "lat":  round(_to_float(f.get("FAC_LAT")) or 0, 5) or None,
                "lon":  round(_to_float(f.get("FAC_LONG")) or 0, 5) or None,
                "street": ", ".join(x for x in [
                    (f.get("FAC_STREET") or "").strip(),
                    (f.get("FAC_CITY") or "").strip(),
                    st,
                    (f.get("FAC_ZIP") or "").strip(),
                ] if x),
                "programs": programs,
                "years": {},
            }
            kept += 1
        print(f"  {kept:,} focus facilities kept for {st}")

        # Now per-facility time series. This is the slow loop; we rate-
        # limit to 0.3s/req and keep going if any one facility 404s.
        for i, frs in enumerate([k for k in by_fac if by_fac[k]]):
            if i % 50 == 0:
                print(f"    history {i}/{len(by_fac)}")
            rows = fetch_history(frs)
            for row in rows:
                yr = _to_int(row.get("Year") or row.get("year"))
                if yr < FIRST_YEAR:
                    continue
                by_fac[frs]["years"][str(yr)] = {
                    "insp":    _to_int(row.get("Inspections")),
                    "formal":  _to_int(row.get("FormalEnforcementActions")),
                    "informal": _to_int(row.get("InformalEnforcementActions")),
                    "snc_q":   _to_int(row.get("QuartersInSNC")
                                       or row.get("QtrsInSNC")),
                    "penalty_usd": _to_float(row.get("TotalPenalties")) or 0,
                }
                year_set.add(yr)
            time.sleep(0.3)

    # Drop facilities with no history rows — they bloat the file.
    by_fac = {k: v for k, v in by_fac.items() if v["years"]}

    return {
        "_meta": {
            "source":   "EPA ECHO (Enforcement & Compliance History Online)",
            "endpoint": ECHO_BASE,
            "states":   states,
            "counties_focus": {k: (sorted(v) if v else "ALL")
                               for k, v in FOCUS_COUNTIES.items() if k in states},
            "years":    sorted(year_set),
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note":     ("Annual inspection/enforcement counts + total penalty "
                         "dollars per ECHO FRS facility ID. SNC = Significant "
                         "Noncompliance quarters (max 4/year). Join to "
                         "facilities.json by lat/lon + name at render."),
        },
        "facilities": by_fac,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--states", default="DE,PA,NJ,MD",
                    help="Comma-separated (default: DE,PA,NJ,MD)")
    args = ap.parse_args()

    states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    print(f"Fetching ECHO for {states}")

    payload = build(states)
    n_fac = len(payload["facilities"])
    n_rows = sum(len(v["years"]) for v in payload["facilities"].values())
    print(f"\n{n_fac} facilities, {n_rows} facility-year rows")

    if args.dry_run:
        print("DRY RUN — not writing.")
        return

    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"Wrote {OUT.name}  ({OUT.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
