#!/usr/bin/env python3
"""
fetch_aqs_history.py — build aqs_monitors_history.json from EPA AQS.

Pulls daily summary readings from the EPA Air Quality System (AQS) for
Delaware monitors, 1999-present, for the pollutants that drive EJScreen's
air-quality indicators: PM2.5, ozone, NO2, SO2, diesel PM proxy (EC).

This is the fill-in for the 2004-2014 gap in the timeline. EJScreen
didn't exist pre-2015, but AQS monitors were measuring — so even though
we can't paint block groups with modeled percentiles that far back, we
CAN show station-level pollutant trends as a sparkline next to the
facility / air-quality controls.

Output shape:
    {
      "_meta": {
        "source":   "EPA AQS (Air Quality System)",
        "endpoint": "https://aqs.epa.gov/data/api/...",
        "state":    "DE (FIPS 10)",
        "params":   {"88101": "PM2.5", "44201": "Ozone", ...},
        "years":    [1999, ..., 2025],
        "retrieved_utc": "...",
        "note":     "Annual means per monitor. Raw daily summaries aggregated."
      },
      "monitors": {
        "10-001-0002-88101-1": {
          "site":  "Seaford",
          "lat":   38.64,
          "lon":   -75.61,
          "param": "PM2.5",
          "units": "Micrograms/cubic meter (LC)",
          "years": {
            "2010": { "mean": 10.3, "max": 37.1, "days_over": 4 },
            ...
          }
        }, ...
      }
    }

Usage:
    export AQS_EMAIL="you@example.com"
    export AQS_KEY="<key from https://aqs.epa.gov/aqsweb/documents/data_api.html#signup>"
    python3 scripts/fetch_aqs_history.py                 # full pull
    python3 scripts/fetch_aqs_history.py --dry-run
    python3 scripts/fetch_aqs_history.py --years 2004-2014

The AQS API requires free signup — one emailed GET to /signup/ and you
get a key immediately. Without credentials the script exits early with
instructions.

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

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests first")

OUT = Path(__file__).parent.parent / "aqs_monitors_history.json"

BASE = "https://aqs.epa.gov/data/api"
STATE_FIPS = "10"  # Delaware

# AQS parameter codes → human names. These are the core EJScreen air
# pollutants plus a couple regional drivers (NO2 from traffic, SO2 from
# Delaware City refinery).
PARAMS = {
    "88101": "PM2.5",          # FRM/FEM mass
    "88502": "PM2.5 (non-FRM)", # acceptable substitute where 88101 missing
    "44201": "Ozone",           # 8-hr
    "42101": "CO",
    "42401": "SO2",
    "42602": "NO2",
    "81102": "PM10",
}

# Exceedance thresholds (NAAQS / recognized health benchmarks) for the
# "days_over" counter. Units match AQS' default reporting units.
THRESHOLDS = {
    "88101": 35.0,   # 24-hr NAAQS µg/m3
    "88502": 35.0,
    "44201": 0.070,  # 8-hr NAAQS ppm
    "42101": 9.0,    # 8-hr NAAQS ppm
    "42401": 0.075,  # 1-hr NAAQS ppm
    "42602": 0.100,  # 1-hr NAAQS ppm
    "81102": 150.0,  # 24-hr NAAQS µg/m3
}

FIRST_YEAR = 1999
LAST_YEAR  = datetime.now().year - 1  # AQS is ~4-6 months behind realtime


def _creds() -> tuple[str, str]:
    email = os.environ.get("AQS_EMAIL", "").strip()
    key   = os.environ.get("AQS_KEY", "").strip()
    if not email or not key:
        sys.exit(
            "Set AQS_EMAIL and AQS_KEY env vars first.\n"
            "Free signup: curl 'https://aqs.epa.gov/data/api/signup?email=YOU@example.com'\n"
            "The key arrives by email in ~30 seconds.")
    return email, key


def fetch_year(email: str, key: str, param: str, year: int) -> list[dict]:
    """Pull daily summary rows for one param × year, statewide.

    dailyData/byState returns one row per monitor × day. That's
    reasonable volume for DE (thousands per year, not millions).
    """
    url = f"{BASE}/dailyData/byState"
    params = {
        "email":    email,
        "key":      key,
        "param":    param,
        "bdate":    f"{year}0101",
        "edate":    f"{year}1231",
        "state":    STATE_FIPS,
    }
    try:
        r = requests.get(url, params=params, timeout=120)
    except requests.RequestException as e:
        print(f"    request error: {e}; skipping")
        return []
    if r.status_code != 200:
        print(f"    HTTP {r.status_code}: {r.text[:160]!r}; skipping")
        return []
    try:
        payload = r.json()
    except Exception as e:
        print(f"    JSON parse failed: {e}; skipping")
        return []
    header = payload.get("Header", [{}])[0]
    status = header.get("status", "")
    if status and status.lower() != "success":
        print(f"    AQS status={status!r}: {header.get('error', [])}; skipping")
        return []
    return payload.get("Data") or []


def _monitor_id(row: dict) -> str:
    """Canonical monitor key: STATE-COUNTY-SITE-PARAM-POC."""
    return (f"{row.get('state_code','')}-{row.get('county_code','')}-"
            f"{row.get('site_number','')}-{row.get('parameter_code','')}-"
            f"{row.get('poc','')}")


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build(years: list[int]) -> dict:
    email, key = _creds()
    monitors: dict[str, dict] = {}
    # daily buffer per (monitor, year) for computing mean/max/exceedances
    buf: dict[tuple[str, int], list[float]] = defaultdict(list)
    year_set: set[int] = set()

    for param, label in PARAMS.items():
        thresh = THRESHOLDS.get(param)
        print(f"\nparam {param} ({label}):")
        for yr in years:
            print(f"  {yr}")
            rows = fetch_year(email, key, param, yr)
            if not rows:
                continue
            for r in rows:
                val = _to_float(r.get("arithmetic_mean"))  # daily mean
                if val is None:
                    continue
                mid = _monitor_id(r)
                if mid not in monitors:
                    monitors[mid] = {
                        "site":  (r.get("local_site_name") or
                                  r.get("site_address") or "").strip(),
                        "lat":   round(_to_float(r.get("latitude"))  or 0, 4) or None,
                        "lon":   round(_to_float(r.get("longitude")) or 0, 4) or None,
                        "param": label,
                        "param_code": param,
                        "units": (r.get("units_of_measure") or "").strip(),
                        "years": {},
                    }
                buf[(mid, yr)].append(val)
                year_set.add(yr)
            print(f"    {len(rows):,} daily rows")
            time.sleep(0.25)  # AQS asks for <10 req/sec; be polite

    # Aggregate daily buffer → annual stats.
    for (mid, yr), vals in buf.items():
        if not vals:
            continue
        t = THRESHOLDS.get(monitors[mid]["param_code"])
        over = sum(1 for v in vals if t is not None and v > t)
        monitors[mid]["years"][str(yr)] = {
            "mean": round(sum(vals) / len(vals), 3),
            "max":  round(max(vals), 3),
            "n":    len(vals),
            "days_over": over,
        }

    # Drop monitors that had zero usable years.
    monitors = {k: v for k, v in monitors.items() if v["years"]}

    return {
        "_meta": {
            "source":   "EPA AQS (Air Quality System) — dailyData/byState",
            "endpoint": f"{BASE}/dailyData/byState",
            "state":    f"DE (FIPS {STATE_FIPS})",
            "params":   PARAMS,
            "thresholds": THRESHOLDS,
            "years":    sorted(year_set),
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note":     ("Per-monitor annual stats aggregated from daily summaries. "
                         "days_over counts daily values above the listed NAAQS/benchmark "
                         "threshold. Use with monitor lat/lon — do not aggregate to "
                         "block groups (point measurements, not a surface)."),
        },
        "monitors": monitors,
    }


def _parse_years(arg: str) -> list[int]:
    if not arg:
        return list(range(FIRST_YEAR, LAST_YEAR + 1))
    if "-" in arg:
        a, b = arg.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(y) for y in arg.split(",") if y.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--years", default="",
                    help=f"Year range or list, e.g. 2004-2014 (default: {FIRST_YEAR}-{LAST_YEAR})")
    args = ap.parse_args()

    years = _parse_years(args.years)
    print(f"Fetching EPA AQS for DE, years {years[0]}–{years[-1]}")

    payload = build(years)
    n_mon = len(payload["monitors"])
    n_rows = sum(len(v["years"]) for v in payload["monitors"].values())
    print(f"\n{n_mon} DE monitors, {n_rows} monitor-year aggregates")

    if args.dry_run:
        print("DRY RUN — not writing.")
        return

    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"Wrote {OUT.name}  ({OUT.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
