#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026. See LICENSE.md.
"""patch_facility_stack_height.py — add stack_height_class field to every
feature in facilities.json, derived from the facility's `type` text via a
heuristic classifier that mirrors industrial site categories.

Stack-height classes (v1.4 of the methodology, Tier 2.4):

    "tall_stack"   (≥25m typical) — refineries, large chemical plants,
                   coal/gas power plants with combustion stacks. Weight
                   multiplier: 0.7 (taller plumes dilute over a wider
                   area, reducing fenceline-near IDW contribution; a
                   full dispersion model would shift weight downwind,
                   which we don't model — see METHODOLOGY.md §6c).
    "low_stack"    (<25m) — smaller permitted point sources, gas
                   turbines, small process stacks. Weight multiplier:
                   0.85.
    "ground_level" — fugitive sources, traffic corridors, CAFOs,
                   contamination sites with no active stacks, post-
                   industrial reuse on contaminated land. Weight
                   multiplier: 1.0.

The multiplier is APPLIED to the weight at runtime by js/cis.js. This
script just classifies facilities; it doesn't change numeric weights.

Usage
-----
    python3 scripts/patch_facility_stack_height.py            # dry-run
    python3 scripts/patch_facility_stack_height.py --apply    # patch
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAC = ROOT / "facilities.json"


def classify_stack(props: dict) -> tuple[str, str]:
    """Return (class, basis) for a facility based on its type text.

    Order matters — most-specific match first. A facility classified
    "tall_stack" has type-text indicating a known tall-stack source
    category (refineries 60-100m typical, large chemical plants 30-60m,
    coal stacks 100m+). "low_stack" is permitted point sources with
    smaller stacks. "ground_level" is fugitive-only or non-stack types.
    """
    type_s = (props.get("type") or "").lower()

    # --- Tall-stack categories (≥25m typical) ---
    if "refinery" in type_s or "refining" in type_s:
        return "tall_stack", "petroleum refinery (typical 60–100m process stacks)"
    if "incinerator" in type_s or "cogeneration" in type_s:
        return "tall_stack", "MSW incinerator / cogeneration (60m+ exhaust stack)"
    if "power generation" in type_s or "power plant" in type_s:
        return "tall_stack", "combustion power generation (gas turbine 30–60m, coal 80m+)"
    if "petrochemical" in type_s or "polyethylene" in type_s:
        return "tall_stack", "petrochemical / polymer plant (30–60m process stacks)"
    if "chlor-alkali" in type_s or "chlorine" in type_s:
        return "tall_stack", "chlorine / chlor-alkali (process vent stacks ≥30m)"
    if "fluorine chemistry" in type_s or "fluorochemicals" in type_s:
        return "tall_stack", "fluorochemical plant (process vent stacks)"
    if "vinyl chloride" in type_s or "pvc" in type_s:
        return "tall_stack", "PVC / vinyl chloride manufacturer (process stacks)"
    if "lng" in type_s:
        return "tall_stack", "LNG complex flares + process stacks"

    # --- Low-stack categories (<25m typical) ---
    if "specialty chemical" in type_s or "chemical manufacturing" in type_s:
        return "low_stack", "specialty / industrial chemical (process stacks <25m typical)"
    if "industrial gas" in type_s:
        return "low_stack", "industrial gas plant (vent stacks <25m)"
    if "petroleum storage" in type_s or "petroleum terminal" in type_s:
        return "low_stack", "petroleum storage tanks (low vents/breathers)"
    if "hazardous waste" in type_s:
        return "low_stack", "RCRA hazardous-waste treatment (low vent stacks)"
    if "former chlor-alkali" in type_s or "former sulfuric" in type_s:
        return "low_stack", "former chemical plant (legacy vents, mostly capped)"

    # --- Ground-level / fugitive categories ---
    if "cafo" in type_s or "poultry" in type_s:
        return "ground_level", "CAFO / poultry processing (fugitive ammonia + dust)"
    if "diesel" in type_s or "highway" in type_s or "traffic" in type_s:
        return "ground_level", "traffic corridor (vehicle exhaust at street level)"
    if "warehouse" in type_s or "distribution" in type_s or "cold storage" in type_s:
        return "ground_level", "post-industrial reuse (no active stacks; fugitive legacy)"
    if "vacant" in type_s or "mall" in type_s:
        return "ground_level", "post-industrial vacancy (no active stacks)"
    if "commercial" in type_s or "redevelopment" in type_s or "development" in type_s:
        return "ground_level", "commercial redevelopment (no industrial stacks)"
    if "tank cleaning" in type_s or "tank wash" in type_s:
        return "ground_level", "tank cleaning operations (fugitive vapors)"
    if "coating" in type_s or "contractor" in type_s:
        return "ground_level", "industrial contractor (no stationary stacks)"
    if "wastewater" in type_s:
        return "ground_level", "WWTP (no significant air stacks; biogas flares low)"
    if "landfill" in type_s:
        return "ground_level", "landfill (gas-collection vents, mostly low)"
    if "manufactured gas" in type_s or "gas light" in type_s:
        return "ground_level", "former MGP (no active stacks; legacy soil contamination)"
    if "contaminated site" in type_s or "contamination site" in type_s or "cleanup" in type_s:
        return "ground_level", "contaminated industrial site (no active stacks)"
    if "former" in type_s and ("nylon" in type_s or "manufacturing" in type_s
                              or "steel" in type_s or "polymer" in type_s):
        return "ground_level", "former manufacturing / contaminated brownfield (no active stacks)"
    if "military" in type_s or "air force" in type_s:
        return "ground_level", "military base (mixed sources; mostly ground-level emissions)"
    if "steel" in type_s:
        return "tall_stack", "steel mill (electric arc / blast furnace stacks ≥40m)"

    # Fallback: industrial sites without a clearer match treated as low-stack.
    if "industrial" in type_s or "specialty" in type_s:
        return "low_stack", "permitted industrial (default for unspecified type)"

    # Truly unknown — default to low_stack as the most conservative middle.
    return "low_stack", "default — class not inferred from type"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write to facilities.json")
    args = ap.parse_args()

    data = json.loads(FAC.read_text())
    feats = data["features"]

    counts = {"tall_stack": 0, "low_stack": 0, "ground_level": 0}
    diffs = []
    for feat in feats:
        p = feat["properties"]
        klass, basis = classify_stack(p)
        counts[klass] += 1
        existing = p.get("stack_height_class")
        if existing != klass:
            diffs.append((p.get("name", "?"), existing, klass, basis))
        p["stack_height_class"] = klass
        p["stack_height_basis"] = basis

    print(f"Stack-height distribution across {len(feats)} facilities:")
    for k, v in counts.items():
        print(f"  {k:14s}: {v}")

    print(f"\n{len(diffs)} facilities have changed stack_height_class:")
    for name, old, new, basis in diffs[:12]:
        print(f"  {name[:55]:55s}  {str(old):>13s} -> {new:14s}")
        print(f"      basis: {basis}")
    if len(diffs) > 12:
        print(f"  ... and {len(diffs) - 12} more")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write facilities.json.")
        return 0

    FAC.write_text(json.dumps(data, separators=(",", ":")))
    print(f"\nApplied: patched stack_height_class + basis into {len(feats)} facilities.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
