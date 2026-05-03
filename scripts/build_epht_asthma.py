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

# Measure ID 99 is documented in the EPHTrackR R package as
# "Annual Number of Hospitalizations for Asthma".
# --discover will surface other asthma measures the API exposes.
SEED_MEASURES = [99]

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


def list_geographic_items(measure_id: int, geo_type: int) -> list[dict]:
    """Return EPHT geographic-item records for measure × geo_type."""
    payload = _get(f"geography/{measure_id}/{geo_type}/0")
    # Response is typically a list of {geographicItemId, geographicItemName, ...}
    if isinstance(payload, dict) and "geographicItems" in payload:
        return payload["geographicItems"]
    if isinstance(payload, list):
        return payload
    return []


def find_de_geo_ids(items: list[dict], geo_type: int) -> dict[str, str]:
    """Map FIPS → EPHT geographic-item ID for Delaware items.

    EPHT response field names vary; we look at common candidates:
      - geographicItemId / id
      - geo / geoCode / fips (raw FIPS, padded)
      - parent / parentGeoId (state FIPS context)
    """
    out: dict[str, str] = {}
    fips_targets = (
        {DE_STATE_FIPS} if geo_type == GEO_TYPE_STATE
        else set(DE_COUNTY_FIPS.keys())
    )
    for item in items:
        item_id = (item.get("geographicItemId") or item.get("id"))
        # Try a number of plausible field names for the FIPS code:
        candidates = [
            item.get("geo"), item.get("geoCode"), item.get("fips"),
            item.get("countyFips"), item.get("stateFips"),
            item.get("geographicItemCode"),
        ]
        for fips in candidates:
            if fips is None:
                continue
            fips_s = str(fips).zfill(5 if geo_type == GEO_TYPE_COUNTY else 2)
            if fips_s in fips_targets:
                out[fips_s] = str(item_id)
                break
    return out


def list_stratification_levels(measure_id: int, geo_type: int) -> list[dict]:
    return _get(f"stratificationlevel/{measure_id}/{geo_type}/0")


def fetch_data(measure_id: int, strat_level_id: str,
               geo_type: int, geo_items: list[str],
               temporal_type: str = "1", temporal_items: list[str] | None = None
               ) -> list[dict]:
    """POST /getCoreHolder. Returns parsed core records."""
    body = {
        "geographicTypeIdFilter": str(geo_type),
        "geographicItemsFilter":  ",".join(str(g) for g in geo_items),
        "temporalTypeIdFilter":   str(temporal_type),
        "temporalItemsFilter":    ",".join(str(t) for t in (temporal_items or [])),
    }
    payload = _post(f"getCoreHolder/{measure_id}/{strat_level_id}/0/0", body)
    if isinstance(payload, dict):
        # Common shapes: {tableResult: [...]}, {resultRows: [...]}
        for key in ("tableResult", "resultRows", "data", "rows"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    if isinstance(payload, list):
        return payload
    return []


def normalize_value(row: dict) -> tuple[float | None, str | None]:
    """Pluck (value, year) out of a core record. Field names vary."""
    val = (row.get("dataValue") or row.get("value") or row.get("rate") or
           row.get("displayValue"))
    year = (row.get("year") or row.get("yearStart") or row.get("temporalItem"))
    try:
        val = float(val) if val not in (None, "", "*") else None
    except (TypeError, ValueError):
        val = None
    return val, str(year) if year is not None else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--discover", action="store_true",
                        help="List asthma measures and DE geographic IDs; do not fetch data")
    parser.add_argument("--measure", type=int, action="append",
                        help="Fetch a specific measure ID; repeatable. Default: " +
                             ",".join(str(m) for m in SEED_MEASURES))
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be written; do not write epht_asthma.json")
    args = parser.parse_args()

    if args.discover:
        print("Asthma measures available on EPHT:")
        for m in discover_asthma_measures():
            print(f"  id={m['id']:<6} {m['title']}")
        print("\nDE geographic IDs (state):")
        items = list_geographic_items(SEED_MEASURES[0], GEO_TYPE_STATE)
        de_state = find_de_geo_ids(items, GEO_TYPE_STATE)
        for fips, gid in sorted(de_state.items()):
            print(f"  fips={fips}  epht_geo_id={gid}")
        print("\nDE geographic IDs (county):")
        items = list_geographic_items(SEED_MEASURES[0], GEO_TYPE_COUNTY)
        de_counties = find_de_geo_ids(items, GEO_TYPE_COUNTY)
        for fips, gid in sorted(de_counties.items()):
            print(f"  fips={fips} ({DE_COUNTY_FIPS.get(fips, '?')})  epht_geo_id={gid}")
        return

    measures_to_fetch = args.measure or SEED_MEASURES
    print(f"Fetching {len(measures_to_fetch)} EPHT measure(s) for Delaware: {measures_to_fetch}")

    counties: dict[str, dict] = {fips: {"name": name, "measures": {}}
                                 for fips, name in DE_COUNTY_FIPS.items()}
    state: dict = {"fips": DE_STATE_FIPS, "name": "Delaware", "measures": {}}
    measures_meta: dict[str, dict] = {}

    for mid in measures_to_fetch:
        print(f"\nMeasure {mid}:")
        # 1) Discover geo items + stratification levels
        items_state = list_geographic_items(mid, GEO_TYPE_STATE)
        de_state_id = find_de_geo_ids(items_state, GEO_TYPE_STATE).get(DE_STATE_FIPS)
        items_county = list_geographic_items(mid, GEO_TYPE_COUNTY)
        de_county_ids = find_de_geo_ids(items_county, GEO_TYPE_COUNTY)
        print(f"  state geo id: {de_state_id}; county geo ids: {de_county_ids}")

        strat_levels = list_stratification_levels(mid, GEO_TYPE_COUNTY)
        if not strat_levels:
            print(f"  no stratification levels; skipping")
            continue
        # Use the first available stratification level by default; --discover
        # surfaces alternates if there are stratified versions worth fetching.
        strat = strat_levels[0]
        strat_id = (strat.get("stratificationLevelId") or strat.get("id") or
                    strat.get("stratificationLevelLocalId"))
        strat_label = (strat.get("stratificationLevelName") or strat.get("name") or strat_id)
        print(f"  stratification: {strat_label} ({strat_id})")

        measures_meta[str(mid)] = {
            "title": next((m["title"] for m in discover_asthma_measures() if m["id"] == mid),
                          f"Measure {mid}"),
            "stratification": strat_label,
        }

        # 2) Fetch county-level rows
        if de_county_ids:
            rows = fetch_data(mid, str(strat_id), GEO_TYPE_COUNTY,
                              list(de_county_ids.values()))
            print(f"  fetched {len(rows)} county rows")
            id_to_fips = {v: k for k, v in de_county_ids.items()}
            for row in rows:
                gid = str(row.get("geographicItemId") or row.get("geo") or "")
                fips = id_to_fips.get(gid)
                if not fips:
                    continue
                val, year = normalize_value(row)
                bucket = counties[fips]["measures"].setdefault(str(mid), {"by_year": {}})
                if year:
                    bucket["by_year"][year] = val

        # 3) Fetch state-level rows (covers age-stratified pediatric variants)
        if de_state_id:
            rows = fetch_data(mid, str(strat_id), GEO_TYPE_STATE, [de_state_id])
            print(f"  fetched {len(rows)} state rows")
            for row in rows:
                val, year = normalize_value(row)
                bucket = state["measures"].setdefault(str(mid), {"by_year": {}})
                if year:
                    bucket["by_year"][year] = val

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
