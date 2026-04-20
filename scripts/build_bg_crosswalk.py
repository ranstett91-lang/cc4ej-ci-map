#!/usr/bin/env python3
"""
build_bg_crosswalk.py — emit scripts/bg10_to_bg20_DE.csv

Downloads the Census 2020 block-group relationship file
(tab20_blkgrp20_blkgrp10_natl.txt), filters to Delaware
(state FIPS 10), and writes a small CSV mapping each
2010-vintage GEOID to its 2020-vintage overlap(s) with an
area-based weight.

fetch_ejscreen_history.py picks this up automatically when it
sees the file at scripts/bg10_to_bg20_DE.csv — without it, the
2016-2020 EJScreen vintages (which use 2010 BG boundaries) get
skipped entirely and the slider stays blank through those years.

Output schema:
    GEOID10,GEOID20,WEIGHT

Usage:
    python3 scripts/build_bg_crosswalk.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests first")

SRC_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/rel2020/blkgrp/"
    "tab20_blkgrp20_blkgrp10_natl.txt"
)
DE_FIPS = "10"
OUT = Path(__file__).parent / "bg10_to_bg20_DE.csv"


def main() -> None:
    print(f"Downloading {SRC_URL} ...")
    r = requests.get(SRC_URL, timeout=300, stream=True)
    r.raise_for_status()

    reader = csv.DictReader(
        (line.decode("utf-8", "replace") for line in r.iter_lines() if line),
        delimiter="|",
    )

    # Totals per 2010 BG so we can normalize weights ourselves even if
    # Census' AREALAND_PART totals are slightly shy of AREALAND_BLKGRP_10.
    by_g10: dict[str, list[tuple[str, float]]] = defaultdict(list)
    kept = 0
    for row in reader:
        g20 = row.get("GEOID_BLKGRP_20", "").strip()
        g10 = row.get("GEOID_BLKGRP_10", "").strip()
        if not g10 or not g20:
            continue
        if not g10.startswith(DE_FIPS) and not g20.startswith(DE_FIPS):
            continue
        try:
            land_part = float(row.get("AREALAND_PART") or 0)
        except ValueError:
            land_part = 0.0
        by_g10[g10].append((g20, land_part))
        kept += 1

    print(f"  {kept:,} DE relationship rows; {len(by_g10):,} distinct 2010 BGs")

    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["GEOID10", "GEOID20", "WEIGHT"])
        for g10, parts in by_g10.items():
            total = sum(a for _, a in parts) or 1.0
            for g20, a in parts:
                w.writerow([g10, g20, round(a / total, 6)])

    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
