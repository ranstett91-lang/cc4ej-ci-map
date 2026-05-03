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
  - AIR LEAK      : pre-2016 year with ANY non-null EJScreen air field or
                    non-null eb. Catches the baseline-bleed-through failure
                    where a build script forgot to null-stub p_* fields.
  - DEMO GAP      : lowinc_pct coverage < DEMO_FLOOR% of the year's rows.
                    Catches crosswalk allocation failures that leave most
                    records demographic-empty.
  - LINGISO EXPECTED NULL : pre-1990 year with non-null lingiso_pct. The
                    "limited-English-speaking household" concept was
                    introduced in 1990 STF3; earlier values can't be
                    comparably synthesized.

No file writes; read-only diagnostic.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
HIST_FILE = ROOT / "de_blockgroups_history.json"
BG_FILE = ROOT / "de_blockgroups.geojson"

ROW_FLOOR_DEFAULT = 500    # DE has ~571 BGs (2010) / ~706 BGs (2020)
ROW_FLOOR_PRE1990 = 400    # Pre-1990 decennials were tract-based; allocation
                            # to 706 2020 BGs may leave more gaps than post-2000.
COVERAGE_FLOOR = 70.0       # % of year's GEOIDs that must match 2020 baseline
DEMO_FLOOR = 90.0           # % of rows that must carry lowinc_pct non-null

EJSCREEN_AIR_FIELDS = (
    "p_pm25", "p_ozone", "p_dslpm", "p_cancer", "p_resp",
    "p_ptraf", "p_pnpl", "p_ptsdf", "p_prmp", "p_pwdis", "eb",
)


def _row_floor(year: int) -> int:
    return ROW_FLOOR_PRE1990 if year < 1990 else ROW_FLOOR_DEFAULT


def _air_leak(rows: dict[str, dict]) -> list[str]:
    """Return sample GEOIDs where an EJScreen air field is non-null. Only
    meaningful when called on pre-2016 year records."""
    offenders: list[str] = []
    for g, rec in rows.items():
        for f in EJSCREEN_AIR_FIELDS:
            if rec.get(f) is not None:
                offenders.append(f"{g}({f}={rec.get(f)})")
                break
        if len(offenders) >= 3:
            break
    return offenders


def _demo_coverage(rows: dict[str, dict]) -> float:
    """Fraction of rows with non-null lowinc_pct, expressed 0-100."""
    if not rows:
        return 0.0
    hits = sum(1 for r in rows.values() if r.get("lowinc_pct") is not None)
    return 100.0 * hits / len(rows)


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

    for year_str in sorted(hist.keys(), key=lambda s: int(s) if s.isdigit() else -1):
        rows = hist[year_str]
        # Skip non-year top-level keys like '_meta' if they ever appear.
        if not year_str.isdigit():
            continue
        year = int(year_str)
        n = len(rows)
        if n == 0:
            print(f"{year_str:<6} {n:>6} {'':>13} {'':>10}  EMPTY")
            continue
        hits = sum(1 for g in rows if g in baseline)
        pct = 100 * hits / n
        flags: list[str] = []
        floor = _row_floor(year)
        if n < floor:
            flags.append(f"LOW ROWS ({n}<{floor})")
        if pct < COVERAGE_FLOOR:
            flags.append(f"VINTAGE SKEW ({pct:.0f}%<{COVERAGE_FLOOR:.0f}%)")
        if year < 2016:
            leaks = _air_leak(rows)
            if leaks:
                flags.append(f"AIR LEAK ({leaks[0]}…)")
            if year <= 1989 and any(
                r.get("lingiso_pct") is not None for r in rows.values()
            ):
                flags.append("LINGISO EXPECTED NULL (1990+ only)")
        demo_pct = _demo_coverage(rows)
        if demo_pct < DEMO_FLOOR:
            flags.append(f"DEMO GAP ({demo_pct:.0f}%<{DEMO_FLOOR:.0f}%)")
        flag_str = ", ".join(flags) if flags else "ok"
        print(f"{year_str:<6} {n:>6} {hits:>7}/{n:<5} {pct:>9.0f}%  {flag_str}")

        if flags:
            strangers = [g for g in list(rows)[:30] if g not in baseline][:5]
            if strangers:
                print(f"       sample GEOIDs not in baseline: {strangers}")


if __name__ == "__main__":
    main()
