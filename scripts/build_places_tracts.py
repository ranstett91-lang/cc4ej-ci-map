#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026 <YOUR NAME>. See LICENSE.md.
"""
build_places_tracts.py — build places_tracts.json side-car from CDC PLACES

Fetches census-tract health indicators for Delaware from the CDC PLACES
Socrata dataset (2025 release, `cwsq-ngmh`) and emits a compact side-car
JSON keyed by 11-char tract GEOID for use by the browser map.

The map looks up these values at popup time by taking the first 11
characters of a block group GEOID and joining to the tract record. This
keeps the pipeline agnostic of the main de_blockgroups.geojson — no
pipeline rebuild is required to surface observed health outcomes.

Usage:
    python3 scripts/build_places_tracts.py              # fetch + write
    python3 scripts/build_places_tracts.py --dry-run    # preview, no write

Requires: requests  (pip install requests)
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
    sys.exit("pip install requests first")


PLACES_URL = "https://chronicdata.cdc.gov/resource/cwsq-ngmh.json"
OUT = Path(__file__).parent.parent / "places_tracts.json"

MEASURES = [
    "CASTHMA",     # Current asthma (adults)
    "CANCER",      # Cancer (excluding skin cancer)
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
]


def fetch(state: str = "DE") -> list[dict]:
    """Fetch all census-tract measure rows for *state* from CDC PLACES."""
    rows: list[dict] = []
    offset = 0
    batch = 5000
    measure_clause = " OR ".join(f"measureid='{m}'" for m in MEASURES)
    where = f"stateabbr='{state}' AND length(locationname)=11 AND ({measure_clause})"
    while True:
        resp = requests.get(PLACES_URL, params={
            "$where":  where,
            "$select": "locationname,measureid,data_value,data_value_type,totalpopulation",
            "$limit":  batch,
            "$offset": offset,
        }, timeout=60)
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        rows.extend(page)
        print(f"  fetched {len(rows)} rows (offset={offset})...")
        if len(page) < batch:
            break
        offset += batch
    return rows


def pivot(rows: list[dict]) -> dict[str, dict]:
    """Reshape long-format rows to {tract_geoid: {measureid: value, ...}}."""
    out: dict[str, dict] = {}
    for row in rows:
        geoid = str(row.get("locationname", "")).strip()
        measure = row.get("measureid")
        raw = row.get("data_value")
        if not geoid or not measure or raw is None:
            continue
        try:
            val = round(float(raw), 1)
        except (TypeError, ValueError):
            continue
        tract = out.setdefault(geoid, {})
        tract[measure] = val
        pop = row.get("totalpopulation")
        if pop is not None and "pop" not in tract:
            try:
                tract["pop"] = int(pop)
            except (TypeError, ValueError):
                pass
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview; do not write places_tracts.json")
    args = parser.parse_args()

    print(f"Fetching CDC PLACES 2025 for Delaware ({len(MEASURES)} measures)")
    rows = fetch()
    tracts = pivot(rows)
    print(f"  {len(tracts)} tracts, {sum(len(v) for v in tracts.values())} values")

    payload = {
        "_meta": {
            "source":        "CDC PLACES, Census Tract Data 2025 release",
            "socrata_id":    "cwsq-ngmh",
            "endpoint":      PLACES_URL,
            "state":         "DE",
            "measures":      MEASURES,
            "unit":          "Crude prevalence, percent of adults 18+",
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note":          "Observed prevalence at census tract level. "
                             "Joined to block groups by 11-char GEOID prefix.",
        },
        "tracts": tracts,
    }

    if args.dry_run:
        print("\nDRY RUN — first 2 tracts:")
        for geoid, vals in list(tracts.items())[:2]:
            print(f"  {geoid}: {vals}")
        return

    with open(OUT, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"\nWrote {OUT.name}")


if __name__ == "__main__":
    main()
