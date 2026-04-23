#!/usr/bin/env python3
"""
fetch_noaa_climate.py \u2014 pull NOAA observed annual climate for Delaware.

Hits NOAA's Climate Data Online v2 API (`ncei.noaa.gov/cdo-web/api/v2/data`)
for the Global Summary of the Year (GSOY) dataset across the three
Delaware counties and writes a county/year index the map scrubber can
use for its "observed climate" overlay:

    noaa_climate_history.json
        {
          "_meta": {
            "source":   "NOAA GSOY via Climate Data Online v2",
            "counties": {"10001": "Kent", "10003": "New Castle", "10005": "Sussex"},
            "years":    [1970, ..., 2024],
            "units":    {"tavg": "F", "prcp": "inches"},
            "baseline": [1991, 2020],
            "baseline_values": { "10001": {"tavg_f": ..., "prcp_in": ...}, ... },
            "retrieved_utc": "..."
          },
          "years": {
            "1970": {
              "10001": {"tavg_f": 55.3, "prcp_in": 43.2, "stations": 3},
              "10003": {...},
              "10005": {...}
            },
            ...
          }
        }

We aggregate to the county by averaging across all stations that
reported that year's annual summary. `stations` is the count that fed
the mean, so the frontend can flag thin-data years.

Usage
-----
    export NOAA_TOKEN="your-cdo-token-here"
    python3 scripts/fetch_noaa_climate.py
    python3 scripts/fetch_noaa_climate.py --start-year 1950
    python3 scripts/fetch_noaa_climate.py --token ABCDE... --dry-run

Request for a token at https://www.ncdc.noaa.gov/cdo-web/token.
NOAA's limits: 5 req/sec, 1 000 req/day. We sleep ~250ms between calls.

Requires: requests  (pip3 install requests)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests first")


OUT = Path(__file__).parent.parent / "noaa_climate_history.json"

API = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"

# Delaware counties. FIPS:10001 is Kent, 10003 is New Castle, 10005 is Sussex.
DE_COUNTIES: dict[str, str] = {
    "10001": "Kent",
    "10003": "New Castle",
    "10005": "Sussex",
}

# We want annual tavg (\u00b0F, with units=standard) and annual precip (inches).
DATATYPES = ["TAVG", "PRCP"]

DEFAULT_FIRST = 1970
DEFAULT_LAST  = datetime.now(timezone.utc).year - 1

# 30-year climate "normal" baseline window, per WMO convention.
BASELINE = (1991, 2020)


# NOAA CDO rejects date ranges longer than 10 years on /data. We chunk.
MAX_WINDOW_YEARS = 10


def _fetch_one_window(token: str, county_fips: str,
                      start_year: int, end_year: int,
                      verbose: bool, sleep_s: float) -> list[dict]:
    """Fetch one \u2264 10-year window for a county, paginating with offset."""
    headers = {"token": token, "User-Agent": "cc4ej-ci-map/1.0"}
    params_base = {
        "datasetid":  "GSOY",
        "locationid": f"FIPS:{county_fips}",
        "datatypeid": DATATYPES,
        "startdate":  f"{start_year}-01-01",
        "enddate":    f"{end_year}-12-31",
        "units":      "standard",
        "limit":      1000,
    }
    rows: list[dict] = []
    offset = 1
    while True:
        params = dict(params_base, offset=offset)
        if verbose:
            print(f"    GET {API}  {county_fips}  "
                  f"{start_year}\u2013{end_year}  offset={offset}")
        r = requests.get(API, headers=headers, params=params, timeout=60)
        if r.status_code == 429:
            print("    rate-limited (429); sleeping 5s then retrying")
            time.sleep(5)
            continue
        if not r.ok:
            print(f"    HTTP {r.status_code} \u2014 {r.text[:220]!r}")
            return rows
        try:
            payload = r.json()
        except ValueError:
            print(f"    non-JSON body: {r.text[:220]!r}")
            return rows
        results = payload.get("results") or []
        if not results:
            break
        rows.extend(results)
        total = (payload.get("metadata", {}).get("resultset", {}).get("count"))
        if total is not None and len(rows) >= total:
            break
        if len(results) < params_base["limit"]:
            break
        offset += len(results)
        time.sleep(sleep_s)
    return rows


def fetch_county_year_range(token: str, county_fips: str,
                            start_year: int, end_year: int,
                            verbose: bool = False,
                            sleep_s: float = 0.25) -> list[dict]:
    """Pull every GSOY record for one county, chunked by MAX_WINDOW_YEARS.

    NOAA's `/data` endpoint rejects start/end ranges longer than 10
    years with HTTP 400 ("date range must be less than 10 years"). We
    walk the full range in \u2264 10-year windows and concatenate results.
    Each window still paginates via `offset` if it exceeds 1 000 rows.
    """
    rows: list[dict] = []
    window_start = start_year
    while window_start <= end_year:
        # Window is INCLUSIVE; `window_start=1970, MAX=10` \u2192 1970\u20131979 (10 yrs).
        window_end = min(end_year, window_start + MAX_WINDOW_YEARS - 1)
        chunk = _fetch_one_window(token, county_fips,
                                  window_start, window_end,
                                  verbose=verbose, sleep_s=sleep_s)
        rows.extend(chunk)
        window_start = window_end + 1
        time.sleep(sleep_s)
    return rows


def aggregate(rows: list[dict]) -> dict[int, dict[str, float | int]]:
    """Collapse station-level annual summaries into per-year county means.

    Each row looks like:
        { "date": "1970-01-01T00:00:00",
          "datatype": "TAVG",
          "station": "GHCND:USC00090140",
          "value": 55.3 }   # because we asked for units=standard

    We average values across stations per (year, datatype). Returns
    per-year dicts keyed by datatype (TAVG \u2192 tavg_f, PRCP \u2192 prcp_in) plus
    a ``stations`` count so the frontend can flag thin data.
    """
    # year \u2192 datatype \u2192 [values]
    buckets: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    stations_per_year: dict[int, set[str]] = defaultdict(set)
    for row in rows:
        dt_raw = row.get("date") or ""
        try:
            year = int(dt_raw[:4])
        except ValueError:
            continue
        datatype = (row.get("datatype") or "").upper()
        if datatype not in DATATYPES:
            continue
        val = row.get("value")
        if val is None:
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue
        buckets[year][datatype].append(val)
        st = row.get("station")
        if st:
            stations_per_year[year].add(st)

    out: dict[int, dict[str, float | int]] = {}
    for year, by_dt in buckets.items():
        entry: dict[str, float | int] = {}
        if "TAVG" in by_dt and by_dt["TAVG"]:
            entry["tavg_f"] = round(mean(by_dt["TAVG"]), 1)
        if "PRCP" in by_dt and by_dt["PRCP"]:
            entry["prcp_in"] = round(mean(by_dt["PRCP"]), 1)
        entry["stations"] = len(stations_per_year[year])
        if entry:
            out[year] = entry
    return out


def compute_baseline(years_map: dict[int, dict[str, float | int]],
                     window: tuple[int, int]) -> dict[str, float]:
    """Average tavg/prcp across the baseline window (inclusive)."""
    lo, hi = window
    tavgs: list[float] = []
    prcps: list[float] = []
    for y in range(lo, hi + 1):
        e = years_map.get(y)
        if not e:
            continue
        if "tavg_f" in e:
            tavgs.append(float(e["tavg_f"]))
        if "prcp_in" in e:
            prcps.append(float(e["prcp_in"]))
    b: dict[str, float] = {}
    if tavgs:
        b["tavg_f"] = round(mean(tavgs), 1)
    if prcps:
        b["prcp_in"] = round(mean(prcps), 1)
    return b


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Pull NOAA GSOY observed annual temp/precip for DE counties.")
    ap.add_argument("--token", default=os.environ.get("NOAA_TOKEN", ""),
                    help="NOAA CDO API token. Falls back to $NOAA_TOKEN env var.")
    ap.add_argument("--start-year", type=int, default=DEFAULT_FIRST,
                    help=f"First year to pull (default {DEFAULT_FIRST}).")
    ap.add_argument("--end-year", type=int, default=DEFAULT_LAST,
                    help=f"Last year to pull (default {DEFAULT_LAST}).")
    ap.add_argument("--sleep", type=float, default=0.25,
                    help="Seconds between API calls (NOAA allows 5/sec).")
    ap.add_argument("--verbose", action="store_true",
                    help="Print each API call as it's issued.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Preview only; do not write the output file.")
    args = ap.parse_args()

    if not args.token:
        sys.exit("no NOAA token provided. Set $NOAA_TOKEN or pass --token. "
                 "Get one at https://www.ncdc.noaa.gov/cdo-web/token")

    if args.start_year > args.end_year:
        sys.exit(f"bad year range: {args.start_year}\u2013{args.end_year}")

    print(f"Fetching NOAA GSOY for DE: {args.start_year}\u2013{args.end_year}, "
          f"{len(DE_COUNTIES)} counties, {len(DATATYPES)} datatypes")

    county_years: dict[str, dict[int, dict[str, float | int]]] = {}
    for fips, cname in DE_COUNTIES.items():
        print(f"\n==> {fips} ({cname} County)")
        rows = fetch_county_year_range(
            args.token, fips, args.start_year, args.end_year,
            verbose=args.verbose, sleep_s=args.sleep)
        if not rows:
            print(f"  0 rows")
            county_years[fips] = {}
            continue
        per_year = aggregate(rows)
        print(f"  {len(rows)} station-year rows \u2192 "
              f"{len(per_year)} years with data "
              f"({min(per_year)}\u2013{max(per_year)})")
        county_years[fips] = per_year
        time.sleep(args.sleep)

    # Pivot to year-major shape (nested-county) for the frontend.
    year_out: dict[str, dict[str, dict]] = {}
    all_years: set[int] = set()
    for fips, per_year in county_years.items():
        all_years.update(per_year.keys())
    for y in sorted(all_years):
        bucket: dict[str, dict] = {}
        for fips in DE_COUNTIES:
            entry = county_years.get(fips, {}).get(y)
            if entry:
                bucket[fips] = entry
        if bucket:
            year_out[str(y)] = bucket

    # Per-county baseline normals for anomaly calculations on the frontend.
    baseline_values: dict[str, dict[str, float]] = {}
    for fips, per_year in county_years.items():
        baseline_values[fips] = compute_baseline(per_year, BASELINE)

    payload = {
        "_meta": {
            "source":         "NOAA GSOY via Climate Data Online v2",
            "dataset":        "Global Summary of the Year",
            "counties":       DE_COUNTIES,
            "years":          sorted(all_years),
            "units":          {"tavg": "F", "prcp": "inches"},
            "baseline":       list(BASELINE),
            "baseline_values": baseline_values,
            "retrieved_utc":  datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note":           "TAVG/PRCP means across all county stations "
                              "reporting that year. `stations` count flags "
                              "thin-data years.",
        },
        "years": year_out,
    }

    print(f"\n  {len(year_out)} total years with data")
    for fips, cname in DE_COUNTIES.items():
        b = baseline_values.get(fips, {})
        if b:
            print(f"  {fips} {cname:>10}: baseline 1991\u20132020 tavg="
                  f"{b.get('tavg_f','-')}\u00b0F, prcp={b.get('prcp_in','-')}in")

    if args.dry_run:
        print("\nDRY RUN \u2014 first year, first county sample:")
        if year_out:
            first_y = next(iter(year_out))
            print(f"  {first_y}: {year_out[first_y]}")
        return

    with open(OUT, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"\nWrote {OUT.name} ({OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
