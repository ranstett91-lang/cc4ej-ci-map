# Facility Weighting Rubric

**Status:** v1.0 (preliminary). This rubric formalizes the facility weights used by the Facility Burden Index (CIS) on the CC4EJ Cumulative Impacts map. Weights are scheduled to be replaced by TRI-derived values in a later methodology version (see [METHODOLOGY.md](METHODOLOGY.md) §weighting and the project changelog).

## Purpose

Each facility in [facilities.json](facilities.json) carries a `weight` value (range 1.2–3.0) that determines how strongly it contributes to a location's modeled facility-burden score. Higher weight = greater hazard contribution per unit of proximity. Until v1.0 of this rubric, weights were assigned by domain judgment without a published basis. This document declares that basis.

## The six tiers

| Tier | Definition | Typical sources | Examples in DE/PA/NJ |
| ---- | ---------- | --------------- | -------------------- |
| **3.0** | Major emitter with HAP profile, OR active Superfund/NPL site with documented contamination, OR PFAS-implicated facility, OR fluorochemical / vinyl-chloride manufacturer | Title V Major + HAP, NPL Superfund, PFAS sites | Solstice/Honeywell AWE, Citisteel, Chemours Chambers Works, Chemours Edge Moor, OxyVinyls Pedricktown |
| **2.5** | Title V Major non-HAP, OR petroleum refinery, OR LNG/petroleum storage at scale, OR active chlorine/chemical manufacturing, OR chemical-disaster (RMP) site | Title V Major, refinery, large RMP | Delaware City Refinery, Energy Transfer Marcus Hook, Kuehne Chemical, Honeywell Delaware Plant, Evraz Claymont Steel |
| **2.0** | Multi-pollutant industrial facility, OR petrochemical / specialty-chemical plant, OR active landfill with gas recovery | Synthetic Minor with multiple pollutants, large industrial | Croda Atlas Point, Valtris, LANXESS, DSWA Cherry Island, Oceanport Industries |
| **1.8** | Permitted industrial facility with single-pollutant or low-volume TRI history, OR active power generation (gas), OR CAFO / large industrial poultry | Synthetic Minor low-volume, gas turbines, CAFOs | Calpine Edge Moor / Hay Road, Air Liquide Delaware City, Nexpera, Dover AFB, Mountaire Millsboro / Harbeson |
| **1.5** | Smaller permitted source, OR petroleum terminal, OR commercial development on contaminated land, OR major traffic / diesel corridor | Smaller permitted, terminals, diesel corridors | I-95/I-495 Claymont, Buckeye Terminals, Messer Claymont, First State Crossing |
| **1.2** | Legacy / historic site without active emissions but with documented contamination, OR municipal wastewater, OR contractor activities at scale | Closed legacy, WWTP, contractors | Wilmington WWTP, Corrosion Control Corp |

## Snap rule

The current numeric `weight` values were assigned before this rubric and include intermediate values (1.3, 1.6, 2.2, 2.3, 2.8) that don't sit exactly on tier centers. For v1.0:

- `weight_tier` is the nearest tier label (e.g., a numeric weight of 2.8 maps to `tier_2.5`; a weight of 1.3 maps to `tier_1.2`).
- The numeric `weight` value is **left unchanged** in this step. Off-tier values reflect facility-specific modifiers (recent emissions volume, multi-pollutant emissions, age, regulatory class) that the v2 TRI-derived weights step will formalize into a multiplicative composite.
- Where weight equals the tier center exactly, `weight_basis` cites the assignment source. Where it doesn't, `weight_basis` notes the off-tier modifier in plain language (e.g., "tier_2.5 with +0.3 modifier for active HAP emissions").

The Spearman rank-correlation between `weight_tier` (snapped) and `weight` (numeric) should be ≥ 0.95 across the 54 facilities; if not, the rubric needs revision.

## What `weight_basis` should contain

Each facility's `weight_basis` field is a one-line citation. It should include, where known:

1. **Regulatory class** — Title V Major / Synthetic Minor / RMP / Superfund / RCRA Corrective Action / closed-legacy-site
2. **Source citation** — TRI Form R ID, EPA NPL listing, DNREC permit identifier, RMP submission, or other public record
3. **Justification for any off-tier modifier** — e.g., "elevated to 2.8 due to recent benzene emissions per TRI 19720..."

Where a regulatory class hasn't been verified against authoritative sources, `weight_basis` says so explicitly: `"preliminary inference from public records; pending DNREC permit verification"`. This is preferable to fabricating a class.

## Provenance and changelog

Source-of-truth for `weight_tier` assignments is `facility_weight_tiers.csv` at the repo root. To change a tier, edit that CSV and run `scripts/patch_facility_weight_tier.py --apply`. Every change is logged in [CHANGELOG.md](CHANGELOG.md).

## Limitations

- This rubric reflects the project team's domain judgment based on public records. It is not a regulatory determination. Weights and tiers are subject to revision as authoritative permit data is verified.
- Tier 2.1 of the methodology roadmap will replace this rubric with a TRI-derived composite formula (see [METHODOLOGY.md](METHODOLOGY.md) §weighting). Until then, treat these tier assignments as the working classification.
- Tier definitions emphasize emission-source severity, not health-outcome severity. A "tier_3.0" facility is not necessarily linked to greater observed health impacts than a "tier_2.5" facility — that's an empirical question handled in the validation analyses (see roadmap Tier 3).

## Citation

When citing CC4EJ facility weights in external work, cite this rubric version and the date of `facility_weight_tiers.csv` retrieval, e.g.:
> *Facility weights derived from CC4EJ Weighting Rubric v1.0 (CC4EJ, 2026); source citations per `weight_basis` field.*
