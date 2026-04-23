#!/usr/bin/env python3
"""
audit_history.py -- sanity-check de_blockgroups_history.json.

Reports, per year:
  - GEOID row count
  - % of GEOIDs present in the live 2020 BG baseline (de_blockgroups.geojson)
  - sample of a few "stranger" GEOIDs (not in baseline) for visual inspection

Flags:
  - LOW ROWS      : row count < ROW_FLOOR (likely under-populated)
  - VINTAGE SKEW  : coverage < COVERAGE_FLOOR (likely a 2010-GEOID year
                    masquerading as 2020, i.e. crosswalk was skipped)
  - EMPTY         : 0 rows -- should be deleted from the JSON

No file writes; read-only diagnostic.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
HIST_FILE = ROOT / "de_blockgroups_history.json"
BG_FILE = ROOT / "de_blockgroups.geojson"

ROW_FLOOR = 500        # DE has ~571 BGs (2010) / ~706 BGs (2020)
COVERAGE_FLOOR = 70.0  # % of year's GEOIDs that must match the 2020 baseline


def main() -> None:
    if not HIST_FILE.exists():
        print(f"missing {HIST_FILE}")
        return
    if not BG_FILE.exists():
        print(f"missing {BG_FILE} -- can't check vintage coverage")
        return

    hist = json.loads(HIST_FILE.read_text())
    bg = json.loads(BG_FILE.read_text())
    baseline = {
        (f["properties"].get("GEOID") or f["properties"].get("geoid") or "")
        for f in bg.get("features", [])
    }
    baseline.discard("")
    print(f"Baseline (de_blockgroups.geojson): {len(baseline)} GEOIDs\n")

    header = f"{'Year':<6} {'Rows':>6} {'In baseline':>13} {'Coverage':>10}  Flags"
    print(header)
    print("-" * len(header))

    for year in sorted(hist.keys()):
        rows = hist[year]
        n = len(rows)
        if n == 0:
            print(f"{year:<6} {n:>6} {'':>13} {'':>10}  EMPTY")
            continue
        hits = sum(1 for g in rows if g in baseline)
        pct = 100 * hits / n
        flags = []
        if n < ROW_FLOOR:
            flags.append(f"LOW ROWS ({n}<{ROW_FLOOR})")
        if pct < COVERAGE_FLOOR:
            flags.append(f"VINTAGE SKEW ({pct:.0f}%<{COVERAGE_FLOOR:.0f}%)")
        flag_str = ", ".join(flags) if flags else "ok"
        print(f"{year:<6} {n:>6} {hits:>7}/{n:<5} {pct:>9.0f}%  {flag_str}")

        if flags:
            strangers = [g for g in list(rows)[:30] if g not in baseline][:5]
            if strangers:
                print(f"       sample GEOIDs not in baseline: {strangers}")


if __name__ == "__main__":
    main()
