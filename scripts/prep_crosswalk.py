#!/usr/bin/env python3
"""
prep_crosswalk.py — build scripts/bg10_to_bg20_DE.csv from a Census 2010→2020
relationship file.

fetch_ejscreen_history.py uses this CSV to crosswalk EJScreen 2015–2020 rows
(which are 2010 block-group GEOIDs) onto 2020 block-group GEOIDs. Without it,
those vintages are silently skipped and the pollution-burden panel stays
stuck at EJScreen 2021+.

The Census Bureau publishes two relevant relationship files for each state:

  - Block-level:       TAB2020_TAB2010_ST10_DE.txt   (pipe-delim, columns
                       STATE_2010 | COUNTY_2010 | TRACT_2010 | BLK_2010 |
                       ... | STATE_2020 | ... | BLK_2020 | AREALAND_INT | ...)
  - Block-group-level: may or may not exist for your state; columns would
                       include GEOID_BLKGRP_10, GEOID_BLKGRP_20, AREALAND_PART.

This script auto-detects which format you gave it. For the block-level file,
it aggregates blocks → block groups by taking the first digit of the block
code as the block-group number (Census convention: BG GEOID = state(2) +
county(3) + tract(6) + first-digit-of-block(1) = 12 chars).

Usage:
    # 1. Download the Delaware relationship file from the Census Bureau:
    #      https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.html
    # 2. Save the .txt as scripts/input_crosswalk_de.txt
    # 3. Run:
    python3 scripts/prep_crosswalk.py

Output:
    scripts/bg10_to_bg20_DE.csv with columns GEOID10, GEOID20, WEIGHT.

Weight is the fraction of each 2010 BG's land area that falls into each
2020 BG. Rows below 1% weight are pruned as noise.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "scripts" / "input_crosswalk_de.txt"
DST = ROOT / "scripts" / "bg10_to_bg20_DE.csv"


def pick(row: dict, *keys: str) -> str:
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return v
    return ""


def bg_geoid(state: str, county: str, tract: str, block: str) -> str:
    """Census convention: BG GEOID = 2-state + 3-county + 6-tract + 1-bg,
    where bg is the first digit of the 4-digit block code."""
    st = state.strip().zfill(2)
    co = county.strip().zfill(3)
    tr = tract.strip().zfill(6)
    bk = block.strip()
    if not bk:
        return ""
    return f"{st}{co}{tr}{bk[0]}"


def process_block_level(rdr: csv.DictReader) -> tuple[dict, dict, int]:
    """Aggregate block-level intersections up to block-group level.

    Returns (pair_area, bg10_area, rows_in) where:
      - pair_area[(bg10, bg20)] = summed AREALAND_INT
      - bg10_area[bg10]         = summed AREALAND_INT across all pairs
                                  (equals total 2010 BG land area because
                                  the intersections partition each block)
    """
    pair_area: dict[tuple[str, str], float] = defaultdict(float)
    bg10_area: dict[str, float] = defaultdict(float)
    rows_in = 0

    # Census varies column names across releases. Try the common spellings.
    STATE_10 = ("STATE_2010", "STATE10", "STATEFP_2010", "STATEFP10", "STATEFP")
    STATE_20 = ("STATE_2020", "STATE20", "STATEFP_2020", "STATEFP20", "STATEFP")
    COUNTY_10 = ("COUNTY_2010", "COUNTY10", "COUNTYFP_2010", "COUNTYFP10", "COUNTYFP")
    COUNTY_20 = ("COUNTY_2020", "COUNTY20", "COUNTYFP_2020", "COUNTYFP20", "COUNTYFP")
    TRACT_10 = ("TRACT_2010", "TRACT10", "TRACTCE_2010", "TRACTCE10", "TRACTCE")
    TRACT_20 = ("TRACT_2020", "TRACT20", "TRACTCE_2020", "TRACTCE20", "TRACTCE")
    BLK_10 = ("BLK_2010", "BLOCK_2010", "BLK10", "BLOCK10", "BLOCKCE_2010", "BLOCKCE10")
    BLK_20 = ("BLK_2020", "BLOCK_2020", "BLK20", "BLOCK20", "BLOCKCE_2020", "BLOCKCE20")
    AREA_COLS = ("AREALAND_INT", "AREALAND", "AREALAND_PART")

    bad_state = 0
    for r in rdr:
        rows_in += 1
        st10 = pick(r, *STATE_10)
        st20 = pick(r, *STATE_20)
        if not st10 or not st20:
            bad_state += 1
        bg10 = bg_geoid(st10, pick(r, *COUNTY_10),
                        pick(r, *TRACT_10), pick(r, *BLK_10))
        bg20 = bg_geoid(st20, pick(r, *COUNTY_20),
                        pick(r, *TRACT_20), pick(r, *BLK_20))
        if not bg10 or not bg20:
            continue
        try:
            intersect = float(pick(r, *AREA_COLS) or 0)
        except ValueError:
            continue
        if intersect <= 0:
            continue
        pair_area[(bg10, bg20)] += intersect
        bg10_area[bg10] += intersect
    if bad_state and bad_state > rows_in * 0.1:
        print(f"  WARNING: {bad_state}/{rows_in} rows had empty state "
              f"column -- check your relationship file's headers. Saw "
              f"{list(rdr.fieldnames or [])[:10]}")
    return pair_area, bg10_area, rows_in


def process_bg_level(rdr: csv.DictReader) -> tuple[dict, dict, int]:
    pair_area: dict[tuple[str, str], float] = defaultdict(float)
    bg10_area: dict[str, float] = defaultdict(float)
    rows_in = 0

    for r in rdr:
        rows_in += 1
        bg10 = pick(r, "GEOID_BLKGRP_10", "GEOID10_BLKGRP").strip()
        bg20 = pick(r, "GEOID_BLKGRP_20", "GEOID20_BLKGRP").strip()
        if not bg10 or not bg20:
            continue
        try:
            part = float(pick(r, "AREALAND_PART") or 0)
            whole = float(pick(r, "AREALAND_BLKGRP_10") or 0)
        except ValueError:
            continue
        if part <= 0 or whole <= 0:
            continue
        pair_area[(bg10, bg20)] = part
        # Use given whole (not summed) because the file is already aggregated.
        bg10_area[bg10] = whole
    return pair_area, bg10_area, rows_in


def main() -> None:
    if not SRC.exists():
        sys.exit(
            f"Input file not found: {SRC}\n"
            "Download Delaware's 2010→2020 relationship file from the Census\n"
            "Bureau (see module docstring) and save it to that path."
        )

    with SRC.open(encoding="utf-8-sig") as f:
        sample = f.read(8192)
        f.seek(0)
        delim = "|" if sample.count("|") > sample.count(",") else ","
        rdr = csv.DictReader(f, delimiter=delim)
        headers = rdr.fieldnames or []

        has_blk_10 = any(h in headers for h in ("BLK_2010", "BLOCK_2010", "BLK10", "BLOCK10"))
        has_blk_20 = any(h in headers for h in ("BLK_2020", "BLOCK_2020", "BLK20", "BLOCK20"))
        has_bg = any(h in headers for h in ("GEOID_BLKGRP_10", "GEOID10_BLKGRP"))
        if has_blk_10 and has_blk_20:
            print(f"Detected block-level relationship file (delim={delim!r})")
            print(f"  headers: {headers}")
            pair_area, bg10_area, rows_in = process_block_level(rdr)
        elif has_bg:
            print(f"Detected block-group-level relationship file (delim={delim!r})")
            print(f"  headers: {headers}")
            pair_area, bg10_area, rows_in = process_bg_level(rdr)
        else:
            sys.exit(
                f"Unrecognized file format. Columns: {headers!r}\n"
                "Expected either BLK_2010+BLK_2020 (block-level) or GEOID_BLKGRP_10\n"
                "(block-group-level)."
            )

    rows_out = 0
    with DST.open("w", newline="") as g:
        wtr = csv.writer(g)
        wtr.writerow(["GEOID10", "GEOID20", "WEIGHT"])
        for (bg10, bg20), area in sorted(pair_area.items()):
            denom = bg10_area.get(bg10, 0)
            if denom <= 0:
                continue
            w = area / denom
            if w < 0.01:
                continue
            wtr.writerow([bg10, bg20, f"{w:.4f}"])
            rows_out += 1

    print(
        f"Wrote {DST.relative_to(ROOT)}: {rows_out} BG→BG rows "
        f"(from {rows_in} input rows, {len(bg10_area)} unique 2010 BGs)"
    )


if __name__ == "__main__":
    main()
