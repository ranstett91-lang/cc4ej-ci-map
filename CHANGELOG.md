# Methodology Changelog

This file logs every version bump to the Facility Burden Index (CIS) methodology. The authoritative technical document is [METHODOLOGY.md](METHODOLOGY.md).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) loosely. Each entry calls out: what changed, why, the file(s) affected, and any rank-order or numeric impact on existing scores.

## Tagging plan

Git tags `methodology-v1.0`, `methodology-v1.1`, `methodology-v1.2` are intended to mark each release on `main` after this branch merges. Apply with:

```sh
# After merging the methodology branch to main:
git tag -a methodology-v1.2 -m "Chronic wind-rose factor (Tier 2.3)" <HEAD-of-merge>
# Earlier tags can point to interim commits or all to the same merge commit
# (the CHANGELOG below is the authoritative version log either way).
git push --tags
```

Tags should NOT be applied while the methodology work lives in a worktree branch — a future rebase would orphan them. CHANGELOG.md is the source of truth until the tags land on `main`.

---

## v1.2.1 — 2026-05-07 — Standalone CIS module + JS↔Python parity test

### Changed
- **CIS math extracted from inline JS in [index.html](index.html) into a standalone module [js/cis.js](js/cis.js)** (Tier 4.2 of the roadmap). The module exposes `haversineKm`, `bearingTo`, `angleDiff`, `chronicWindFactor`, `rawProximityCIS`, `normalizeCIS`, `cisInterpretation`, and `CIS_DECAY` / `CIS_MIN_MI` as both browser globals (for the inline app code that uses bare names) AND as a CommonJS module (for Node-based testing). No math change.
- **NaN/null coordinate guard strengthened.** Previously the inline `haversineMi` checked `lat1`/`lat2` for null/NaN but not the longitudes; the cis.js version checks all four coordinates and returns the 999-mile sentinel for any of them. Closes a theoretical NaN-propagation path.
- **`rawProximityCIS()` in index.html is now a 6-line wrapper** that injects mutable globals (`facilitiesData.features`, `windFromDeg`, `windRose`) into the pure cis.js function. Existing call sites — `precomputeCISNorm`, `buildCISGrid`, the address-search lookup, the click-to-score popup — keep their 3-arg `(lat, lng, year)` signature unchanged.

### Added
- **[scripts/test_cis_parity.py](scripts/test_cis_parity.py)** — JS↔Python parity test. Generates a deterministic 59-point battery (8 anchor points × 3 wind-mode variants + 35 random points across DE/PA/NJ), runs both Python (`_cis_stats.raw_proximity_cis`) and JS (via Node spawning a temp harness that loads `js/cis.js`), and asserts machine-precision equality.
  - Result: max |Δ| = **2.3 × 10⁻¹²** across all 59 points (≈10× f64 epsilon — pure operation-order rounding noise). Passes at tolerance 1×10⁻⁹.
  - Skips gracefully if Node.js is not on PATH.
- **NaN guard in [scripts/_cis_stats.py](scripts/_cis_stats.py)** `haversine_mi()` — matches the cis.js behavior for parity.

### Why
- Single source of truth for the production math means the methodology document and the rendered map can never silently disagree.
- Parity test runs in seconds and turns "the JS and Python implementations match" from a manual-audit assumption into a verified property of the codebase.
- Future math changes (Tier 2.2 multi-pollutant, Tier 2.4 stack height) can be made in cis.js + _cis_stats.py and tested for parity in the same commit, blocking drift before it lands.

### Files affected
- New: [js/cis.js](js/cis.js), [scripts/test_cis_parity.py](scripts/test_cis_parity.py)
- Modified: [index.html](index.html) (script tag for cis.js, inline math removed, rawProximityCIS wrapper added), [scripts/_cis_stats.py](scripts/_cis_stats.py) (NaN guard parity), [METHODOLOGY.md](METHODOLOGY.md) (version bump)

### Reproducibility
```sh
python3 scripts/test_cis_parity.py            # default tolerance 1e-6
python3 scripts/test_cis_parity.py --tol 1e-9 # stricter
python3 scripts/test_cis_parity.py --verbose  # per-point output
```

---

## v1.2 — 2026-05-06 — Chronic wind-rose factor

### Changed
- **Wind factor in `rawProximityCIS()` now defaults to a 10-year climatological wind rose** instead of the snapshot-only behavior of v1.0–v1.1. The live wind toggle still applies a snapshot factor on user request; the static rendered grid and the CIS_P95 normalization now use chronic (rose) weighting so the published map reflects climatology rather than a momentary observation.
- Three modes added (priority order): snapshot (`windFromDeg !== null`), chronic (rose loaded, no snapshot), baseline (rose not loaded). See [METHODOLOGY.md §6](METHODOLOGY.md).
- Robustness: input validation on `noaa_wind_rose.json` shape — a malformed file silently falls back to the v1.0 baseline (no-wind) behavior rather than crashing the CIS path.

### Added
- **[scripts/fetch_noaa_wind_rose.py](scripts/fetch_noaa_wind_rose.py)** — pulls NOAA Integrated Surface Database (ISD) hourly observations for KILG (Wilmington/New Castle Airport), bins into 16 compass sectors over a configurable year window (default 2015–2024), writes [noaa_wind_rose.json](noaa_wind_rose.json).
- **[noaa_wind_rose.json](noaa_wind_rose.json)** — generated wind climatology (~99,800 directional observations + ~11,500 calm; mean speed 4.19 m/s; predominant directions NW/S/WNW/W).

### Quantitative impact
- Per-facility wind multiplier under the chronic rose ranges from ~0.93 to ~1.07 in practice (modest, because the rose averages out across all directions).
- Rank-order at BG centroids: production CIS rank under v1.2 chronic vs v1.1 baseline (no-wind) preserved at high ρ (verified by `audit_cis_sensitivity.py`).
- Absolute scores re-anchored: CIS_P95 changes slightly, so individual normalized values may shift ±5–10% even when relative rank is unchanged.

### Why
- A snapshot wind factor varies with whatever the last weather fetch returned, making the rendered grid non-reproducible (two viewers seeing different weather see different overlays). A chronic rose anchors the map to a published climatological reference. Future viewers running `fetch_noaa_wind_rose.py` against the same year window get identical output.
- See [METHODOLOGY.md §6](METHODOLOGY.md) for the math and the v1.2 limitations (single station, no speed weighting, no diurnal variation).

### Files affected
- [index.html](index.html) — `windRose` global ([index.html:3151](index.html:3151)); fetch + parse with shape validation in the load chain; `chronicWindFactor()` helper; `rawProximityCIS()` rewritten with three-mode wind logic.
- [METHODOLOGY.md](METHODOLOGY.md) — §6 rewritten; version bumped to v1.2.

### Reproducibility
```sh
python3 scripts/fetch_noaa_wind_rose.py --years 2015-2024
```
Re-running with the same year window produces identical output (the source data does not change after the fact). Bumping the year window triggers a methodology version bump.

---

## v1.1 — 2026-05-06 — TRI-derived facility weights

### Changed
- **Facility weights are now derived from EPA TRI public records** rather than hand-curated. Composite formula:
  ```
  weight = clamp(1.2, 3.0,
      base_tier × (1 + α · log10(1 + recent_5yr_avg_lbs / 1000))
                × (1 + β · HAP_flag)
                × (1 + γ · NAICS_high_risk_flag))
  ```
  with α = 0.03, β = 0.05, γ = 0.05.
- 34 of 54 facilities (those with a `trifid` join key) have their numeric `weight` recalculated from TRI release-pound history, EPA HAP-list match, and NAICS classification.
- 20 facilities without TRI matches (Superfund-only, traffic corridors, legacy contamination sites, smaller permitted) keep their rubric tier weight unchanged.
- **`weight_tier`** (rubric regulatory classification) is unchanged. **`weight`** (operational value used by the CIS formula) and **`weight_basis`** (now appends a TRI-derivation line) are updated.

### Quantitative impact
- Spearman rank correlation between v1.0 (hand-curated) and v1.1 (TRI-derived) weights: **ρ = 0.971**. Rank-order is preserved; the formula amplifies the existing severity ordering without inverting it.
- Largest changes (all upward, all to refineries / chemical plants with multi-million-pound annual TRI release): Delaware City Refinery 2.5 → 3.0, Paulsboro Refining 2.5 → 3.0, Braskem Marcus Hook 2.3 → 2.8, Evraz Claymont Steel 2.5 → 2.9.
- No facility's weight decreased. No weight is below 1.2 or above 3.0 (formula is clamped).

### Why
- The v1.0 hand-curated weights had no published rubric basis, leaving the methodology open to "you made up the numbers" criticism. The composite formula uses public EPA records as inputs, making every weight reproducible from `tri_history.json`, `tri_facilities.json`, and a documented HAP/NAICS list.
- See [METHODOLOGY.md §7](METHODOLOGY.md) and [weighting_rubric.md](weighting_rubric.md) for full rationale.

### Files affected
- [facilities.json](facilities.json) — `weight` updated; `weight_basis` extended with TRI-derived provenance.
- [facility_weights.json](facility_weights.json) — generated audit JSON keyed by trifid.
- [weight_provenance.csv](weight_provenance.csv) — generated audit CSV (one row per facility).
- [scripts/build_facility_weights.py](scripts/build_facility_weights.py) — new build script (idempotent; supports `--patch` to apply).

### Reproducibility
```sh
python3 scripts/build_facility_weights.py            # dry-run + write audit files
python3 scripts/build_facility_weights.py --patch    # apply to facilities.json
```

### Limitations introduced
- The `recent_5yr_avg_lbs` term uses total annual TRI release pounds without pollutant-toxicity weighting. A facility releasing 1M lb of low-toxicity solvent and a facility releasing 1M lb of HAP get the same emissions multiplier (the HAP flag adds a flat 5%, not a toxicity-weighted boost). Pollutant-toxicity-weighted scoring lands in v1.2.
- HAP detection uses substring matching against TRI chemical names — a curated list of ~45 keyword markers covering the substantial majority of CAA §112 HAPs that appear in DE/PA/NJ TRI submissions. Edge-case chemical names may miss matches; review `weight_provenance.csv` `hap_keywords` column to verify.

---

## v1.0 — 2026-05-06 — Initial published methodology

### Added
- **[METHODOLOGY.md](METHODOLOGY.md)** — first formal write-up of the CIS formula, parameters, normalization, time filter, and wind treatment. No formula changes from prior implementation; this version documents the existing math and adds the rubric + sensitivity scaffolding.
- **[weighting_rubric.md](weighting_rubric.md)** — six-tier weighting rubric (3.0 / 2.5 / 2.0 / 1.8 / 1.5 / 1.2) with regulatory-class definitions and per-facility basis citations.
- **[scripts/patch_facility_weight_tier.py](scripts/patch_facility_weight_tier.py)** — idempotent patcher that adds `weight_tier` and `weight_basis` to every feature in `facilities.json`.
- **[scripts/audit_cis_sensitivity.py](scripts/audit_cis_sensitivity.py)** — sensitivity analysis script. Reports Spearman ρ between production-decay (1.5) and {1.0, 1.25, 1.75, 2.0} variants. Result: minimum ρ = 0.981 across 700 BG centroids — rank-order is robust.
- **In-app methodology section** in `index.html` Data & Methods modal ("How Facility Burden Index (CIS) is scored").
- **Validation analysis** at [analyses/cis_places_correlation_2026.md](analyses/cis_places_correlation_2026.md) — empirical CIS × CDC PLACES correlation with age-confounder analysis.

### Changed
- **User-facing rename:** "Exposure surface" → "Facility Burden Index" everywhere in user-facing copy. Internal identifiers (`CIS_*`, `cis-grid`, `toggleCISGrid()`) and EPA EJScreen indicator labels ("Traffic exposure", "Diesel exposure") stay unchanged.

### Files affected
- [index.html](index.html) — UI rename, new methodology section, narrative copy update.
- [facilities.json](facilities.json) — added `weight_tier` and `weight_basis` to all 54 features.
- [README.md](README.md), [data_sources.md](data_sources.md) — link-out to METHODOLOGY.md.

### Compatibility note
- Numeric `weight` values were NOT changed in v1.0. The rubric formalizes existing weights; v1.1 is the first version that recalculates them.
