#!/usr/bin/env python3
"""
fetch_asthma_zip_history.py — build asthma_zip_history.json.

Pulls asthma ED-visit rates by Delaware geography and year. Three
supported paths, in order of preference:

  1. CSV from CDC EPHT Network Data Explorer (recommended).
     https://ephtracking.cdc.gov/DataExplorer/ — pick "Asthma →
     Emergency Department Visits", filter to Delaware, choose pediatric
     or all-ages, then "Export → CSV with data".
     This is the same backend DE DPH's My Healthy Community portal
     pulls from, but CDC's copy typically runs ~2 years ahead of
     what bubbles up to the state page (which caps at 2016 as of
     this writing).

  2. CSV from DE My Healthy Community (fallback, 2016 and earlier).
     https://myhealthycommunity.dhss.delaware.gov/ — "Asthma Emergency
     Department Visits", "Download data" button near the map.
     Use only if EPHT is unavailable for the years you need.

  3. CDC EPHT REST API (advanced, often flaky). The getCoreHolder
     endpoint path structure shifts; constants below are best-effort
     and may need updating. If rows come back empty, fall back to
     path 1.

Output shape:
    {
      "_meta": {
        "source":   "CDC EPHT Network (CSV export or API)",
        "indicator": "Asthma ED Visits",
        "units":    "age-adjusted rate per 10,000",
        "endpoint": "https://ephtracking.cdc.gov/...",
        "state":    "DE",
        "years":    [2014, 2015, ..., 2022],
        "retrieved_utc": "...",
        "note":     "ZIP or county rows. <6 events/yr suppressed upstream."
      },
      "zips": {
        "19703": { "years": {"2018": 142.3, "2019": 138.0, ...} },
        ...
      }
    }

The map joins these records to block groups by ZIP centroid (or
county FIPS when only county geography is available) at render time —
not perfect, but these are the finest geographies either portal
publishes for asthma indicators.

Usage:
    python3 scripts/fetch_asthma_zip_history.py --csv ~/Downloads/epht.csv
    python3 scripts/fetch_asthma_zip_history.py                  # try API
    python3 scripts/fetch_asthma_zip_history.py --dry-run

Expected CSV columns (case-insensitive, extras ignored):
    ZIP (or County / GEOID), Year, Rate (or "Age-adjusted Rate")

Requires: requests  (pip3 install requests)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests first")

OUT = Path(__file__).parent.parent / "asthma_zip_history.json"

# CDC EPHT Network API.
# Measure 296 = "Asthma ED Visits, Crude Rate per 10,000, Children (0-17)".
# Geography 44 = ZIP Code Tabulation Area (ZCTA).
# FIPS 10 = Delaware (state-level filter).
# Stratification 1 = single year (vs multi-year rolling avg).
#
# The API returns a JSON array of annual rate rows keyed by ZCTA.
# A few ZIPs are suppressed in some years (small numerator → unstable rate);
# those come back as null and we just skip them.
API = "https://ephtracking.cdc.gov/apigateway/api/v1/getCoreHolder"
MEASURE_ID   = 296
GEO_TYPE_ID  = 44      # ZCTA
STRAT_LEVEL  = 1       # annual
STATE_FIPS   = 10      # Delaware

# EPHT API often publishes a ~2-year lag (2024 data not out until 2026-ish).
# We'll ask for everything from 2010 forward and let the response tell us
# what's actually available.
FIRST_YEAR = 2010
LAST_YEAR  = datetime.now().year


def fetch_api() -> list[dict]:
    """Pull all available yearly ZIP rates for DE pediatric asthma ED visits.

    The EPHT getCoreHolder endpoint takes measure + geography + year
    filters as path segments. We request each year individually because
    asking for a multi-year range triggers server-side aggregation that
    we don't want.
    """
    out: list[dict] = []
    for yr in range(FIRST_YEAR, LAST_YEAR + 1):
        url = (f"{API}/{MEASURE_ID}/ALL/ALL/{STATE_FIPS}/"
               f"{yr}/{yr}/{GEO_TYPE_ID}/{STRAT_LEVEL}")
        print(f"  {yr}: {url}")
        try:
            r = requests.get(url, timeout=60)
        except requests.RequestException as e:
            print(f"    request error: {e}; skipping")
            continue
        if r.status_code != 200:
            print(f"    HTTP {r.status_code}; skipping")
            continue
        try:
            payload = r.json()
        except Exception as e:
            print(f"    JSON parse failed: {e}; skipping")
            continue
        # EPHT sometimes wraps rows under "tableResult"; sometimes returns
        # a bare array. Handle both.
        rows = payload.get("tableResult") if isinstance(payload, dict) else payload
        if not rows:
            print(f"    no rows (not yet published?)")
            continue
        for row in rows:
            out.append({
                "zip":  str(row.get("geoId") or row.get("geo_id") or "").strip(),
                "year": int(row.get("Year") or row.get("year") or yr),
                "rate": row.get("dataValue") or row.get("value"),
            })
        print(f"    {len(rows)} rows")
    return out


def read_csv(path: Path) -> list[dict]:
    """Fallback: parse a CSV the user downloaded from the DE portal."""
    rows: list[dict] = []
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        # Normalize headers so either "ZIP" / "zip" / "Zip Code" works.
        lut = {k.lower().strip(): k for k in reader.fieldnames or []}
        zip_k = lut.get("zip") or lut.get("zip code") or lut.get("zcta")
        year_k = lut.get("year")
        rate_k = (lut.get("rate")
                  or lut.get("age-adjusted rate")
                  or lut.get("crude rate"))
        if not (zip_k and year_k and rate_k):
            sys.exit(f"CSV missing required columns; got {list(lut)}")
        for r in reader:
            rows.append({
                "zip":  (r.get(zip_k) or "").strip(),
                "year": int((r.get(year_k) or "0").strip() or 0),
                "rate": r.get(rate_k),
            })
    return rows


def _to_float(v) -> float | None:
    if v is None or v == "" or str(v).strip().lower() in ("null", "suppressed", "*"):
        return None
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return None


def build(rows: list[dict]) -> dict:
    by_zip: dict[str, dict] = defaultdict(lambda: {"years": {}})
    year_set: set[int] = set()
    for r in rows:
        z = r["zip"]
        if not z or not z.isdigit() or len(z) != 5:
            continue
        # Delaware ZIPs start with 197, 198, or 199.
        if not z.startswith(("197", "198", "199")):
            continue
        rate = _to_float(r.get("rate"))
        if rate is None:
            continue
        yr = r.get("year") or 0
        if yr < 1990 or yr > 2100:
            continue
        by_zip[z]["years"][str(yr)] = rate
        year_set.add(yr)

    # Drop ZIPs with no usable years after filtering.
    by_zip = {k: v for k, v in by_zip.items() if v["years"]}

    return {
        "_meta": {
            "source":    "CDC EPHT Network API (DE pediatric asthma ED visits)",
            "indicator": "Asthma ED Visits, Children 0-17",
            "units":     "age-adjusted rate per 10,000",
            "endpoint":  API,
            "state":     "DE",
            "years":     sorted(year_set),
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note":      ("ZIP-level. Years with <6 events are suppressed by "
                          "EPHT and dropped here. Use with BG→ZIP centroid "
                          "lookup at render time — ZIP is the finest geography "
                          "DE DPH publishes for this indicator."),
        },
        "zips": by_zip,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--csv", type=Path,
                    help="Local CSV download from DE EPHT portal (fallback)")
    args = ap.parse_args()

    if args.csv:
        print(f"Reading CSV {args.csv}")
        rows = read_csv(args.csv)
    else:
        print(f"Fetching EPHT API {FIRST_YEAR}-{LAST_YEAR}...")
        rows = fetch_api()

    payload = build(rows)
    n_zip = len(payload["zips"])
    n_rows = sum(len(v["years"]) for v in payload["zips"].values())
    years = payload["_meta"]["years"]
    print(f"\n{n_zip} DE ZIPs, {n_rows} ZIP-year rows, "
          f"years {years[0] if years else '?'}–{years[-1] if years else '?'}")

    if args.dry_run:
        print("DRY RUN — not writing.")
        return

    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"Wrote {OUT.name}  ({OUT.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
