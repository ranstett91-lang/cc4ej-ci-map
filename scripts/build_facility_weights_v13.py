#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026. See LICENSE.md.
"""build_facility_weights_v13.py — extends v1.1's TRI-derived weights with
per-category breakdowns for the multi-pollutant CIS variants (Tier 2.2).

Outputs (added to facility_weights.json by --patch):

    facility_weights.json {
      _meta: {... existing v1.1 _meta ...,
              schema_version: 2,
              category_weights_added: true,
              cancer_chemicals_seen: <count>,
              respiratory_chemicals_seen: <count>},
      weights: {
        "<trifid>": {
          ... v1.1 fields (weight, base_tier, multiplier, hap_flag, ...),
          weight_by_category: {
            combined:    <existing v1.1 weight>,
            cancer:      <weight × cancer_air_share>,
            respiratory: <weight × respiratory_air_share>
          },
          air_lbs_5yr_by_category: {combined, cancer, respiratory}
        }, ...
      }
    }

Allocation
----------
For each TRI-matched facility, sum the most-recent 5-year AIR releases
(stack + fugitive) per category from tri_chemical_history.json. Define:

    cancer_share      = cancer_air_lbs / max(combined_air_lbs, 1)
    respiratory_share = respiratory_air_lbs / max(combined_air_lbs, 1)

    weight_cancer       = weight_combined × cancer_share
    weight_respiratory  = weight_combined × respiratory_share

The combined weight (v1.1) is unchanged. Category weights ADD information,
they don't replace anything. A facility with zero cancer-relevant
emissions gets weight_cancer = 0 — i.e., it does NOT contribute to the
CIS_cancer surface. Documented in METHODOLOGY.md §7 as the
"category-share allocation" rule.

Facilities without TRI matches (Superfund-only, traffic, legacy) keep
weight_combined from the rubric and get weight_cancer / weight_respiratory
= None (the JS surfaces will exclude them; the combined surface still
includes them).

Usage
-----
    python3 scripts/build_facility_weights_v13.py            # dry-run
    python3 scripts/build_facility_weights_v13.py --patch    # write
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "scripts"))
from _chem_categories import categories_for_chem  # type: ignore


FAC_WEIGHTS = ROOT / "facility_weights.json"
FACILITIES = ROOT / "facilities.json"
TRI_CHEM = ROOT / "tri_chemical_history.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", action="store_true",
                    help="write category weights into facility_weights.json")
    ap.add_argument("--years", type=int, default=5,
                    help="recent year window for category emissions (default 5)")
    args = ap.parse_args()

    if not FAC_WEIGHTS.exists():
        print(f"ERROR: {FAC_WEIGHTS} not found — run "
              f"build_facility_weights.py first", file=sys.stderr)
        return 1
    if not TRI_CHEM.exists():
        print(f"ERROR: {TRI_CHEM} not found — run "
              f"fetch_tri_chemical_history.py first", file=sys.stderr)
        return 1

    fw = json.loads(FAC_WEIGHTS.read_text())
    chem_data = json.loads(TRI_CHEM.read_text())
    chemicals = chem_data["chemicals"]
    facilities = chem_data["facilities"]

    # Pre-classify every chemical so we don't recompute per-facility.
    chem_to_cats = {chem_id: categories_for_chem(meta)
                    for chem_id, meta in chemicals.items()}
    cancer_chems = {c for c, cats in chem_to_cats.items() if "cancer" in cats}
    resp_chems = {c for c, cats in chem_to_cats.items() if "respiratory" in cats}

    print(f"Classified {len(chemicals):,} TRI chemicals: "
          f"{len(cancer_chems):,} cancer-listed, "
          f"{len(resp_chems):,} respiratory-listed", file=sys.stderr)

    # For each TRI-matched facility in facility_weights, sum recent-N-year
    # AIR releases per category.
    matched = 0
    cancer_facilities = 0
    resp_facilities = 0
    for trifid, payload in fw["weights"].items():
        weight_combined = payload["weight"]
        years_history = facilities.get(trifid, {})
        if not years_history:
            payload["weight_by_category"] = {
                "combined": weight_combined,
                "cancer": None,
                "respiratory": None,
            }
            payload["air_lbs_5yr_by_category"] = {
                "combined": 0, "cancer": 0, "respiratory": 0,
            }
            continue

        # Pick the most recent N years actually present.
        recent_years = sorted(years_history.keys(), reverse=True)[:args.years]
        air_combined = 0.0
        air_cancer = 0.0
        air_respiratory = 0.0
        for y in recent_years:
            for chem_id, vals in years_history[y].items():
                lbs = float(vals.get("air_lbs") or 0)
                air_combined += lbs
                if chem_id in cancer_chems:
                    air_cancer += lbs
                if chem_id in resp_chems:
                    air_respiratory += lbs

        if air_combined > 0:
            cancer_share = air_cancer / air_combined
            resp_share = air_respiratory / air_combined
            weight_cancer = round(weight_combined * cancer_share, 3)
            weight_resp = round(weight_combined * resp_share, 3)
        else:
            weight_cancer = 0.0
            weight_resp = 0.0

        payload["weight_by_category"] = {
            "combined": weight_combined,
            "cancer": weight_cancer,
            "respiratory": weight_resp,
        }
        payload["air_lbs_5yr_by_category"] = {
            "combined": round(air_combined, 1),
            "cancer": round(air_cancer, 1),
            "respiratory": round(air_respiratory, 1),
        }
        matched += 1
        if weight_cancer > 0:
            cancer_facilities += 1
        if weight_resp > 0:
            resp_facilities += 1

    print(f"\nFacilities with TRI air-release history: {matched}")
    print(f"  → contribute to cancer surface:      {cancer_facilities}")
    print(f"  → contribute to respiratory surface: {resp_facilities}")

    # Top 10 by cancer + respiratory weight for sanity.
    rows = [(p.get("name"), p["weight_by_category"]) for p in fw["weights"].values()
            if p.get("weight_by_category")]
    rows_cancer = [(n, c["cancer"]) for n, c in rows if c.get("cancer")]
    rows_resp = [(n, c["respiratory"]) for n, c in rows if c.get("respiratory")]
    rows_cancer.sort(key=lambda t: -t[1])
    rows_resp.sort(key=lambda t: -t[1])
    print(f"\nTop 8 cancer-surface contributors:")
    for n, w in rows_cancer[:8]:
        print(f"  {n[:55]:55s}  weight_cancer = {w:.3f}")
    print(f"\nTop 8 respiratory-surface contributors:")
    for n, w in rows_resp[:8]:
        print(f"  {n[:55]:55s}  weight_respiratory = {w:.3f}")

    fw["_meta"]["schema_version"] = 2
    fw["_meta"]["category_weights_added"] = True
    fw["_meta"]["cancer_chemicals_seen"] = len(cancer_chems)
    fw["_meta"]["respiratory_chemicals_seen"] = len(resp_chems)
    fw["_meta"]["category_window_years"] = args.years
    fw["_meta"]["regenerated_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if not args.patch:
        print("\nDry-run only. Re-run with --patch to write facility_weights.json.")
        return 0

    FAC_WEIGHTS.write_text(json.dumps(fw, separators=(",", ":")))
    print(f"\nWrote category weights into {FAC_WEIGHTS.relative_to(ROOT)}")

    # Also patch facilities.json so the live site can read weight_by_category
    # directly per feature without a second fetch / merge step. The existing
    # `weight` field is unchanged — this only ADDS the category breakdown.
    fac_data = json.loads(FACILITIES.read_text())
    patched = 0
    for feat in fac_data["features"]:
        trifid = feat["properties"].get("trifid")
        if not trifid:
            # No TRI match — set explicit category weights so the JS can rely
            # on the field's presence: combined = the rubric weight, cancer
            # and respiratory = null (excluded from those surfaces).
            feat["properties"]["weight_by_category"] = {
                "combined": feat["properties"].get("weight"),
                "cancer": None,
                "respiratory": None,
            }
            continue
        wbc = fw["weights"].get(trifid, {}).get("weight_by_category")
        if wbc:
            feat["properties"]["weight_by_category"] = wbc
            patched += 1
    FACILITIES.write_text(json.dumps(fac_data, separators=(",", ":")))
    print(f"Patched {patched}/{len(fac_data['features'])} facilities.json features "
          f"with weight_by_category")
    return 0


if __name__ == "__main__":
    sys.exit(main())
