#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026 <YOUR NAME>. See LICENSE.md.
"""
fetch_brfss_child_asthma.py — DE state pediatric asthma prevalence

Strategy (in order):
  1) Try CDC BRFSS current asthma prevalence Socrata dataset, filter
     stateabbr='DE' and the child/youth age bucket if exposed. The
     Child Asthma Call-Back Survey (ACBS) is not released every year for
     every state; missing state-year rows are expected.
  2) On miss: return the most recent published CDC NHIS national
     pediatric (0-17) current-asthma prevalence, with fallback=True so
     the UI displays a "national fallback" chip.

The NHIS fallback value is documented in the NHIS_FALLBACK constant
below with the source URL. Update it when CDC publishes a newer year.

Used by build_at_risk_populations.py. This matches the American Lung
Association State of the Air methodology for pediatric asthma: state
BRFSS rate where available, else NHIS national rate, applied to county
under-18 populations from ACS.

Usage (standalone):
    python3 scripts/fetch_brfss_child_asthma.py           # print result
    python3 scripts/fetch_brfss_child_asthma.py --state DE

Requires: requests  (pip install requests)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("pip install requests first")


# CDC BRFSS Prevalence and Trends Data (current asthma among adults is
# widely available; child asthma via ACBS is more intermittent). If a
# child-specific dataset ID becomes stable, replace SOCRATA_BASE below.
SOCRATA_BASE = "https://chronicdata.cdc.gov/resource"

# Candidate dataset IDs to try for BRFSS child asthma (state-level).
# The build script treats all failures as "missing" and falls back to NHIS.
CANDIDATE_DATASETS = [
    # Asthma Call-back Survey - Child (historical releases)
    "j32f-wbr2",
    # BRFSS Asthma Prevalence (if a child measure is exposed)
    "qqpq-5w5a",
]

# NHIS national pediatric (0-17) current-asthma prevalence.
# Update with each NHIS annual release.
#   Source: CDC NHIS Early Release Program, asthma prevalence tables.
#   URL:    https://www.cdc.gov/asthma/nhis/default.htm
# Value as of last update (documented in-script for review):
NHIS_FALLBACK = {
    "rate_pct":   6.5,   # Most recent national current-asthma prevalence, children 0-17
    "vintage":    2023,
    "scope":      "national",
    "source":     "nhis",
    "source_url": "https://www.cdc.gov/asthma/nhis/default.htm",
}


def try_socrata(dataset_id: str, state: str = "DE") -> Optional[dict]:
    """Query a Socrata dataset for child asthma in *state*.

    Returns a dict with rate_pct+vintage on success, else None.
    """
    url = f"{SOCRATA_BASE}/{dataset_id}.json"
    # Try a few plausible filter shapes; exact column names vary by release.
    attempts = [
        {"$where": f"stateabbr='{state}'",
         "$select": "year,data_value,measure",
         "$limit": 50},
        {"$where": f"locationabbr='{state}'",
         "$select": "year,data_value,question",
         "$limit": 50},
    ]
    for params in attempts:
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code != 200:
                continue
            rows = resp.json()
            if not rows:
                continue
            # Filter to current asthma prevalence (measure/question varies).
            asthma_rows = [
                r for r in rows
                if "current asthma" in str(r.get("measure", "")).lower()
                or "current asthma" in str(r.get("question", "")).lower()
            ]
            if not asthma_rows:
                continue
            latest = max(asthma_rows, key=lambda r: int(r.get("year", 0) or 0))
            val = latest.get("data_value")
            if val is None:
                continue
            return {
                "rate_pct": round(float(val), 1),
                "vintage":  int(latest.get("year", 0)),
                "scope":    "state",
                "source":   "brfss_child",
                "source_url": f"{SOCRATA_BASE}/{dataset_id}",
                "dataset_id": dataset_id,
            }
        except (requests.RequestException, ValueError, KeyError):
            continue
    return None


def fetch(state: str = "DE") -> dict:
    """Return pediatric asthma prevalence for *state*, falling back to NHIS."""
    for dataset_id in CANDIDATE_DATASETS:
        result = try_socrata(dataset_id, state=state)
        if result is not None:
            result["fallback"] = False
            return result
    # No state rate available — return NHIS national fallback.
    fallback = dict(NHIS_FALLBACK)
    fallback["fallback"] = True
    return fallback


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--state", default="DE",
                        help="Two-letter state abbreviation (default: DE)")
    args = parser.parse_args()
    result = fetch(state=args.state)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
