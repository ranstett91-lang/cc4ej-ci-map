#!/usr/bin/env python3
"""
fetch_tri_history.py — build facilities_tri.json from EPA TRI (1987+).

Fetches Toxic Release Inventory (TRI) annual reporting rows from the EPA
Envirofacts REST API for Delaware, Delaware County PA, and Gloucester /
Salem counties NJ (the Claymont airshed), then pivots to per-facility
year-over-year pounds-released series.

The map joins these records to facilities.json by proximity
(<0.5 mi haversine) + name-token overlap at render time, so the
fetcher does not need to know about our facility IDs — it just needs
name + lat/lon per TRIFID.

Output shape:
    {
      "_meta": {
        "source": "EPA Envirofacts TRI",
        "endpoint": "https://data.epa.gov/efservice/...",
        "states": ["DE","PA","NJ"],
        "years": [1987, 1988, ..., 2023],
        "retrieved_utc": "2026-04-19T...",
        "note": "Annual pounds released. Sum over all chemicals per TRIFID per year."
      },
      "facilities": {
        "TRIFID_1": {
          "name": "...",
          "lat":  39.8034,
          "lon": -75.4381,
          "street": "..., Claymont DE",
          "years": {
            "1987": { "total_lbs": 142300.0, "top_chems": [["Benzene",45000],["Toluene",32000]] },
            ...
          }
        }, ...
      }
    }

Usage:
    python3 scripts/fetch_tri_history.py              # full pull
    python3 scripts/fetch_tri_history.py --dry-run    # preview only
    python3 scripts/fetch_tri_history.py --states DE  # DE only

Requires: requests  (pip install requests)

Network note: EPA Envirofacts gates the XML/JSON REST service behind
host-level allowlisting in some sandboxes (403 Host not in allowlist).
If you see that, run this script from a machine with open outbound access
to data.epa.gov, then commit the resulting facilities_tri.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip install requests first")

OUT = Path(__file__).parent.parent / "facilities_tri.json"

BASE = "https://data.epa.gov/efservice"
FAC_TABLE = "tri_facility"
REPORT_TABLE = "tri_reporting_form"
RELEASE_TABLE = "tri_release_qty"

# Claymont airshed counties — keeps payload small while covering the
# cross-state emission sources the map cares about. Maryland's Eastern
# Shore is included so Kent and Sussex DE see their actual upwind
# sources (poultry processors, wood treaters, etc.) and the map isn't
# biased toward New Castle / the Claymont corridor.
FOCUS_COUNTIES = {
    "DE": None,                    # entire state (all 3 counties)
    "PA": {"DELAWARE"},            # Marcus Hook / Trainer / Eddystone
    "NJ": {"SALEM", "GLOUCESTER"}, # Paulsboro / Gibbstown / Penns Grove
    "MD": {"CECIL", "KENT", "QUEEN ANNE'S", "CAROLINE", "TALBOT",
           "DORCHESTER", "WICOMICO", "WORCESTER", "SOMERSET"},
}


def fetch_facilities(state: str) -> list[dict]:
    """Pull facility rows for a state. One row per TRIFID."""
    url = f"{BASE}/{FAC_TABLE}/state_abbr/{state}/JSON"
    print(f"  {url}")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return r.json()


def fetch_releases(state: str) -> list[dict]:
    """Pull per-chemical annual release rows for a state.

    Envirofacts joins tri_reporting_form (which carries year + TRIFID)
    to tri_release_qty (which carries pounds). Pagination syntax is
    /rows/START:END/JSON — the rows clause must come BEFORE the format
    specifier, otherwise the service returns an HTML error page.

    Envirofacts occasionally returns HTTP 500 with a server-side trace
    ('NoneType' object has no attribute 'get') when paging very deep.
    We retry a couple times with backoff, and if it still fails we treat
    the partial page set as complete rather than aborting the whole run.
    """
    import time
    base_url = f"{BASE}/{REPORT_TABLE}/state_abbr/{state}/{RELEASE_TABLE}"
    print(f"  {base_url}/rows/.../JSON")
    rows: list[dict] = []
    offset = 0
    step = 5000  # smaller chunks — the joined view is wide; 10k pages timed out
    while True:
        url = f"{base_url}/rows/{offset}:{offset + step - 1}/JSON"
        page = None
        last_err = None
        for attempt, wait in enumerate([0, 5, 15]):
            if wait:
                time.sleep(wait)
            try:
                r = requests.get(url, timeout=300)
            except requests.RequestException as e:
                last_err = f"request error: {e}"
                continue
            if r.status_code == 500:
                last_err = f"HTTP 500 — {r.text[:200]!r}"
                continue
            if r.status_code != 200:
                print(f"    HTTP {r.status_code} at offset={offset} — first 200 bytes:")
                print(f"    {r.text[:200]!r}")
                r.raise_for_status()
            ctype = r.headers.get("Content-Type", "")
            if "json" not in ctype.lower():
                last_err = f"non-JSON (Content-Type: {ctype})"
                continue
            try:
                page = r.json()
                break
            except Exception as e:
                last_err = f"JSON parse failed: {e}"
                continue

        if page is None:
            print(f"    giving up at offset={offset} after retries ({last_err}); "
                  f"treating {len(rows):,} rows as complete for {state}.")
            break
        if not page:
            break
        rows.extend(page)
        print(f"    fetched {len(rows):,} rows")
        if len(page) < step:
            break
        offset += step
    return rows


def _in_focus(row: dict, state: str) -> bool:
    counties = FOCUS_COUNTIES.get(state)
    if counties is None:
        return True
    county = (row.get("county_name") or row.get("county") or "").upper()
    return county in counties


def _to_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def build(states: list[str]) -> dict:
    by_trifid: dict[str, dict] = {}
    year_set: set[int] = set()

    for st in states:
        print(f"\nFacilities for {st}:")
        facs = fetch_facilities(st)
        for f in facs:
            if not _in_focus(f, st):
                continue
            tid = f.get("tri_facility_id") or f.get("trifid") or f.get("TRI_FACILITY_ID")
            if not tid:
                continue
            lat = _to_float(f.get("pref_latitude")  or f.get("latitude"))
            lon = _to_float(f.get("pref_longitude") or f.get("longitude"))
            name = (f.get("facility_name") or "").strip()
            street = (f.get("street_address") or "").strip()
            city = (f.get("city_name") or f.get("city") or "").strip()
            zip_ = (f.get("zip_code") or f.get("zip") or "").strip()
            by_trifid[tid] = {
                "name": name,
                "lat": round(lat, 5) if lat else None,
                "lon": round(lon, 5) if lon else None,
                "street": ", ".join(x for x in [street, city, st, zip_] if x),
                "years": {},
            }
        print(f"  {len(by_trifid):,} focus-area facilities so far")

        print(f"\nRelease rows for {st}:")
        rows = fetch_releases(st)
        per_fac_year_chem: dict[tuple[str, int, str], float] = defaultdict(float)
        for r in rows:
            tid = r.get("tri_facility_id") or r.get("trifid") or r.get("TRI_FACILITY_ID")
            if tid not in by_trifid:
                continue
            try:
                yr = int(r.get("reporting_year") or r.get("year") or 0)
            except (TypeError, ValueError):
                continue
            if yr < 1987:
                continue
            chem = (r.get("chem_name") or r.get("chemical_name") or "Unknown").strip()
            # TRI stores release quantities in several columns; sum air + water
            # + land + underground + off-site. Envirofacts returns them as
            # separate rows OR pre-aggregated in `total_release` depending on
            # the view — handle both.
            pounds = _to_float(r.get("total_release")
                               or r.get("total_releases")
                               or r.get("release_qty")
                               or 0)
            if pounds <= 0:
                continue
            per_fac_year_chem[(tid, yr, chem)] += pounds
            year_set.add(yr)

        for (tid, yr, chem), lbs in per_fac_year_chem.items():
            yrs = by_trifid[tid]["years"]
            ys = yrs.setdefault(str(yr), {"total_lbs": 0.0, "_chems": {}})
            ys["total_lbs"] += lbs
            ys["_chems"][chem] = ys["_chems"].get(chem, 0.0) + lbs

    # Finalize: trim chemical dict to top-5 per year, round pounds.
    for tid, rec in by_trifid.items():
        for yr, ys in rec["years"].items():
            chems = ys.pop("_chems", {})
            top = sorted(chems.items(), key=lambda kv: -kv[1])[:5]
            ys["total_lbs"] = round(ys["total_lbs"], 1)
            ys["top_chems"] = [[c, round(p, 1)] for c, p in top]

    # Drop facilities with no reporting rows at all — they just bloat the
    # file. Keep those with any year of reported releases.
    by_trifid = {k: v for k, v in by_trifid.items() if v["years"]}

    return {
        "_meta": {
            "source":        "EPA Envirofacts TRI (Toxics Release Inventory)",
            "endpoint":      f"{BASE}/{FAC_TABLE} + {REPORT_TABLE}/{RELEASE_TABLE}",
            "states":        states,
            "years":         sorted(year_set),
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note":          "Annual TRI-reported pounds released (air + water + land "
                             "+ underground + off-site), summed across all chemicals "
                             "per TRIFID per year. top_chems are the 5 largest "
                             "contributors that year.",
        },
        "facilities": by_trifid,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--states", default="DE,PA,NJ,MD",
                    help="Comma-separated (default: DE,PA,NJ,MD)")
    args = ap.parse_args()

    states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    print(f"Fetching TRI for states: {states}")

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
