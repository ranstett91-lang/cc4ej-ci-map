#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026. See LICENSE.md.
"""patch_facility_weight_tier.py — add `weight_tier` and `weight_basis` fields
to every feature in facilities.json. Backs the v1.0 weighting rubric documented
at weighting_rubric.md.

What it does
------------
For each facility, this script computes:

  * weight_tier   — closest rubric tier (one of 3.0, 2.5, 2.0, 1.8, 1.5, 1.2)
                    derived from the existing numeric `weight` value
  * weight_basis  — short citation string composed from existing `source`,
                    `type`, `trifid`, and `note` fields, plus an
                    inferred regulatory-class hint (Superfund / Title V /
                    refinery / CAFO / chemical / etc.)

Numeric `weight` values are NOT modified. This step is a documentation
backfill — it makes the existing weights auditable. Tier 2.1 of the
methodology roadmap will replace these weights with TRI-derived composites.

Pattern follows scripts/apply_tri_crosswalk.py: --dry-run by default,
--apply to write. Re-runnable / idempotent.

Usage
-----
    python3 scripts/patch_facility_weight_tier.py            # dry-run preview
    python3 scripts/patch_facility_weight_tier.py --apply    # write facilities.json
    python3 scripts/patch_facility_weight_tier.py --csv      # also write
                                                              # facility_weight_tiers.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# Shared CIS math/stats helpers — single source of truth.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cis_stats import spearman_rho

ROOT = Path(__file__).resolve().parent.parent
FAC = ROOT / "facilities.json"
CSV_OUT = ROOT / "facility_weight_tiers.csv"

# Rubric tier centers, descending. See weighting_rubric.md.
TIERS = [3.0, 2.5, 2.0, 1.8, 1.5, 1.2]


def snap_to_tier(w: float) -> float:
    """Return the nearest rubric tier center for a numeric weight."""
    return min(TIERS, key=lambda t: abs(t - w))


def infer_regulatory_class(props: dict) -> str:
    """Heuristic regulatory-class label from existing type/source/note text.

    Conservative: when the public record doesn't clearly support a label,
    returns "preliminary inference" so reviewers know to verify.
    """
    type_s = (props.get("type") or "").lower()
    source = (props.get("source") or "").lower()
    note = (props.get("note") or "").lower()
    blob = f"{type_s} {source} {note}"

    # Order matters — most-specific first.
    if "superfund" in blob or "npl" in blob:
        return "EPA NPL/Superfund"
    if "rcra corrective" in blob or "rcra" in source:
        return "RCRA Corrective Action"
    if "rmp" in blob or "chemical disaster" in blob:
        return "RMP-listed (chemical disaster risk)"
    if "refinery" in type_s or "refining" in type_s:
        return "petroleum refinery (Title V Major)"
    if "incinerator" in type_s:
        return "MSW incinerator (Title V Major)"
    if "lng" in type_s or "petroleum storage" in type_s or "petroleum terminal" in type_s:
        return "petroleum/LNG storage"
    if "pfas" in blob or "fluorine chemistry" in type_s or "fluorochemicals" in type_s:
        return "PFAS / fluorochemical site"
    if "vinyl chloride" in type_s or "pvc" in type_s:
        return "PVC / vinyl-chloride manufacturer"
    if "chlorine" in type_s or "chlor-alkali" in type_s:
        return "chlorine / chlor-alkali"
    if "specialty chemical" in type_s or "chemical manufacturing" in type_s or "chemicals" in type_s:
        return "specialty / industrial chemical (likely Synthetic Minor or Title V)"
    if "power generation" in type_s or "cogeneration" in type_s or "power plant" in type_s:
        return "power generation"
    if "cafo" in type_s or "poultry" in type_s:
        return "CAFO / poultry processing (industrial scale)"
    if "landfill" in type_s:
        return "active landfill"
    if "wastewater" in type_s:
        return "municipal wastewater treatment"
    if "hazardous waste" in type_s:
        return "hazardous-waste treatment (RCRA-permitted)"
    if "industrial gas" in type_s:
        return "industrial gas manufacturer"
    if "steel" in type_s:
        return "steel mill (closed/contaminated)"
    if "manufactured gas" in type_s or "gas light" in type_s:
        return "former MGP (contamination site)"
    if "military" in type_s or "air force" in type_s:
        return "military / federal facility (PFAS-impacted)"
    if "diesel" in type_s or "highway" in type_s or "traffic" in type_s:
        return "major traffic / diesel corridor"
    if "warehouse" in type_s or "distribution" in type_s or "cold storage" in type_s:
        return "post-industrial reuse on contaminated land"
    if "vacant" in type_s or "mall" in type_s:
        return "post-industrial vacancy on contaminated land"
    if "commercial" in type_s or "redevelopment" in type_s or "development" in type_s:
        return "commercial redevelopment on contaminated land"
    if "tank cleaning" in type_s or "tank wash" in type_s or "coating" in type_s or "contractor" in type_s:
        return "industrial contractor / RCRA waste handler"
    if "petrochemical" in type_s or "polyethylene" in type_s:
        return "petrochemical / polymer manufacturer (Title V Major)"
    if "nylon" in type_s or "polymer" in type_s:
        return "former synthetic-polymer manufacturer (contamination site)"
    if "contaminated site" in type_s or "contamination site" in type_s or "cleanup" in type_s:
        return "documented contaminated industrial site (active or legacy)"
    if type_s.strip().startswith("industrial"):
        return "permitted industrial site (regulatory class to be verified)"

    return "preliminary inference pending DNREC permit verification"


def build_basis(props: dict, tier: float) -> str:
    """Compose weight_basis citation string."""
    weight = props.get("weight")
    rclass = infer_regulatory_class(props)

    parts = [f"tier_{tier:.1f}"]
    if weight is not None and abs(weight - tier) > 0.01:
        delta = weight - tier
        sign = "+" if delta > 0 else ""
        parts.append(f"{sign}{delta:.1f} modifier (facility-specific)")
    parts.append(rclass)

    trifid = props.get("trifid")
    if trifid:
        parts.append(f"TRI {trifid}")

    src = props.get("source") or ""
    src_short = src.split(";")[0].split("/")[0].strip()
    if src_short and len(src_short) <= 60:
        parts.append(f"src: {src_short}")
    elif src_short:
        parts.append(f"src: {src_short[:57]}...")

    return "; ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Patch weight_tier + weight_basis into facilities.json")
    ap.add_argument("--apply", action="store_true",
                    help="write changes to facilities.json (default: dry-run)")
    ap.add_argument("--csv", action="store_true",
                    help="also emit facility_weight_tiers.csv audit trail")
    args = ap.parse_args()

    data = json.loads(FAC.read_text())
    feats = data["features"]

    rows = []
    diffs = []
    rank_pairs = []  # for snap-rule sanity check

    for feat in feats:
        p = feat["properties"]
        name = p.get("name", "")
        weight = p.get("weight")
        if weight is None:
            print(f"ERROR: facility {name!r} missing `weight`", file=sys.stderr)
            return 1
        tier = snap_to_tier(float(weight))
        basis = build_basis(p, tier)

        existing_tier = p.get("weight_tier")
        existing_basis = p.get("weight_basis")
        if existing_tier != tier or existing_basis != basis:
            diffs.append((name, existing_tier, tier, existing_basis, basis))

        p["weight_tier"] = tier
        p["weight_basis"] = basis
        rank_pairs.append((float(weight), tier))
        rows.append({"name": name, "weight": weight, "weight_tier": tier, "weight_basis": basis})

    # Snap-rule sanity: rubric requires Spearman ρ(weight, tier) ≥ 0.95.
    rho = spearman_rho([p[0] for p in rank_pairs], [p[1] for p in rank_pairs])
    print(f"Snap-rule rank correlation (weight vs tier): ρ = {rho:.3f}")
    if rho < 0.95:
        print("WARNING: ρ below 0.95 threshold — review rubric tier mapping", file=sys.stderr)

    print(f"\n{len(diffs)} facilities have changed weight_tier or weight_basis:\n")
    for (name, et, nt, eb, nb) in diffs[:8]:
        print(f"  {name[:55]:55s}  {str(et):>5s} -> {nt:.1f}")
        print(f"      basis: {nb[:120]}")
    if len(diffs) > 8:
        print(f"  ... and {len(diffs) - 8} more (run with --csv to see full list)")

    if args.csv:
        with CSV_OUT.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["name", "weight", "weight_tier", "weight_basis"])
            w.writeheader()
            for row in rows:
                w.writerow(row)
        print(f"\nWrote {CSV_OUT.relative_to(ROOT)}")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write facilities.json.")
        return 0

    FAC.write_text(json.dumps(data, separators=(",", ":")))
    print(f"\nApplied: patched weight_tier + weight_basis into {len(feats)} facilities.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
