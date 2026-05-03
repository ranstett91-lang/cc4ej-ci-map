#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026 <YOUR NAME>. See LICENSE.md.
"""
fetch_sota_at_risk.py — read hand-transcribed SOTA DE county tables

The American Lung Association's "State of the Air" city-rankings pages are
JavaScript-rendered with an unstable layout, so a web scraper would be brittle.
SOTA releases annually; hand-transcribing 3 DE counties into a committed CSV
is faster to audit via `git diff` and the values are citation-sensitive.

This reader parses scripts/sota_de_<year>.csv and returns a dict keyed by
5-digit county FIPS, with a shape consumable by build_at_risk_populations.py.
Blank cells become `None`; downstream composes them with source="pending".

Usage (standalone):
    python3 scripts/fetch_sota_at_risk.py               # print parsed rows
    python3 scripts/fetch_sota_at_risk.py --year 2025
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


HERE = Path(__file__).parent


def _num(val: str) -> float | int | None:
    """Parse a cell to int/float/None; blank → None."""
    if val is None:
        return None
    s = val.strip()
    if not s:
        return None
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return None


def _grade(val: str) -> str | None:
    s = (val or "").strip().upper()
    return s if s in {"A", "B", "C", "D", "F", "PASS", "FAIL", "INC"} else None


def read(year: int = 2025) -> dict[str, dict]:
    """Return {fips5: sota_record} for all Delaware counties in the CSV."""
    path = HERE / f"sota_de_{year}.csv"
    if not path.exists():
        sys.exit(f"Missing {path}. Transcribe the SOTA {year} report into this CSV.")

    out: dict[str, dict] = {}
    expected_cols = {
        "fips", "name", "ozone_grade", "ozone_days",
        "pm25_daily_grade", "pm25_daily_days",
        "pm25_annual_status", "pm25_annual_value",
        "pediatric_asthma", "adult_asthma_pct", "copd_pct", "cvd_pct",
        "lung_cancer", "poverty", "people_of_color",
    }

    with path.open() as f:
        reader = csv.DictReader(r for r in f if not r.lstrip().startswith("#"))
        missing = expected_cols - set(reader.fieldnames or [])
        if missing:
            sys.exit(f"{path} is missing columns: {sorted(missing)}")
        for row in reader:
            fips = (row.get("fips") or "").strip()
            if not fips:
                continue
            out[fips] = {
                "name":               row["name"].strip(),
                "ozone_grade":        _grade(row["ozone_grade"]),
                "ozone_days":         _num(row["ozone_days"]),
                "pm25_daily_grade":   _grade(row["pm25_daily_grade"]),
                "pm25_daily_days":    _num(row["pm25_daily_days"]),
                "pm25_annual_status": _grade(row["pm25_annual_status"]),
                "pm25_annual_value":  _num(row["pm25_annual_value"]),
                "pediatric_asthma":   _num(row["pediatric_asthma"]),
                "adult_asthma_pct":   _num(row["adult_asthma_pct"]),
                "copd_pct":           _num(row["copd_pct"]),
                "cvd_pct":            _num(row["cvd_pct"]),
                "lung_cancer":        _num(row["lung_cancer"]),
                "poverty":            _num(row["poverty"]),
                "people_of_color":    _num(row["people_of_color"]),
                "vintage":            year,
            }

    if len(out) != 3:
        sys.exit(f"Expected 3 DE counties in {path}, found {len(out)}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--year", type=int, default=2025,
                        help="SOTA report year (default 2025)")
    args = parser.parse_args()
    print(json.dumps(read(args.year), indent=2))


if __name__ == "__main__":
    main()
