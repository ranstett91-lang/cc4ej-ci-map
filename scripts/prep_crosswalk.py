#!/usr/bin/env python3
"""
prep_crosswalk.py — convert a Census 2010→2020 block-group relationship file
to the CSV format fetch_ejscreen_history.py expects.

fetch_ejscreen_history.py crosswalks EJScreen 2015–2020 (2010 GEOIDs) into
2020 GEOIDs. Without this crosswalk, those vintages are silently skipped and
the pollution-burden panel stays stuck at EJScreen 2021+. Run this once
to unlock the 2015–2020 years.

Usage:
    # 1. Download the Delaware 2010→2020 block-group relationship file from
    #    the Census Bureau landing page:
    #      https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.html
    #    Under "2020 Census → 2010 Census → Block Group", pick Delaware
    #    (state FIPS 10). Save it as:
    #      scripts/input_crosswalk_de.txt
    # 2. Run:
    python3 scripts/prep_crosswalk.py

Output:
    scripts/bg10_to_bg20_DE.csv with columns GEOID10, GEOID20, WEIGHT.

Weight is AREALAND_PART / AREALAND_BLKGRP_10 — the fraction of each 2010 BG
that falls into each 2020 BG. Rows below 1% weight are pruned as noise.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "scripts" / "input_crosswalk_de.txt"
DST = ROOT / "scripts" / "bg10_to_bg20_DE.csv"


def pick(row: dict, *keys: str) -> str:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return ""


def main() -> None:
    if not SRC.exists():
        sys.exit(
            f"Input file not found: {SRC}\n"
            "Download Delaware's 2010→2020 block-group relationship file from the\n"
            "Census Bureau (see module docstring) and save it to that path."
        )

    with SRC.open() as f:
        sample = f.read(8192)
        f.seek(0)
        delim = "|" if sample.count("|") > sample.count(",") else ","
        rdr = csv.DictReader(f, delimiter=delim)

        rows_in = 0
        rows_out = 0
        with DST.open("w", newline="") as g:
            wtr = csv.writer(g)
            wtr.writerow(["GEOID10", "GEOID20", "WEIGHT"])

            for r in rdr:
                rows_in += 1
                g10 = pick(r, "GEOID_BLKGRP_10", "GEOID10_BLKGRP", "BLKGRP_GEOID_10").strip()
                g20 = pick(r, "GEOID_BLKGRP_20", "GEOID20_BLKGRP", "BLKGRP_GEOID_20").strip()
                if not g10 or not g20:
                    continue
                try:
                    part = float(pick(r, "AREALAND_PART", "AREA_PART") or 0)
                    whole = float(pick(r, "AREALAND_BLKGRP_10", "AREALAND_10") or 0)
                except ValueError:
                    continue
                if whole <= 0:
                    continue
                w = part / whole
                if w < 0.01:
                    continue
                wtr.writerow([g10, g20, f"{w:.4f}"])
                rows_out += 1

    print(f"Wrote {DST.relative_to(ROOT)}: {rows_out} rows (from {rows_in} input)")


if __name__ == "__main__":
    main()
