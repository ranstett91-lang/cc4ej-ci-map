#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026. See LICENSE.md.
"""audit_cis_sensitivity.py — sensitivity analysis for the Facility Burden
Index (CIS) decay-exponent choice.

Purpose
-------
The production CIS uses an inverse-distance-weighting (IDW) decay exponent
of 1.5 (CIS_DECAY in index.html). Common defensible choices in EJ proximity
literature are 1.0, 1.5, and 2.0; lower values weight regional dispersion
heavily and higher values emphasize hyper-local proximity. Whether the
headline result depends on this choice is testable and important to disclose.

This script recomputes the no-wind CIS at every Delaware block-group centroid
under decay ∈ {1.0, 1.25, 1.5, 1.75, 2.0} and reports Spearman rank
correlation between each variant and the production decay (1.5). Output is a
markdown table suitable for pasting into METHODOLOGY.md §8.

Math here mirrors index.html's rawProximityCIS() exactly:
    score = Σ_facilities (weight / max(distance_mi, CIS_MIN_MI)^decay)

The "haversine returns miles" convention from the JS is preserved (units
cancel in a rank comparison).

Usage
-----
    python3 scripts/audit_cis_sensitivity.py            # print to stdout
    python3 scripts/audit_cis_sensitivity.py --write    # also write
                                                          # METHODOLOGY.md §8 in place
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Shared CIS math/stats helpers — single source of truth for haversine,
# centroid, raw_proximity_cis, and spearman_rho across all CIS scripts.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cis_stats import feature_centroid, raw_proximity_cis, spearman_rho

ROOT = Path(__file__).resolve().parent.parent
FAC = ROOT / "facilities.json"
BG = ROOT / "de_blockgroups.geojson"
METHODOLOGY = ROOT / "METHODOLOGY.md"

CIS_MIN_MI = 0.15
DECAYS = [1.0, 1.25, 1.5, 1.75, 2.0]
PRODUCTION_DECAY = 1.5


def render_table(rho_by_decay: dict[float, float]) -> str:
    rows = ["| Decay | Spearman ρ vs production (1.5) | Interpretation |",
            "| --- | --- | --- |"]
    interp = {
        1.0: "Regional-dispersion emphasis",
        1.25: "Mild regional emphasis",
        1.5: "Production parameter",
        1.75: "Mild local emphasis",
        2.0: "Hyper-local emphasis",
    }
    for d in DECAYS:
        rho = rho_by_decay[d]
        if d == PRODUCTION_DECAY:
            rows.append(f"| **{d}** | **1.000** (production) | {interp[d]} |")
        else:
            rows.append(f"| {d} | {rho:.3f} | {interp[d]} |")
    return "\n".join(rows)


def render_summary(rho_by_decay: dict[float, float], n_bgs: int) -> str:
    min_rho = min(rho for d, rho in rho_by_decay.items() if d != PRODUCTION_DECAY)
    if min_rho >= 0.95:
        verdict = (
            f"\n**Result:** all variant decays show ρ ≥ {min_rho:.3f} against the "
            f"production decay (1.5) across {n_bgs} Delaware block-group centroids. "
            f"The rank-order of burdened communities is **robust** to the choice of "
            f"decay within the standard IDW range; the headline result does not "
            f"depend on the parameter choice."
        )
    else:
        verdict = (
            f"\n**Result:** at least one decay variant shows ρ = {min_rho:.3f} "
            f"(< 0.95) against the production decay (1.5) across {n_bgs} block-group "
            f"centroids. The rank-order of burdened communities is **sensitive** to "
            f"the decay choice; this should be disclosed in the limitations section."
        )
    return verdict


def update_methodology(table: str, summary: str) -> bool:
    """Replace the §8 placeholder table in METHODOLOGY.md with the computed one."""
    text = METHODOLOGY.read_text()
    start_marker = "| Decay | Spearman ρ vs production (1.5) | Interpretation |"
    end_marker = "**Interpretation rule:**"
    si = text.find(start_marker)
    ei = text.find(end_marker)
    if si == -1 or ei == -1 or ei < si:
        print("Could not locate §8 markers in METHODOLOGY.md", file=sys.stderr)
        return False
    new = text[:si] + table + "\n\n" + summary + "\n\n" + text[ei:]
    METHODOLOGY.write_text(new)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="overwrite METHODOLOGY.md §8 with computed table")
    args = ap.parse_args()

    facilities = json.loads(FAC.read_text())["features"]
    bgs = json.loads(BG.read_text())["features"]
    print(f"Computing CIS at {len(bgs)} BG centroids × {len(DECAYS)} decay variants "
          f"(facilities: {len(facilities)})...", file=sys.stderr)

    centroids = [feature_centroid(f["geometry"]) for f in bgs]

    scores_by_decay: dict[float, list[float]] = {}
    for d in DECAYS:
        scores = [raw_proximity_cis(lat, lng, facilities, decay=d, min_mi=CIS_MIN_MI)
                  for (lat, lng) in centroids]
        scores_by_decay[d] = scores

    production = scores_by_decay[PRODUCTION_DECAY]
    rho_by_decay = {d: spearman_rho(production, scores_by_decay[d]) for d in DECAYS}

    table = render_table(rho_by_decay)
    summary = render_summary(rho_by_decay, len(bgs))

    print(table)
    print(summary)

    if args.write:
        if update_methodology(table, summary):
            print(f"\nUpdated {METHODOLOGY.relative_to(ROOT)} §8.", file=sys.stderr)
        else:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
