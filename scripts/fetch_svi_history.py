#!/usr/bin/env python3
"""
fetch_svi_history.py — build svi_tract_history.json from CDC SVI.

Pulls tract-level Social Vulnerability Index scores for Delaware from
every published SVI vintage (2000, 2010, 2014, 2016, 2018, 2020, 2022).
This is the cleanest way to extend the demographics story backward
before EJScreen existed — SVI uses ACS + decennial inputs that CDC
re-builds consistently vintage to vintage.

Output shape:
    {
      "_meta": {
        "source": "CDC/ATSDR Social Vulnerability Index",
        "endpoint": "https://svi.cdc.gov/Documents/Data/...",
        "state":    "DE",
        "themes":   {"RPL_THEME1": "Socioeconomic", ...},
        "years":    [2000, 2010, 2014, 2016, 2018, 2020, 2022],
        "retrieved_utc": "...",
        "note":     "Percentile rank within state. -999 = suppressed."
      },
      "tracts": {
        "10001040100": {
          "name": "Census Tract 401",
          "years": {
            "2020": {
              "overall": 0.82,
              "ses":     0.76,
              "hhd":     0.91,
              "minority": 0.70,
              "housing": 0.64
            }, ...
          }
        }, ...
      }
    }

Geographies: 2000/2010 SVI vintages are on 2010 tract boundaries;
2014-2022 are on 2010 tract boundaries for 2014/2016/2018 and 2020
tract boundaries for 2020/2022. At render we trim BG GEOIDs to 11
chars to look up tract scores — block-group boundaries are stable-ish
across 2010→2020 but the crosswalk script handles mismatches when
needed.

Usage:
    python3 scripts/fetch_svi_history.py                 # full pull
    python3 scripts/fetch_svi_history.py --dry-run
    python3 scripts/fetch_svi_history.py --years 2018,2020,2022

The SVI download URLs occasionally move when CDC re-organizes their
Documents/Data folder. If a year 404s, check
https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html
and update the URL in VINTAGES.

Requires: requests  (pip3 install requests)
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests first")

OUT = Path(__file__).parent.parent / "svi_tract_history.json"

# Per-vintage CSV download URLs. CDC hosts these under svi.cdc.gov with
# a consistent /Documents/Data/<year>/csv/states/ prefix since 2018;
# older vintages live in year-specific subpaths. The file name is always
# Delaware.csv (Initial caps) or DELAWARE.csv — we try both.
BASE = "https://svi.cdc.gov/Documents/Data"

VINTAGES: dict[int, list[str]] = {
    2000: [
        f"{BASE}/2000_SVI_Data/SVI2000_US.csv",
    ],
    2010: [
        f"{BASE}/2010_SVI_Data/CSV/Delaware.csv",
        f"{BASE}/2010_SVI_Data/CSV/DELAWARE.csv",
    ],
    2014: [
        f"{BASE}/2014_SVI_Data/CSV/States/Delaware.csv",
        f"{BASE}/2014_SVI_Data/CSV/DELAWARE.csv",
    ],
    2016: [
        f"{BASE}/2016_SVI_Data/CSV/States/Delaware.csv",
    ],
    2018: [
        f"{BASE}/2018_SVI_Data/CSV/States/Delaware.csv",
    ],
    2020: [
        f"{BASE}/2020/csv/states/Delaware.csv",
    ],
    2022: [
        f"{BASE}/2022/csv/states/Delaware.csv",
    ],
}

# SVI theme columns. CDC renamed these over the years:
#   2014+: RPL_THEME1..4 (percentile ranks), RPL_THEMES (overall)
#   2010:  R_PL_THEMES + R_PL_THEME1..4
#   2000:  USTP (overall percentile); themes not published separately
# We try both forms and use whichever exists.
COL_MAP = {
    "overall":  ["RPL_THEMES", "R_PL_THEMES", "USTP"],
    "ses":      ["RPL_THEME1", "R_PL_THEME1"],
    "hhd":      ["RPL_THEME2", "R_PL_THEME2"],  # Household composition/disability
    "minority": ["RPL_THEME3", "R_PL_THEME3"],
    "housing":  ["RPL_THEME4", "R_PL_THEME4"],
}
FIPS_COLS = ["FIPS", "FIPS_CODE", "GEOID10", "GEOID20", "GEOID"]
NAME_COLS = ["LOCATION", "NAME", "Location", "AREA_NAME"]
DE_FIPS = "10"


def _try_download(urls: list[str]) -> str | None:
    for url in urls:
        print(f"    GET {url}")
        try:
            r = requests.get(url, timeout=180)
        except requests.RequestException as e:
            print(f"      request error: {e}")
            continue
        if r.status_code == 200 and r.text.strip():
            return r.text
        print(f"      HTTP {r.status_code}")
    return None


def _pick(row: dict, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in row and row[c] not in (None, ""):
            return row[c]
        # Case-insensitive retry
        for k, v in row.items():
            if k.upper() == c.upper() and v not in (None, ""):
                return v
    return None


def _to_float(v):
    if v in (None, "", "-999", -999):
        return None
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return None


def parse_csv(text: str, year: int) -> dict[str, dict]:
    reader = csv.DictReader(io.StringIO(text))
    out: dict[str, dict] = {}
    for row in reader:
        fips = _pick(row, FIPS_COLS) or ""
        fips = str(fips).strip().zfill(11)
        if not fips.isdigit() or len(fips) < 11 or not fips.startswith(DE_FIPS):
            continue
        rec = {}
        for theme, cols in COL_MAP.items():
            val = _to_float(_pick(row, cols))
            if val is not None:
                rec[theme] = val
        if not rec:
            continue
        name = _pick(row, NAME_COLS) or ""
        out[fips] = {"name": str(name).strip(), **rec}
    return out


def build(years: list[int]) -> dict:
    by_tract: dict[str, dict] = {}
    year_set: set[int] = set()

    for year in sorted(years):
        urls = VINTAGES.get(year)
        if not urls:
            print(f"\n{year}: no URL configured; skipping")
            continue
        print(f"\nSVI {year}:")
        text = _try_download(urls)
        if not text:
            print(f"  all {len(urls)} URL(s) failed; skipping")
            continue
        snapshot = parse_csv(text, year)
        if not snapshot:
            print(f"  0 DE tracts parsed (column mapping miss?)")
            continue
        print(f"  {len(snapshot)} DE tracts")
        year_set.add(year)
        for fips, rec in snapshot.items():
            name = rec.pop("name", "")
            node = by_tract.setdefault(fips, {"name": name, "years": {}})
            if not node["name"] and name:
                node["name"] = name
            node["years"][str(year)] = rec

    return {
        "_meta": {
            "source":   "CDC/ATSDR Social Vulnerability Index (SVI)",
            "endpoint": BASE,
            "state":    "DE",
            "themes": {
                "overall":  "Overall vulnerability percentile (RPL_THEMES)",
                "ses":      "Socioeconomic status (Theme 1)",
                "hhd":      "Household composition & disability (Theme 2)",
                "minority": "Minority status & language (Theme 3)",
                "housing":  "Housing type & transportation (Theme 4)",
            },
            "years":    sorted(year_set),
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note":     ("Percentile rank 0-1 within state. -999 (CDC's suppression "
                         "sentinel) is converted to null and dropped. 2000 vintage "
                         "reports only the overall index — themes blank. 2000/2010 "
                         "use 2010 tract boundaries; 2014/2016/2018 use 2010 tracts; "
                         "2020/2022 use 2020 tracts."),
        },
        "tracts": by_tract,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--years", default="",
                    help="Comma-separated subset (default: all published vintages)")
    args = ap.parse_args()

    if args.years:
        years = [int(y) for y in args.years.split(",") if y.strip().isdigit()]
    else:
        years = sorted(VINTAGES)

    print(f"Fetching SVI for DE, vintages {years}")

    payload = build(years)
    n_tract = len(payload["tracts"])
    n_rows = sum(len(v["years"]) for v in payload["tracts"].values())
    print(f"\n{n_tract} DE tracts, {n_rows} tract-year rows")

    if args.dry_run:
        print("DRY RUN — not writing.")
        return

    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"Wrote {OUT.name}  ({OUT.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
