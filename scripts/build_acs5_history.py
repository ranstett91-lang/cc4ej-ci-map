#!/usr/bin/env python3
"""
build_acs5_history.py -- fetch ACS 5-year demographics 2009-2015 for all
Delaware block groups and merge them into de_blockgroups_history.json.

Why this exists
---------------
EJScreen only publishes releases from 2016 onward, so any slider position
before 2016 used to silently fall back to the 2016 vintage (see the old
`_resolveHistoryYear` clamp). This script backfills 2009-2015 from ACS 5-year
directly, giving the Demographics info-panel section real data for those
years. Air / EJScreen-only fields are written as explicit null in each new
year record so they render as "—" in the panel (see EJSCREEN_ONLY_FIELDS in
_census_common.py).

Data flow
---------
For each vintage YYYY in 2009..2015:
  1. Query api.census.gov/data/YYYY/acs/acs5 for Delaware state (10),
     all 3 counties, block-group geography.
  2. Derive the five canonical demographic percentages:
       lowinc_pct       = pop below 2x poverty / pop with poverty status
       unemp_pct        = unemployed / civilian labor force, age 16+
       lingiso_pct      = limited-English-speaking households / total HH
       edu_nohsdip_pct  = pop 25+ with less than HS / pop 25+
       poc_pct          = 100 - (non-Hispanic white / total)
  3. Produce a per-bg10 record dict via _census_common.build_demo_record.
  4. Crosswalk bg10 GEOIDs to bg20 GEOIDs using the existing
     scripts/bg10_to_bg20_DE.csv (population-weighted, already in place).
  5. Merge the year into de_blockgroups_history.json.

Usage
-----
  python3 scripts/build_acs5_history.py                # fetches all 2009-2015
  python3 scripts/build_acs5_history.py --years 2014 2015
  python3 scripts/build_acs5_history.py --dry-run       # print, don't write
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).parent))

from _census_common import (  # noqa: E402
    _census_clean,
    apply_crosswalk,
    build_demo_record,
    load_crosswalk,
    load_history,
    merge_year,
    safe_pct,
    save_history,
)

CROSSWALK_FILE = Path(__file__).parent / "bg10_to_bg20_DE.csv"
STATE_FIPS = "10"
COUNTY_FIPS = ("001", "003", "005")
DEFAULT_YEARS = tuple(range(2009, 2016))

# ACS variable IDs. Each group below is a (numerator-list, denominator) pair
# for the canonical percent. Fields chosen to be stable across 2009-2015.
VARS = {
    # Total pop + non-Hispanic white (for poc_pct)
    "B03002_001E": "pop_total",
    "B03002_003E": "pop_nhwhite",
    # Ratio of income to poverty — under 2x poverty (EJScreen's low-income cut)
    # C17002 was introduced in 2010 ACS; 2009 vintage uses C17002 as well
    # (confirmed in Census API catalog for 2005-2009 release).
    "C17002_001E": "pov_universe",
    "C17002_002E": "pov_under_0_5",
    "C17002_003E": "pov_0_5_to_0_99",
    "C17002_004E": "pov_1_0_to_1_24",
    "C17002_005E": "pov_1_25_to_1_49",
    "C17002_006E": "pov_1_5_to_1_84",
    "C17002_007E": "pov_1_85_to_1_99",
    # Employment status (age 16+)
    "B23025_003E": "labor_force",
    "B23025_005E": "unemployed",
    # Linguistic isolation — limited-English-speaking households (C16002)
    "C16002_001E": "hh_universe",
    "C16002_004E": "hh_lep_spanish",
    "C16002_007E": "hh_lep_indoeu",
    "C16002_010E": "hh_lep_api",
    "C16002_013E": "hh_lep_other",
    # Educational attainment (place-of-birth table, works universally)
    "B06009_001E": "pop_25plus",
    "B06009_002E": "edu_less_than_hs",
}


def _fetch_json(url: str, timeout: int = 60, retries: int = 3) -> list[list[str]]:
    """GET the Census Data API, retrying on transient network errors."""
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "cc4ej-ci-map/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"census API unreachable: {url} -- last error: {last_err}")


def _fetch_vintage(year: int) -> dict[str, dict]:
    """Return {bg10_geoid: {field: value, ...}} for all DE block groups in
    the given ACS 5-year vintage. Raises on network or API failure."""
    vars_csv = ",".join(sorted(VARS.keys()))
    out: dict[str, dict] = {}
    for county in COUNTY_FIPS:
        url = (
            f"https://api.census.gov/data/{year}/acs/acs5"
            f"?get={vars_csv}"
            f"&for=block%20group:*"
            f"&in=state:{STATE_FIPS}%20county:{county}"
        )
        print(f"  GET {url}")
        rows = _fetch_json(url)
        header = rows[0]
        idx = {name: i for i, name in enumerate(header)}
        # Geography columns returned by the API for BG queries:
        #   state, county, tract, block group
        for r in rows[1:]:
            bg10 = (
                r[idx["state"]]
                + r[idx["county"]]
                + r[idx["tract"]]
                + r[idx["block group"]]
            )
            rec_raw = {friendly: r[idx[v]] for v, friendly in VARS.items()}
            rec = _derive_demo(rec_raw)
            out[bg10] = rec
    return out


def _derive_demo(raw: dict[str, str]) -> dict:
    """Collapse raw Census counts into the five canonical demographic
    percentages. Each returns None when the denominator universe is zero or
    either operand is a Census suppression sentinel (negative value)."""
    total = _census_clean(raw.get("pop_total"))
    nhwhite = _census_clean(raw.get("pop_nhwhite"))
    poc_pct = None
    if total is not None and nhwhite is not None and total > 0:
        poc_pct = round(100.0 * (total - nhwhite) / total, 1)

    pov_under_2x = _sum_optional(
        raw, (
            "pov_under_0_5", "pov_0_5_to_0_99",
            "pov_1_0_to_1_24", "pov_1_25_to_1_49",
            "pov_1_5_to_1_84", "pov_1_85_to_1_99",
        ),
    )
    lowinc_pct = safe_pct(pov_under_2x, raw.get("pov_universe"))

    unemp_pct = safe_pct(raw.get("unemployed"), raw.get("labor_force"))

    lep_sum = _sum_optional(raw, ("hh_lep_spanish", "hh_lep_indoeu",
                                   "hh_lep_api", "hh_lep_other"))
    lingiso_pct = safe_pct(lep_sum, raw.get("hh_universe"))

    edu_nohsdip_pct = safe_pct(raw.get("edu_less_than_hs"), raw.get("pop_25plus"))

    return {
        "lowinc_pct": lowinc_pct,
        "unemp_pct": unemp_pct,
        "lingiso_pct": lingiso_pct,
        "edu_nohsdip_pct": edu_nohsdip_pct,
        "poc_pct": poc_pct,
    }


def _sum_optional(raw: dict[str, str], keys: Iterable[str]) -> float | None:
    """Sum Census cells (after sentinel filtering via _census_clean); return
    None if ALL are missing/suppressed. A single valid cell is enough to
    produce a partial sum (ACS suppresses some detail cells independently)."""
    total = 0.0
    seen_any = False
    for k in keys:
        v = _census_clean(raw.get(k))
        if v is None:
            continue
        total += v
        seen_any = True
    return total if seen_any else None


def run(years: Iterable[int], dry_run: bool = False) -> None:
    xwalk = load_crosswalk(CROSSWALK_FILE)
    if not xwalk:
        raise SystemExit(
            f"crosswalk missing or empty: {CROSSWALK_FILE}\n"
            "run scripts/prep_crosswalk.py first, or commit bg10_to_bg20_DE.csv"
        )

    hist = load_history()
    for year in years:
        print(f"\n=== ACS 5-year {year} ({year - 4}-{year}) ===")
        try:
            raw_bg10 = _fetch_vintage(year)
        except RuntimeError as e:
            print(f"  SKIPPED: {e}")
            continue
        print(f"  fetched {len(raw_bg10)} bg10 records")
        # Wrap each demo record with explicit null for EJScreen-only fields
        # BEFORE crosswalking so the merge produces correctly-shaped dst records.
        wrapped = {bg10: build_demo_record(rec) for bg10, rec in raw_bg10.items()}
        # Demographics crosswalk uses area-weighted means, which is what
        # apply_crosswalk does when weights are 0..1 proportions. Each bg20
        # that overlaps multiple bg10s gets a weighted average of the
        # demographic percentages.
        bg20 = apply_crosswalk(wrapped, xwalk)
        print(f"  crosswalked to {len(bg20)} bg20 records")
        merge_year(hist, year, bg20)

    if dry_run:
        sample_geoid = next(iter(next(iter(hist.values())).keys()), None) if hist else None
        print(f"\nDRY RUN — would write {len(hist)} years; sample record "
              f"({sample_geoid} in {sorted(hist.keys())[-1] if hist else 'n/a'}):")
        if sample_geoid:
            latest = sorted(hist.keys())[-1]
            print(json.dumps(hist[latest].get(sample_geoid, {}), indent=2))
        return
    save_history(hist)
    print(f"\nwrote {len(hist)} years to de_blockgroups_history.json")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--years", nargs="+", type=int, default=list(DEFAULT_YEARS))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(args.years, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
