#!/usr/bin/env python3
"""
build_places_history.py — build places_tracts_history.json from CDC PLACES.

Fetches tract-level adult health prevalence estimates for Delaware across
every annual PLACES release we can reach, writes a year-major side-car
the timeline-scrub panel can nearest-year-match against.

Output shape (year-major so the frontend can reuse nearestYearWithData):

    {
      "_meta": {
        "source":   "CDC PLACES (Local Data for Better Health)",
        "state":    "DE",
        "measures": ["CASTHMA", "COPD", ...],
        "unit":     "Crude prevalence %, adults 18+",
        "years":    [2020, 2021, 2022, 2023, 2024, 2025],
        "vintages": {"2020": "4ai3-zynv", ...},
        "retrieved_utc": "...",
        "note":     "Keyed by Socrata release year. BRFSS reference year \u2248 release - 2."
      },
      "years": {
        "2025": { "10003014502": {"CASTHMA": 11.3, "CHD": 6.1, ...}, ... },
        "2024": { ... },
        ...
      }
    }

Join to a block group by taking the first 11 chars of its GEOID:
    tract = BG_GEOID[:11]

Usage:
    python3 scripts/build_places_history.py                 # full pull
    python3 scripts/build_places_history.py --dry-run       # preview, no write
    python3 scripts/build_places_history.py --years 2022,2023,2024
    python3 scripts/build_places_history.py --id 2023=yjkw-uj5s  # override

Requires: requests  (pip3 install requests)

Notes
-----
- Sandbox cannot reach chronicdata.cdc.gov \u2014 run this locally.
- Each PLACES release is a distinct Socrata dataset. IDs below are best
  known at write time; if any 404 check https://chronicdata.cdc.gov
  (search "PLACES Census Tract Data <year> release") and pass --id to
  override.
- Column case drifts across releases (measureid vs MeasureId, locationname
  vs LocationName); we lowercase every key on read.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests first")


OUT = Path(__file__).parent.parent / "places_tracts_history.json"

# Release year -> Socrata dataset ID on chronicdata.cdc.gov.
# Release year N roughly covers BRFSS years N-2 and N-3.
# Verified 2026-04-22 against the chronicdata catalog API \u2014 the
# long-format "Local Data for Better Health, Census Tract Data YYYY release"
# family (NOT the GIS-friendly wide-format variants, which have different
# schemas).
VINTAGES: dict[int, str] = {
    2025: "cwsq-ngmh",   # BRFSS 2022 + 2021 \u2014 current
    2024: "ai6z-tcin",   # BRFSS 2021 + 2020
    2023: "em5e-5hvn",   # BRFSS 2020 + 2019
    2022: "nw2y-v4gm",   # BRFSS 2019 + 2018
    2021: "373s-ayzu",   # BRFSS 2018 + 2017
    2020: "4ai3-zynv",   # BRFSS 2017 + 2016 (first PLACES annual release)
}

# Measure IDs consumed by renderHealthSection in index.html. Extra measures
# are harmless \u2014 the frontend only renders the ones it knows.
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
    "MHLTH",       # Mental health not good \u226514 days
    "PHLTH",       # Physical health not good \u226514 days
]

BASE = "https://chronicdata.cdc.gov/resource"


def _lower_keys(row: dict) -> dict:
    """Socrata case drifts across releases; flatten to lowercase once."""
    return {k.lower(): v for k, v in row.items()}


def fetch_year(year: int, dataset_id: str, state: str = "DE") -> list[dict]:
    """Fetch tract-level measure rows for *year*.

    We filter to:
      - stateabbr == DE
      - length(locationname) == 11  (census-tract GEOID, not county)
      - measureid in our MEASURES list

    Paginates in 5000-row pages; stops when a page is short.
    """
    url = f"{BASE}/{dataset_id}.json"
    measure_clause = " OR ".join(f"upper(measureid)='{m}'" for m in MEASURES)
    where = (f"upper(stateabbr)='{state}' AND length(locationname)=11 "
             f"AND ({measure_clause})")
    rows: list[dict] = []
    offset = 0
    step = 5000
    print(f"  {year} ({dataset_id}): {url}")
    while True:
        try:
            r = requests.get(url, params={
                "$where":  where,
                "$limit":  step,
                "$offset": offset,
            }, timeout=120)
        except requests.RequestException as e:
            print(f"    request error: {e}; stopping this year")
            return []
        if r.status_code == 404:
            print(f"    404 \u2014 dataset id may be stale; skipping {year}")
            return []
        if not r.ok:
            print(f"    {r.status_code} \u2014 {r.text[:140]!r}; stopping this year")
            return []
        page = r.json()
        if not page:
            break
        rows.extend(_lower_keys(row) for row in page)
        print(f"    fetched {len(rows)} rows (offset={offset})")
        if len(page) < step:
            break
        offset += step
    return rows


def pivot(rows: list[dict]) -> dict[str, dict]:
    """Long-format rows \u2192 {tract_geoid: {MEASURE: value_rounded_1dp, ...}}."""
    out: dict[str, dict] = {}
    for row in rows:
        geoid = str(row.get("locationname") or "").strip()
        measure = str(row.get("measureid") or "").upper()
        raw = row.get("data_value")
        if len(geoid) != 11 or not measure or raw is None:
            continue
        try:
            val = round(float(raw), 1)
        except (TypeError, ValueError):
            continue
        out.setdefault(geoid, {})[measure] = val
        # Stash totalpopulation once per tract when present (handy for the
        # 'tract at least N people' sanity checks in the UI).
        pop = row.get("totalpopulation")
        if pop is not None and "pop" not in out[geoid]:
            try:
                out[geoid]["pop"] = int(pop)
            except (TypeError, ValueError):
                pass
    return out


def parse_overrides(pairs: list[str]) -> dict[int, str]:
    """--id 2023=yjkw-uj5s --id 2022=abcd-1234 \u2192 {2023: 'yjkw-uj5s', ...}."""
    out: dict[int, str] = {}
    for p in pairs or []:
        if "=" not in p:
            sys.exit(f"bad --id value {p!r}; expected YEAR=DATASET_ID")
        y, v = p.split("=", 1)
        out[int(y.strip())] = v.strip()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build places_tracts_history.json from CDC PLACES."
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="Preview; do not write places_tracts_history.json")
    ap.add_argument("--years", default="",
                    help="Comma-separated release years to fetch "
                         "(default: all in VINTAGES)")
    ap.add_argument("--id", action="append", metavar="YEAR=DATASET_ID",
                    help="Override Socrata dataset id for a year; repeatable")
    args = ap.parse_args()

    overrides = parse_overrides(args.id)
    vintages = dict(VINTAGES, **overrides)
    if args.years.strip():
        wanted = {int(y) for y in args.years.split(",")}
        vintages = {y: d for y, d in vintages.items() if y in wanted}
    if not vintages:
        sys.exit("no release years selected; check --years/--id")

    print(f"Fetching CDC PLACES Delaware across "
          f"{sorted(vintages)} ({len(MEASURES)} measures)")

    years_out: dict[str, dict] = {}
    for year in sorted(vintages):
        rows = fetch_year(year, vintages[year])
        if not rows:
            print(f"  {year}: 0 rows; skipping")
            continue
        tracts = pivot(rows)
        print(f"  {year}: {len(tracts)} tracts, "
              f"{sum(len(v) for v in tracts.values())} values")
        if tracts:
            years_out[str(year)] = tracts

    if not years_out:
        sys.exit("no data fetched \u2014 every vintage empty; check dataset IDs")

    payload = {
        "_meta": {
            "source":   "CDC PLACES (Local Data for Better Health)",
            "state":    "DE",
            "measures": MEASURES,
            "unit":     "Crude prevalence, percent of adults 18+",
            "years":    sorted(int(y) for y in years_out.keys()),
            "vintages": {str(y): vintages[y] for y in sorted(vintages)
                         if str(y) in years_out},
            "retrieved_utc":
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note":     "Keyed by Socrata release year. BRFSS reference year "
                        "\u2248 release - 2. Join to BGs by 11-char GEOID prefix.",
        },
        "years": years_out,
    }

    if args.dry_run:
        print("\nDRY RUN \u2014 summary:")
        for y in sorted(years_out, key=int):
            sample_geoid, sample_vals = next(iter(years_out[y].items()))
            print(f"  {y}: {len(years_out[y])} tracts; "
                  f"sample {sample_geoid}={sample_vals}")
        return

    with open(OUT, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"\nWrote {OUT.name} ({OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
