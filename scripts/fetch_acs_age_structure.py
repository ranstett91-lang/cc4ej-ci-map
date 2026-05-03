#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026 <YOUR NAME>. See LICENSE.md.
"""
fetch_acs_age_structure.py — DE county age structure from ACS 5-year

Fetches total population, population under 18, and population 65+ for the
three Delaware counties (Kent 10001, New Castle 10003, Sussex 10005) from
the US Census ACS 5-year API table B01001 (sex by age), and returns a
dict keyed by 5-digit county FIPS.

Used by build_at_risk_populations.py to populate the age-structure rows
of the "At-Risk Populations" panel. This matches the denominator used by
the American Lung Association's State of the Air methodology, which
applies state BRFSS rates to county U-18 Census populations.

Usage (standalone):
    python3 scripts/fetch_acs_age_structure.py            # print summary
    python3 scripts/fetch_acs_age_structure.py --year 2023

Notes:
    - The ACS API is keyless for small queries (fewer than 50/day). For
      higher volume, set CENSUS_API_KEY in the environment.
    - B01001_001E is total population.
    - Under-18 bins: B01001_003E..006E (male) + B01001_027E..030E (female).
    - 65+ bins: B01001_020E..025E (male) + B01001_044E..049E (female).

Requires: requests  (pip install requests)
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("pip install requests first")


DE_COUNTIES = {"001": "Kent", "003": "New Castle", "005": "Sussex"}

# ACS B01001 sex-by-age bin codes for under-18 and 65+
U18_BINS_MALE   = [f"B01001_{n:03d}E" for n in (3, 4, 5, 6)]       # <5, 5-9, 10-14, 15-17
U18_BINS_FEMALE = [f"B01001_{n:03d}E" for n in (27, 28, 29, 30)]
O65_BINS_MALE   = [f"B01001_{n:03d}E" for n in (20, 21, 22, 23, 24, 25)]  # 65-66,67-69,70-74,75-79,80-84,85+
O65_BINS_FEMALE = [f"B01001_{n:03d}E" for n in (44, 45, 46, 47, 48, 49)]

TOTAL_BIN = "B01001_001E"
ALL_BINS = [TOTAL_BIN] + U18_BINS_MALE + U18_BINS_FEMALE + O65_BINS_MALE + O65_BINS_FEMALE


def fetch_acs(year: int = 2023, state_fips: str = "10",
              api_key: Optional[str] = None) -> dict[str, dict]:
    """Return {fips5: {pop, u18_count, u18_pct, o65_count, o65_pct, vintage}}."""
    url = f"https://api.census.gov/data/{year}/acs/acs5"
    params = {
        "get": "NAME," + ",".join(ALL_BINS),
        "for": f"county:{','.join(DE_COUNTIES.keys())}",
        "in":  f"state:{state_fips}",
    }
    if api_key:
        params["key"] = api_key

    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    rows = resp.json()
    header, *data = rows
    idx = {col: i for i, col in enumerate(header)}

    out: dict[str, dict] = {}
    for row in data:
        county = row[idx["county"]]
        state  = row[idx["state"]]
        fips5  = f"{state}{county}"
        pop    = int(row[idx[TOTAL_BIN]])
        u18    = sum(int(row[idx[b]]) for b in U18_BINS_MALE + U18_BINS_FEMALE)
        o65    = sum(int(row[idx[b]]) for b in O65_BINS_MALE   + O65_BINS_FEMALE)
        out[fips5] = {
            "name":      DE_COUNTIES.get(county, f"County {county}"),
            "pop":       pop,
            "u18_count": u18,
            "u18_pct":   round(100.0 * u18 / pop, 1) if pop else None,
            "o65_count": o65,
            "o65_pct":   round(100.0 * o65 / pop, 1) if pop else None,
            "vintage":   f"{year - 4}-{year}",  # 5-year window ending at year
        }
    return out


# Census "places" are incorporated cities/towns, separate from counties.
# The repo uses county + tract levels for most data; places let us surface
# a sub-county layer like "City of Wilmington" without redrawing geometry.
DE_PLACES = {
    # Wilmington — the EJ-vulnerable urban core of New Castle County.
    # Census place FIPS 77580. Within county FIPS 10003.
    "1077580": {"name": "Wilmington", "state": "10", "place": "77580", "parent_county": "10003"},
}


def fetch_acs_places(year: int = 2023,
                     api_key: Optional[str] = None) -> dict[str, dict]:
    """Return ACS age-structure for each entry in DE_PLACES, keyed by state+place FIPS."""
    url = f"https://api.census.gov/data/{year}/acs/acs5"
    out: dict[str, dict] = {}
    for key, meta in DE_PLACES.items():
        params = {
            "get": "NAME," + ",".join(ALL_BINS),
            "for": f"place:{meta['place']}",
            "in":  f"state:{meta['state']}",
        }
        if api_key:
            params["key"] = api_key
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            rows = resp.json()
        except (requests.RequestException, ValueError):
            continue
        if not rows or len(rows) < 2:
            continue
        header, *data = rows
        idx = {col: i for i, col in enumerate(header)}
        row = data[0]
        pop = int(row[idx[TOTAL_BIN]])
        u18 = sum(int(row[idx[b]]) for b in U18_BINS_MALE + U18_BINS_FEMALE)
        o65 = sum(int(row[idx[b]]) for b in O65_BINS_MALE   + O65_BINS_FEMALE)
        out[key] = {
            "name":          meta["name"],
            "parent_county": meta["parent_county"],
            "pop":           pop,
            "u18_count":     u18,
            "u18_pct":       round(100.0 * u18 / pop, 1) if pop else None,
            "o65_count":     o65,
            "o65_pct":       round(100.0 * o65 / pop, 1) if pop else None,
            "vintage":       f"{year - 4}-{year}",
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--year", type=int, default=2023,
                        help="Latest year of the ACS 5-year window (default 2023)")
    parser.add_argument("--places", action="store_true",
                        help="Also print DE places (Wilmington)")
    args = parser.parse_args()

    key = os.environ.get("CENSUS_API_KEY")
    data = fetch_acs(year=args.year, api_key=key)
    for fips, rec in sorted(data.items()):
        print(f"{fips} {rec['name']}: pop={rec['pop']:,}  "
              f"u18={rec['u18_count']:,} ({rec['u18_pct']}%)  "
              f"65+={rec['o65_count']:,} ({rec['o65_pct']}%)  "
              f"[{rec['vintage']}]")

    if args.places:
        places = fetch_acs_places(year=args.year, api_key=key)
        for fips, rec in sorted(places.items()):
            print(f"{fips} {rec['name']} (city, within {rec['parent_county']}): "
                  f"pop={rec['pop']:,}  "
                  f"u18={rec['u18_count']:,} ({rec['u18_pct']}%)  "
                  f"65+={rec['o65_count']:,} ({rec['o65_pct']}%)  "
                  f"[{rec['vintage']}]")


if __name__ == "__main__":
    main()
