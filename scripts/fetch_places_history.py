#!/usr/bin/env python3
"""
fetch_places_history.py — build places_tract_history.json from CDC PLACES.

Pulls tract-level health prevalence estimates for Delaware across every
annual PLACES release (2019 through 2024). Each release uses a different
Socrata dataset ID on chronicdata.cdc.gov, so we hit them one at a time
and stitch the results into a per-tract year-over-year series.

Output shape:
    {
      "_meta": {
        "source":  "CDC PLACES (Local Data for Better Health)",
        "endpoint": "https://chronicdata.cdc.gov/resource/<id>.json",
        "state":    "DE",
        "measures": ["CASTHMA", "COPD", ...],
        "unit":     "Crude prevalence %, adults 18+",
        "years":    [2019, 2020, ..., 2024],
        "retrieved_utc": "...",
        "note":     "BRFSS-modeled tract prevalence. Join to BGs by 11-char GEOID prefix."
      },
      "tracts": {
        "10001040100": {
          "years": {
            "2024": {"CASTHMA": 9.8, "COPD": 5.7, ...},
            "2023": {...}
          }
        }, ...
      }
    }

The map joins these to block groups by trimming the last char of the BG
GEOID — tract = BG[:11] — so the pipeline stays agnostic of DE's BG file.

Usage:
    python3 scripts/fetch_places_history.py              # full pull
    python3 scripts/fetch_places_history.py --dry-run
    python3 scripts/fetch_places_history.py --years 2022,2023,2024

Requires: requests  (pip3 install requests)

Dataset IDs: each PLACES annual release is a new Socrata dataset. If a
year below 404s, look up the current ID at chronicdata.cdc.gov
(search "PLACES Census Tract Data <year> release") and update VINTAGES.
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

OUT = Path(__file__).parent.parent / "places_tract_history.json"

# Year → Socrata dataset ID on chronicdata.cdc.gov.
# Release year ≈ BRFSS year + 2 (release N covers BRFSS up to year N-2).
# Update these if a year starts 404'ing — IDs are stable per release but
# occasionally CDC re-publishes with a new slug.
VINTAGES: dict[int, str] = {
    2024: "cwsq-ngmh",   # BRFSS 2022 + 2021
    2023: "yjkw-uj5s",   # BRFSS 2021 + 2020
    2022: "duw2-7jbt",   # BRFSS 2020 + 2019
    2021: "373s-598d",   # BRFSS 2019 + 2018
    2020: "4ai3-zynv",   # BRFSS 2018 + 2017
    2019: "cwsq-ngmh-2019",  # placeholder; first PLACES release was 2020 calendar
}

MEASURES = [
    "CASTHMA",     # Current asthma, adults
    "CANCER",      # Cancer excluding skin
    "CHD",         # Coronary heart disease
    "COPD",        # Chronic obstructive pulmonary disease
    "STROKE",      # Stroke
    "DEPRESSION",  # Depression
    "BPHIGH",      # High blood pressure
    "DIABETES",    # Diagnosed diabetes
    "KIDNEY",      # Chronic kidney disease
    "OBESITY",     # Obesity
    "CSMOKING",    # Current smoking
    "MHLTH",       # Mental health not good ≥14 days
    "PHLTH",       # Physical health not good ≥14 days
    "LPA",         # No leisure-time physical activity
]

BASE = "https://chronicdata.cdc.gov/resource"


def fetch_year(year: int, dataset_id: str, state: str = "DE") -> list[dict]:
    """Fetch all tract measure rows for *year* from the given Socrata dataset.

    Different vintages spell their columns differently (measureid vs
    MeasureId; locationname vs LocationName), so we select * and let the
    pivot step normalize case.
    """
    url = f"{BASE}/{dataset_id}.json"
    rows: list[dict] = []
    offset = 0
    step = 5000
    measure_clause = " OR ".join(f"upper(measureid)='{m}'" for m in MEASURES)
    where = (f"upper(stateabbr)='{state}' AND length(locationname)=11 "
             f"AND ({measure_clause})")
    print(f"  {year}: {url}")
    while True:
        try:
            r = requests.get(url, params={
                "$where":  where,
                "$limit":  step,
                "$offset": offset,
            }, timeout=120)
        except requests.RequestException as e:
            print(f"    request error: {e}; treating as empty")
            return rows
        if r.status_code == 404:
            print(f"    404 — dataset ID may be stale; skipping")
            return rows
        if r.status_code != 200:
            print(f"    HTTP {r.status_code}: {r.text[:160]!r}; skipping")
            return rows
        try:
            page = r.json()
        except Exception as e:
            print(f"    JSON parse failed: {e}; skipping")
            return rows
        if not page:
            break
        rows.extend(page)
        print(f"    {len(rows):,} rows")
        if len(page) < step:
            break
        offset += step
        time.sleep(0.25)  # be polite to Socrata
    return rows


def _lower(d: dict) -> dict:
    """Normalize dict keys to lowercase — Socrata varies case between datasets."""
    return {k.lower(): v for k, v in d.items()}


def pivot(rows: list[dict]) -> dict[str, dict[str, float]]:
    """Reshape long-format rows to {tract_geoid: {measure: value, ...}}."""
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        r = _lower(row)
        geoid = str(r.get("locationname") or r.get("tractfips") or "").strip()
        measure = str(r.get("measureid") or "").strip().upper()
        raw = r.get("data_value")
        if len(geoid) != 11 or not geoid.isdigit() or not measure or raw is None:
            continue
        if measure not in MEASURES:
            continue
        try:
            out[geoid][measure] = round(float(raw), 1)
        except (TypeError, ValueError):
            continue
    return dict(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--years", default="",
                    help="Comma-separated subset of release years (default: all)")
    args = ap.parse_args()

    want = None
    if args.years.strip():
        want = {int(y) for y in args.years.split(",") if y.strip().isdigit()}

    by_tract: dict[str, dict] = defaultdict(lambda: {"years": {}})
    years_ok: list[int] = []

    for year in sorted(VINTAGES):
        if want is not None and year not in want:
            continue
        ds_id = VINTAGES[year]
        rows = fetch_year(year, ds_id)
        if not rows:
            print(f"    no rows for {year}; skipping")
            continue
        snapshot = pivot(rows)
        if not snapshot:
            print(f"    0 usable tracts for {year}; skipping")
            continue
        for geoid, vals in snapshot.items():
            by_tract[geoid]["years"][str(year)] = vals
        years_ok.append(year)
        print(f"  {year}: {len(snapshot):,} DE tracts")

    n_tract = len(by_tract)
    n_rows = sum(len(v["years"]) for v in by_tract.values())
    print(f"\n{n_tract} DE tracts, {n_rows} tract-year snapshots, "
          f"years {years_ok}")

    payload = {
        "_meta": {
            "source":   "CDC PLACES (Local Data for Better Health)",
            "endpoint": f"{BASE}/<socrata_id>.json",
            "vintages": {str(y): VINTAGES[y] for y in years_ok},
            "state":    "DE",
            "measures": MEASURES,
            "unit":     "Crude prevalence %, adults 18+",
            "years":    years_ok,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note":     ("BRFSS-modeled tract prevalence. Join to block groups "
                         "by 11-char GEOID prefix at render time. Each release "
                         "aggregates the prior two BRFSS cycles, so year-over-year "
                         "changes are smoothed (consecutive releases share ~50% "
                         "of their BRFSS source years)."),
        },
        "tracts": dict(by_tract),
    }

    if args.dry_run:
        print("DRY RUN — not writing.")
        return

    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"Wrote {OUT.name}  ({OUT.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
