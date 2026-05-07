#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026. See LICENSE.md.
"""fetch_epa_aqs_monitors.py — pull EPA AQS annual concentration data for
Delaware monitors over a multi-year window.

Output
------
    air_monitors.json — {
        _meta: { source, endpoint, state, parameters, years,
                 retrieved_utc, n_monitors, n_records },
        parameters: { "<param_code>": { name, units, ... } },
        monitors: [ {
            site_id: "10-001-0002",
            lat: 39.123, lng: -75.456,
            site_name: "...",
            county: "...",
            annual_means: { "<param_code>": { "<year>": <mean_conc>, ... } },
            multi_year_mean: { "<param_code>": <mean across all years> }
        }, ... ]
    }

Source
------
EPA AirData pre-generated annual files (no auth required, public CSV):
    https://aqs.epa.gov/aqsweb/airdata/annual_conc_by_monitor_{YYYY}.zip
~4 MB compressed per year. Contains every monitor in the US; we filter to
state_code='10' (Delaware).

Why pre-gen files vs the AQS API: the API requires per-account email key
and has a low daily quota (the public test@aqs.api/test credential is
typically rate-limited). Pre-gen files are reliable and reproducible.

Parameters fetched (criteria pollutants relevant to facility burden):
    88101  PM2.5 - Local Conditions
    42602  Nitrogen dioxide (NO2)
    44201  Ozone
    42401  Sulfur dioxide
    42101  Carbon monoxide

Usage
-----
    python3 scripts/fetch_epa_aqs_monitors.py
    python3 scripts/fetch_epa_aqs_monitors.py --years 2018-2024
    python3 scripts/fetch_epa_aqs_monitors.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "air_monitors.json"

DE_STATE_CODE = "10"
DEFAULT_YEARS = list(range(2018, 2025))
PARAMETERS = {
    "88101": {"name": "PM2.5 (local conditions)", "units": "μg/m³"},
    "42602": {"name": "Nitrogen dioxide (NO2)", "units": "ppb"},
    "44201": {"name": "Ozone (O3)", "units": "ppm"},
    "42401": {"name": "Sulfur dioxide (SO2)", "units": "ppb"},
    "42101": {"name": "Carbon monoxide (CO)", "units": "ppm"},
}


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


def fetch_year(year: int) -> list[dict]:
    """Download annual_conc_by_monitor_{year}.zip and return DE rows only.

    The CSV inside the zip has 56 columns; we keep just the ones we use,
    discarding the rest at parse time to keep memory footprint small.
    """
    url = (f"https://aqs.epa.gov/aqsweb/airdata/"
           f"annual_conc_by_monitor_{year}.zip")
    req = Request(url, headers={"User-Agent": "cc4ej-ci-map/1.0"})
    with urlopen(req, timeout=180) as resp:
        blob = resp.read()
    rows = []
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        # 2018/2019/2024 zips have the CSV at the root; 2020-2023 nest it
        # inside a directory. Filter to *.csv non-directory entries so both
        # layouts work without per-year branching.
        csv_names = [n for n in zf.namelist()
                     if n.lower().endswith(".csv") and not n.endswith("/")]
        if not csv_names:
            return rows
        with zf.open(csv_names[0]) as fh:
            reader = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8"))
            for row in reader:
                if row.get("State Code") != DE_STATE_CODE:
                    continue
                pcode = row.get("Parameter Code")
                if pcode not in PARAMETERS:
                    continue
                rows.append(row)
    return rows


def site_id(row: dict) -> str:
    return f"{row['State Code']}-{row['County Code']}-{row['Site Num']}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="", help="e.g. 2018-2024")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    years = parse_years(args.years)
    print(f"Fetching EPA AirData annual concentrations for DE, years "
          f"{years[0]}-{years[-1]} ({len(years)} files × ~4 MB)",
          file=sys.stderr)

    # monitor[site_id] -> dict of metadata + annual_means
    monitors: dict[str, dict] = {}
    for year in years:
        try:
            rows = fetch_year(year)
        except Exception as ex:
            print(f"  {year}: fetch failed ({ex})", file=sys.stderr)
            continue
        # For each row, the CSV has multiple summaries (Daily Max / 1st Max /
        # Arithmetic Mean / etc.). Use Arithmetic Mean only for averaging.
        # For ozone, the annual fourth-highest daily max is more
        # health-relevant, but Arithmetic Mean is the simplest comparable
        # value across pollutants. We document this caveat in the analysis.
        for row in rows:
            metric = row.get("Metric Used", "")
            poc = row.get("POC")
            # POC=1 is the primary measurement (multiple monitors at one
            # site distinguish via POC). Restrict to POC=1 to avoid double-
            # counting co-located measurements.
            if poc != "1":
                continue
            sid = site_id(row)
            mon = monitors.setdefault(sid, {
                "site_id": sid,
                "lat": float(row.get("Latitude", 0) or 0),
                "lng": float(row.get("Longitude", 0) or 0),
                "site_name": (row.get("Local Site Name") or row.get("Address")
                              or sid),
                "county": row.get("County Name") or "",
                "city": row.get("City Name") or "",
                "annual_means": defaultdict(dict),
            })
            try:
                val = float(row.get("Arithmetic Mean", "") or "nan")
            except ValueError:
                continue
            pcode = row["Parameter Code"]
            mon["annual_means"][pcode][str(year)] = round(val, 4)
        print(f"  {year}: parsed {len(rows):,} DE rows", file=sys.stderr)

    # Compute multi-year mean per (monitor, parameter).
    for mon in monitors.values():
        multi = {}
        for pcode, ymap in mon["annual_means"].items():
            vals = [v for v in ymap.values() if v is not None]
            if vals:
                multi[pcode] = round(sum(vals) / len(vals), 4)
        mon["multi_year_mean"] = multi
        # Convert defaultdict to plain dict for JSON serialization.
        mon["annual_means"] = {k: dict(v) for k, v in mon["annual_means"].items()}

    payload = {
        "_meta": {
            "source": "EPA AirData annual_conc_by_monitor pre-generated files",
            "endpoint": ("https://aqs.epa.gov/aqsweb/airdata/"
                         "annual_conc_by_monitor_{year}.zip"),
            "state": "DE",
            "state_code": DE_STATE_CODE,
            "years": years,
            "parameters": PARAMETERS,
            "metric_used": "Arithmetic Mean (POC=1 only)",
            "n_monitors": len(monitors),
            "n_records": sum(len(m["annual_means"]) for m in monitors.values()),
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note": (
                "Annual arithmetic means are simpler to compare across pollutants "
                "than the parameter-specific health benchmarks (e.g. ozone 4th-"
                "highest 8-hour mean, NO2 98th percentile). For correlating with "
                "facility burden, the year-averaged mean is sufficient — we don't "
                "need NAAQS exceedance counts."
            ),
        },
        "monitors": list(monitors.values()),
    }

    print(f"\nMonitors found: {len(monitors)}")
    by_county = defaultdict(int)
    for m in monitors.values():
        by_county[m["county"]] += 1
    for county, n in sorted(by_county.items(), key=lambda t: -t[1]):
        print(f"  {county:20s}: {n}")

    print(f"\nMulti-year mean coverage by parameter:")
    coverage = defaultdict(int)
    for m in monitors.values():
        for p in m.get("multi_year_mean", {}):
            coverage[p] += 1
    for pcode, n in sorted(coverage.items(), key=lambda t: -t[1]):
        print(f"  {PARAMETERS[pcode]['name']:35s}: {n} monitors")

    if args.dry_run:
        print("\nDry-run only.")
        return 0

    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"\nWrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
