#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026. See LICENSE.md.
"""fetch_tri_chemical_history.py — per-chemical-per-year TRI release data
for the Delaware River airshed (DE + adjacent PA/NJ counties).

Output
------
    tri_chemical_history.json — {
        _meta: { source, endpoint, states, year_range, retrieved_utc, ... },
        chemicals: {
            "<tri_chem_id>": {
                cas: "...", name: "...",
                hap_flag: 0/1,            # CAA §112 (caac_ind)
                carc_flag: 0/1,           # EPA classified carcinogen (carc_ind)
                metal_flag: 0/1
            }, ...
        },
        facilities: {
            "<TRIFID>": {
                "<year>": {
                    "<tri_chem_id>": {
                        air_lbs: <stack + fugitive air release in lbs>,
                        total_lbs: <on + off site release in lbs>
                    }, ...
                }, ...
            }, ...
        }
    }

Why this layout
---------------
The existing tri_history.json sums every chemical into one annual number per
facility, which is correct for "how much pollution overall" but not for
multi-pollutant analysis (cancer drivers vs respiratory drivers). This file
preserves the per-chemical granularity AND tags each chemical with EPA's
own carcinogen + HAP classifications so downstream code can build category-
specific weights without re-curating chemical lists.

Year window
-----------
Default 2015-2024 — matches the wind-rose climatology window in
fetch_noaa_wind_rose.py and the recent_5yr_avg lookback in
build_facility_weights.py. Larger windows are supported via --years.
The earliest TRI year is 1987, but per-chemical detail is heavy; we
default to a recent-only window unless explicitly widened.

Usage
-----
    python3 scripts/fetch_tri_chemical_history.py
    python3 scripts/fetch_tri_chemical_history.py --years 2010-2024
    python3 scripts/fetch_tri_chemical_history.py --states DE,PA,NJ
    python3 scripts/fetch_tri_chemical_history.py --dry-run
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


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tri_chemical_history.json"

BASE_ROOT = "https://data.epa.gov/efservice/tri_form_r_ez"
DEFAULT_STATES = ["DE", "PA", "NJ"]
DEFAULT_YEARS = list(range(2015, 2025))


def parse_years(spec: str) -> list[int]:
    spec = (spec or "").strip()
    if not spec:
        return list(DEFAULT_YEARS)
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return sorted(out)


def fetch_year_state(year: int, state: str, page_size: int = 1000,
                     verbose: bool = False) -> list[dict]:
    """Fetch every TRI Form R row for (year, state). Replicates the
    pagination logic from fetch_tri_history.py (same endpoint, same quirks).
    """
    rows: list[dict] = []
    start = 0
    base = f"{BASE_ROOT}/state_abbr/{state.upper()}/reporting_year/{year}"
    while True:
        end = start + page_size - 1
        url = f"{base}/rows/{start}:{end}/JSON"
        for attempt in range(3):
            try:
                r = requests.get(url, timeout=180,
                                 headers={"Accept": "application/json",
                                          "User-Agent": "cc4ej-ci-map/1.0"})
                break
            except requests.RequestException as e:
                if attempt == 2:
                    print(f"    {year}/{state}: request failed: {e}", file=sys.stderr)
                    return rows
                time.sleep(2 ** attempt)
        if r.status_code == 404:
            return rows
        if not r.ok:
            print(f"    {year}/{state}: HTTP {r.status_code}", file=sys.stderr)
            return rows
        try:
            page = r.json()
        except ValueError:
            print(f"    {year}/{state}: non-JSON response", file=sys.stderr)
            return rows
        if isinstance(page, dict):
            err = page.get("Error") or page.get("error")
            if err:
                print(f"    {year}/{state}: API error {err}", file=sys.stderr)
                return rows
            for v in page.values():
                if isinstance(v, list):
                    page = v
                    break
            else:
                return rows
        if not page:
            break
        rows.extend({k.lower(): v for k, v in row.items()} for row in page)
        if len(page) < page_size:
            break
        start += page_size
    return rows


def _num(v) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _ind(v) -> int:
    """Coerce '0'/'1'/0/1/None to 0/1 integer."""
    if v in (None, "", "0", 0):
        return 0
    if v in ("1", 1):
        return 1
    try:
        return 1 if int(v) else 0
    except (TypeError, ValueError):
        return 0


def air_release_lbs(row: dict) -> float:
    """Air release = stack (point source) + fugitive. The fields can be
    null when the facility didn't report air emissions; coerce to 0."""
    return _num(row.get("stack_tot_rel")) + _num(row.get("fugitive_tot_rel"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="", help="e.g. 2015-2024 or 2020,2022")
    ap.add_argument("--states", default="DE,PA,NJ",
                    help="comma-separated state codes (default DE,PA,NJ)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print summary, don't write tri_chemical_history.json")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    years = parse_years(args.years)
    states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    print(f"Fetching tri_form_r_ez for states={states} years={years[0]}-{years[-1]} "
          f"({len(years)} years × {len(states)} states = {len(years) * len(states)} requests)",
          file=sys.stderr)

    # facilities[trifid][year][chem_id] = {air_lbs, total_lbs}
    facilities: dict[str, dict[str, dict[str, dict]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: {"air_lbs": 0.0, "total_lbs": 0.0}))
    )
    # chemicals[chem_id] = {cas, name, hap_flag, carc_flag, metal_flag}
    chemicals: dict[str, dict] = {}

    for year in years:
        for state in states:
            rows = fetch_year_state(year, state, verbose=args.verbose)
            print(f"  {year}/{state}: {len(rows):,} rows",
                  file=sys.stderr)
            for row in rows:
                trifid = row.get("tri_facility_id") or row.get("tri_facility_id_form")
                chem_id = row.get("tri_chem_id")
                if not trifid or not chem_id:
                    continue
                year_key = str(year)
                bucket = facilities[trifid][year_key][chem_id]
                bucket["air_lbs"] += air_release_lbs(row)
                bucket["total_lbs"] += _num(row.get("total_on_off_site_release"))

                if chem_id not in chemicals:
                    chemicals[chem_id] = {
                        "cas": row.get("cas_registry_number") or "",
                        "name": (row.get("cas_chem_name")
                                 or row.get("chem_name")
                                 or row.get("generic_chem_name")
                                 or "Unknown"),
                        "hap_flag": _ind(row.get("caac_ind")),
                        "carc_flag": _ind(row.get("carc_ind")),
                        "metal_flag": _ind(row.get("metal_ind")),
                    }

    # Round all release values to 1 decimal for compactness.
    for trifid, year_map in facilities.items():
        for year, chem_map in year_map.items():
            for chem_id, vals in chem_map.items():
                vals["air_lbs"] = round(vals["air_lbs"], 1)
                vals["total_lbs"] = round(vals["total_lbs"], 1)

    payload = {
        "_meta": {
            "source": "EPA Envirofacts tri_form_r_ez",
            "endpoint": (BASE_ROOT
                         + "/state_abbr/{state}/reporting_year/{year}/JSON"),
            "states": states,
            "years": years,
            "schema_version": 1,
            "fields_per_release": {
                "air_lbs": "stack_tot_rel + fugitive_tot_rel (point + fugitive air, lbs/yr)",
                "total_lbs": "total_on_off_site_release (all media + transfers, lbs/yr)",
            },
            "chemical_flags": {
                "hap_flag": "caac_ind from TRI — Clean Air Act §112 HAP listing",
                "carc_flag": "carc_ind from TRI — EPA-classified carcinogen",
                "metal_flag": "metal_ind from TRI — metal/metal compound",
            },
            "n_facilities": len(facilities),
            "n_chemicals": len(chemicals),
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "chemicals": chemicals,
        "facilities": {trifid: {y: dict(c) for y, c in ym.items()}
                       for trifid, ym in facilities.items()},
    }

    n_obs = sum(len(c) for ym in facilities.values() for c in ym.values())
    print(f"\nFacilities: {len(facilities):,}  "
          f"Chemicals: {len(chemicals):,}  "
          f"(facility, year, chemical) tuples: {n_obs:,}", file=sys.stderr)
    print(f"HAP-listed chemicals: {sum(1 for c in chemicals.values() if c['hap_flag'])}",
          file=sys.stderr)
    print(f"Carcinogen-listed chemicals: {sum(1 for c in chemicals.values() if c['carc_flag'])}",
          file=sys.stderr)

    if args.dry_run:
        print("\nDry-run only. Re-run without --dry-run to write tri_chemical_history.json.",
              file=sys.stderr)
        return 0

    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"\nWrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.1f} KB)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
