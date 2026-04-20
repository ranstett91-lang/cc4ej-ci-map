#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026 <YOUR NAME>. See LICENSE.md.
"""
seed_history_from_baseline.py \u2014 generate a 2023 stub for the time-slider.

The real history file is populated by fetch_ejscreen_history.py (needs
internet to reach EPA gaftp). This helper extracts the current baseline
scores from de_blockgroups.geojson and writes a minimal history file with
just the "2023" key so the slider wiring works end-to-end before the full
fetch is run.

Usage:
    python3 scripts/seed_history_from_baseline.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "de_blockgroups.geojson"
OUT = ROOT / "de_blockgroups_history.json"

FIELDS = [
    "eb", "sv",
    "p_pm25", "p_ozone", "p_dslpm", "p_cancer", "p_resp",
    "p_ptraf", "p_pnpl", "p_ptsdf", "p_prmp", "p_pwdis",
    "lowinc_pct", "unemp_pct", "lingiso_pct", "edu_nohsdip_pct",
    "under5_pct", "over64_pct", "poc_pct",
]


def main() -> None:
    gj = json.loads(SRC.read_text())
    year_record: dict[str, dict] = {}
    for feat in gj["features"]:
        p = feat["properties"]
        geoid = str(p.get("GEOID", "")).zfill(12)
        year_record[geoid] = {k: p[k] for k in FIELDS if k in p and p[k] is not None}

    out = {"2023": year_record}
    if OUT.exists():
        existing = json.loads(OUT.read_text())
        existing["2023"] = year_record
        out = existing

    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"Wrote {OUT.name}: {len(year_record)} GEOIDs at 2023")


if __name__ == "__main__":
    main()
