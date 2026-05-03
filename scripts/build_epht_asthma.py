#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026 <YOUR NAME>. See LICENSE.md.
"""
build_epht_asthma.py — fetch CDC EPHT Tracking Network asthma measures for DE

The repo's existing places_tracts.json carries CDC PLACES adult-asthma
prevalence (BRFSS-derived survey estimate) at census-tract level. EPHT
adds *observed* health-care utilization — actual ED visits and hospital
admissions for asthma — at state and county granularity. These two
sources are complementary: PLACES tells you "how many people report
having asthma"; EPHT tells you "how many people went to the ER or were
admitted for an asthma attack." High EPHT relative to PLACES suggests
worse asthma control or worse environmental triggers, both of which are
EJ-relevant signals.

Geographic granularity for asthma measures on EPHT is **state and county
only** (not census tract). Pediatric (age-stratified) breakouts are
**state-level only** on the national EPHT — county-level numbers are
all-ages.

Endpoints (CDC EPHT Tracking Network Data API, base
https://ephtracking.cdc.gov/apigateway/api/v1):

  GET  /measuresearch
       List all measures. Filter for asthma-related entries.

  GET  /geography/{measureId}/{geoTypeId}/{rollup}
       List the EPHT-internal geographic IDs supported by a measure
       at a given geographic level (state, county). EPHT uses its own
       integer IDs internally — not raw FIPS — so we have to look these
       up before fetching data.

  GET  /stratificationlevel/{measureId}/{geoTypeId}/{smoothing}
       List stratification levels (e.g. ST = state, ST_CT = state x
       county, age-stratified variants). We use the lowest geographic
       grain available.

  POST /getCoreHolder/{measureId}/{stratificationLevelId}/{isSmoothed}/0
       Fetch the actual data values. JSON body fields are all strings:
         { "geographicTypeIdFilter": "...",
           "geographicItemsFilter":  "comma-separated EPHT geo IDs",
           "temporalTypeIdFilter":   "...",
           "temporalItemsFilter":    "comma-separated years" }

Authentication (optional but recommended): pass an API token as a query
parameter (?apiToken=...). Get a token by emailing trackingsupport@cdc.gov
and set it as the EPHT_API_KEY environment variable.

Usage:
    # 1) See which asthma measures the API exposes for Delaware
    python3 scripts/build_epht_asthma.py --discover

    # 2) Default: fetch confirmed asthma measures for DE counties + state
    python3 scripts/build_epht_asthma.py

    # 3) Preview without writing
    python3 scripts/build_epht_asthma.py --dry-run

    # 4) Fetch a specific measure ID
    python3 scripts/build_epht_asthma.py --measure 99

Requires: requests
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip install requests first")


BASE = "https://ephtracking.cdc.gov/apigateway/api/v1"
OUT  = Path(__file__).parent.parent / "epht_asthma.json"

# Default measures fetched. Picked for renderer fit:
#   101 = Crude Rate of Hospitalizations for Asthma per 10,000 (state x county)
#   103 = Age-adjusted Rate of Hospitalizations for Asthma per 10,000 (state x county)
#   588 = Crude Prevalence of Children <=17 Currently Diagnosed with Asthma (state)
# --discover lists every asthma measure the API exposes; pass --measure ID
# to add others (e.g. tract-level 894/897/900 once we add tract support).
# Measure 436 (county ED visit rate) returns HTTP 405 from getCoreHolder
# under all stratification levels we've tried — likely deprecated; the
# tract-level ED-visit measures (894/897/900) are the modern path.
SEED_MEASURES = [101, 103, 588]

# Geographic type IDs per CDC EPHT convention. These are stable and used
# as defaults; --discover will validate them.
GEO_TYPE_STATE  = 1
GEO_TYPE_COUNTY = 2

DE_STATE_FIPS = "10"
DE_COUNTY_FIPS = {"10001": "Kent", "10003": "New Castle", "10005": "Sussex"}


def _token_qs() -> str:
    """Return the apiToken query-string fragment, or empty string."""
    tok = os.environ.get("EPHT_API_KEY")
    return f"?apiToken={tok}" if tok else ""


def _get(path: str, timeout: int = 60) -> list | dict:
    url = f"{BASE}/{path}{_token_qs()}"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, body: dict, timeout: int = 60) -> list | dict:
    url = f"{BASE}/{path}{_token_qs()}"
    resp = requests.post(url, json=body, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def discover_asthma_measures() -> list[dict]:
    """Return all measures whose title contains 'asthma' (case-insensitive)."""
    measures = _get("measuresearch")
    if not isinstance(measures, list):
        sys.exit(f"Unexpected /measuresearch response shape: {type(measures).__name__}")
    asthma = []
    for m in measures:
        # Field names vary slightly between EPHT releases; try a few.
        title = (m.get("measureName") or m.get("name") or
                 m.get("measureTitle") or m.get("title") or "")
        mid = (m.get("measureId") or m.get("id") or m.get("measureID"))
        if "asthma" in str(title).lower() and mid is not None:
            asthma.append({"id": mid, "title": title, "raw": m})
    return asthma


def list_stratification_levels(measure_id: int, geo_type: int) -> list[dict]:
    """Return EPHT stratification levels for a measure × geographic type."""
    return _get(f"stratificationlevel/{measure_id}/{geo_type}/0")


# CDC removed the /geography/{measureId}/{geoTypeId}/0 lookup endpoint
# (returns 410 Gone). Modern EPHT accepts raw FIPS strings directly in
# geographicItemsFilter, and getCoreHolder responses include `geoId`
# already in FIPS form, so the lookup-then-fetch dance is unnecessary.
# Kept here as a no-op stub so any external callers don't crash.
def list_geographic_items(measure_id: int, geo_type: int) -> list[dict]:
    return []


def find_de_geo_ids(items: list[dict], geo_type: int) -> dict[str, str]:
    return {}


def fetch_data(measure_id: int, strat_level_id: str,
               geo_type: int, geo_items: list[str],
               temporal_type: str = "1", temporal_items: list[str] | None = None
               ) -> list[dict]:
    """POST /getCoreHolder. Returns the tableResult rows."""
    body = {
        "geographicTypeIdFilter": str(geo_type),
        "geographicItemsFilter":  ",".join(str(g) for g in geo_items),
        "temporalTypeIdFilter":   str(temporal_type),
        "temporalItemsFilter":    ",".join(str(t) for t in (temporal_items or [])),
    }
    payload = _post(f"getCoreHolder/{measure_id}/{strat_level_id}/0/0", body)
    if isinstance(payload, dict):
        for key in ("tableResult", "resultRows", "data", "rows"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    if isinstance(payload, list):
        return payload
    return []


def normalize_row(row: dict) -> tuple[str | None, str | None, float | None]:
    """Pluck (geo_id, year, value) from a tableResult row.

    EPHT now returns FIPS directly in `geoId`, year in `temporal`, and the
    value in `dataValue`. Suppressed cells (suppressionFlag='1') return
    value=None — privacy suppression rather than missing data.
    """
    geo_id = str(row.get("geoId") or row.get("geo") or "") or None
    year = (row.get("temporal") or row.get("temporalId") or row.get("year"))
    suppressed = str(row.get("suppressionFlag", "0")) == "1"
    raw_val = (row.get("dataValue") or row.get("displayValue") or row.get("value"))
    if suppressed or raw_val in (None, "", "*"):
        val: float | None = None
    else:
        try:
            val = float(raw_val)
        except (TypeError, ValueError):
            val = None
    return geo_id, (str(year) if year is not None else None), val



def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--discover", action="store_true",
                        help="List asthma measures and DE geographic IDs; do not fetch data")
    parser.add_argument("--measure", type=int, action="append",
                        help="Fetch a specific measure ID; repeatable. Default: " +
                             ",".join(str(m) for m in SEED_MEASURES))
    parser.add_argument("--years",
                        help="Comma-separated years to fetch (e.g. '2018,2019,2020,2021,2022,2023'). "
                             "Default: 2018-2023.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be written; do not write epht_asthma.json")
    args = parser.parse_args()

    if args.discover:
        print("Asthma measures available on EPHT:")
        for m in discover_asthma_measures():
            print(f"  id={m['id']:<6} {m['title']}")
        print("\nNote: CDC removed the /geography lookup endpoint (returns 410 Gone).")
        print("FIPS go directly into geographicItemsFilter — no lookup needed.")
        print(f"  DE state FIPS:    {DE_STATE_FIPS}")
        print(f"  DE county FIPS:   {', '.join(sorted(DE_COUNTY_FIPS.keys()))}")
        return

    measures_to_fetch = args.measure or SEED_MEASURES
    years = [y.strip() for y in (args.years or "").split(",") if y.strip()]
    if not years:
        # Default: most-recent ~6 years. EPHT data lags by 1-2 years for
        # hospitalization measures; older years are the safer floor.
        years = [str(y) for y in range(2018, 2024)]
    print(f"Fetching {len(measures_to_fetch)} EPHT measure(s) for Delaware: {measures_to_fetch}")
    print(f"Years: {','.join(years)}")

    counties: dict[str, dict] = {fips: {"name": name, "measures": {}}
                                 for fips, name in DE_COUNTY_FIPS.items()}
    state: dict = {"fips": DE_STATE_FIPS, "name": "Delaware", "measures": {}}
    measures_meta: dict[str, dict] = {}

    # Pre-fetch the asthma measure catalog once for title lookups.
    catalog = {m["id"]: m["title"] for m in discover_asthma_measures()}

    # Counts are tallied here so the final summary is honest about what
    # actually populated vs. what failed — useful when iterating on
    # measure IDs that may have been deprecated upstream.
    fetch_errors: list[tuple[int, str, str]] = []

    for mid in measures_to_fetch:
        print(f"\nMeasure {mid} ({catalog.get(mid, '?')}):")

        # Stratification lookup. Wrapped because some legacy measures
        # also error here, and we'd rather skip than abort the whole run.
        try:
            strat_county = list_stratification_levels(mid, GEO_TYPE_COUNTY)
        except requests.RequestException as e:
            strat_county = []
            fetch_errors.append((mid, "stratification (county)", str(e)))
        try:
            strat_state = list_stratification_levels(mid, GEO_TYPE_STATE)
        except requests.RequestException as e:
            strat_state = []
            fetch_errors.append((mid, "stratification (state)", str(e)))

        county_strat_id = None
        if isinstance(strat_county, list) and strat_county:
            county_strat_id = (strat_county[0].get("id") or
                               strat_county[0].get("stratificationLevelId"))

        state_strat_id = None
        if isinstance(strat_state, list) and strat_state:
            state_strat_id = (strat_state[0].get("id") or
                              strat_state[0].get("stratificationLevelId"))

        measures_meta[str(mid)] = {
            "title": catalog.get(mid, f"Measure {mid}"),
            "county_supported": county_strat_id is not None,
            "state_supported":  state_strat_id is not None,
        }

        # County-level fetch: FIPS strings go directly in the filter.
        if county_strat_id is not None:
            try:
                rows = fetch_data(mid, str(county_strat_id), GEO_TYPE_COUNTY,
                                  list(DE_COUNTY_FIPS.keys()),
                                  temporal_items=years)
                print(f"  county: {len(rows)} rows")
                for row in rows:
                    geo_id, year, val = normalize_row(row)
                    if geo_id not in DE_COUNTY_FIPS or not year:
                        continue
                    bucket = counties[geo_id]["measures"].setdefault(
                        str(mid), {"by_year": {}})
                    bucket["by_year"][year] = val
            except requests.RequestException as e:
                print(f"  county: ERROR {e}")
                fetch_errors.append((mid, "county", str(e)))
        else:
            print(f"  county: not supported by this measure")

        # State-level fetch (covers pediatric/age-stratified measures
        # like 587/588 that only release at state grain).
        if state_strat_id is not None:
            try:
                rows = fetch_data(mid, str(state_strat_id), GEO_TYPE_STATE,
                                  [DE_STATE_FIPS], temporal_items=years)
                print(f"  state:  {len(rows)} rows")
                for row in rows:
                    geo_id, year, val = normalize_row(row)
                    if geo_id != DE_STATE_FIPS or not year:
                        continue
                    bucket = state["measures"].setdefault(str(mid), {"by_year": {}})
                    bucket["by_year"][year] = val
            except requests.RequestException as e:
                print(f"  state:  ERROR {e}")
                fetch_errors.append((mid, "state", str(e)))
        else:
            print(f"  state:  not supported by this measure")

    if fetch_errors:
        print(f"\n{len(fetch_errors)} fetch error(s):")
        for mid, where, msg in fetch_errors:
            print(f"  measure {mid} ({where}): {msg}")

    payload = {
        "_meta": {
            "source":        "CDC Environmental Public Health Tracking Network",
            "url":           "https://ephtracking.cdc.gov/",
            "api_base":      BASE,
            "state":         "DE",
            "measures":      measures_meta,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note":          "Observed asthma health-care utilization (ED visits, "
                             "hospitalizations) at state + county granularity. "
                             "Pediatric (age-stratified) breakouts are state-level "
                             "only on the national EPHT — county values are all-ages.",
        },
        "state":    state,
        "counties": counties,
    }

    if args.dry_run:
        print("\nDRY RUN — payload preview:")
        for fips, c in counties.items():
            print(f"  {fips} {c['name']}: {len(c['measures'])} measures")
        return

    with OUT.open("w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"\nWrote {OUT.name}")


if __name__ == "__main__":
    main()
