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

## 2026-05-07 — Tier 3.2 air-monitor correlation analysis (no methodology bump)

Empirical validation of the CIS as a proximity-burden proxy against EPA AQS measured air quality. Not a methodology change — adds an analysis report alongside the v2.0 release that the report tests against.

### Added
- **[scripts/fetch_epa_aqs_monitors.py](scripts/fetch_epa_aqs_monitors.py)** — pulls EPA AirData annual_conc_by_monitor_*.zip pre-generated files (no auth required), filters to DE state code 10, extracts annual arithmetic mean for the criteria pollutants (PM2.5, NO2, O3, SO2, CO).
- **[scripts/analyze_cis_monitors.py](scripts/analyze_cis_monitors.py)** — for each active DE monitor, computes the production CIS at the monitor's coordinates and correlates with the multi-year mean concentration. Reports observed Spearman ρ + directional-hypothesis test.
- **[air_monitors.json](air_monitors.json)** — generated side-car (11 DE monitors over 2018-2024).
- **[analyses/cis_monitor_correlation_2026.md](analyses/cis_monitor_correlation_2026.md)** — full report with per-monitor table, headline ρ, limitations, reproducibility instructions.

### Headline findings (full report at the link above)
- PM2.5 (n=7): ρ = +0.14 — **directionally consistent** with prediction.
- SO2 (n=5): ρ = +0.10 — directionally consistent.
- O3 (n=7): ρ = −0.45 — **inverse, but consistent with NOx-titration chemistry** (urban industrial corridors have lower regional O3 because freshly-emitted NO consumes it). Not a contradiction.
- NO2, CO: only 1 monitor each in DE; correlation undefined.

### Honest framing
- Sample-size caveat is essential — Spearman ρ at n=5–7 has wide CIs; the report explicitly avoids "statistically significant" language and tests direction-of-effect, not magnitude.
- What this DOES show: the CIS is not anti-correlated with measured pollution in directions that contradict its design; the methodology is honestly testable against external data; the test was run and the results published regardless of sign.
- What this DOES NOT show: a strong predictive relationship between CIS and measured concentration. A clearer test requires Delaware's monitor network to grow, cross-state airshed pooling, or AERMOD-grade dispersion modeling (Tier 3.3 — partner-dependent).

### Files affected
- New: [scripts/fetch_epa_aqs_monitors.py](scripts/fetch_epa_aqs_monitors.py), [scripts/analyze_cis_monitors.py](scripts/analyze_cis_monitors.py), [air_monitors.json](air_monitors.json), [analyses/cis_monitor_correlation_2026.md](analyses/cis_monitor_correlation_2026.md)
- Modified: [METHODOLOGY.md](METHODOLOGY.md) §8c (new empirical-validation subsection)

### Reproducibility
```sh
python3 scripts/fetch_epa_aqs_monitors.py --years 2018-2024
python3 scripts/analyze_cis_monitors.py
```

---

## v2.0 — 2026-05-07 — Population-weighted CIS_P95 normalization (major bump)

### Why this is v2.0 not v1.5
The 0-10 normalized scale is the user-facing contract of the published map. v1.x adjusted the math that *produces* CIS scores; v2.0 changes the math that *anchors* the scale. Cells that scored 6.5 on the v1.4 map score ~6.86 on the v2.0 map. Numbers cited in legislator memos, press releases, and grant proposals against the v1.x scale need to be re-reported. That's a major-version-level commitment, not a refinement.

### Changed
- **Normalization is now population-weighted** ([METHODOLOGY.md §4](METHODOLOGY.md)). Each BG centroid is sampled with weight = BG ACS population. The 95th percentile is computed against cumulative population rather than against geometric BG count. The new sentence is: "5% of Delaware *residents* live in a place with raw CIS at or above P95" — not "5% of polygons hit P95."
- **Quantitative shift**: v1.4 unweighted P95 (combined category) = 9.99; v2.0 weighted P95 = 9.46. A −5.3% shift in the denominator means published normalized scores rise ~5% across the map. Rank-order is unchanged — the percentile is a denominator, not a re-sort.
- BGs with zero population (commercial parks, water bodies, etc.) are excluded from the percentile calculation. They were always excluded from population-burden interpretation anyway; v2.0 makes that explicit.

### Added
- **`populationWeightedPercentile(samples, q)` in [js/cis.js](js/cis.js)** and **`population_weighted_percentile(samples, q)` in [scripts/_cis_stats.py](scripts/_cis_stats.py)** — shared math, single source of truth, parity-tested against each other.
- **P95 parity check in [scripts/test_cis_parity.py](scripts/test_cis_parity.py)** — verifies that JS and Python compute identical population-weighted percentiles for a 700-BG synthetic battery. Result: identical to ALL 12 decimal places.
- The inline `precomputeCISNorm` in [index.html](index.html) now calls `CIS.populationWeightedPercentile()` rather than inlining the loop, so future percentile math changes land in one file with parity test coverage.

### Why population-weighted is the right anchor
- BG populations vary 10–50× across Delaware. An unweighted percentile gives a 200-resident rural BG and a 5,000-resident urban BG equal say in defining "the 95th percentile community." Under population weighting, the high-burden urban BGs that are also the high-population BGs (Wilmington, Marcus Hook border, NCC industrial corridor) carry their proportional share of the cutoff definition.
- The 0-10 scale is a *resident-centered* communication device. Anchoring it to resident-experienced burden, not polygon-counted burden, makes the published numbers honest about what they're describing.

### Limitations
- Still uses BG centroids (not dasymetric within-BG sampling). A future v2.1 could distribute BG population across NLCD imperviousness pixels to identify where within each BG residents actually live; this would mostly affect sparse rural BGs where the centroid lies far from population concentration.
- 0-pop BG exclusion drops ~10–15 BGs from the normalization sample. These are typically commercial/industrial-only zones; their CIS scores still render but don't influence the P95.
- The 5% downward shift in P95 is roughly stable across categories; a future audit might verify that cancer/respiratory P95s shift by similar magnitudes.

### Files affected
- Modified: [js/cis.js](js/cis.js), [scripts/_cis_stats.py](scripts/_cis_stats.py), [scripts/test_cis_parity.py](scripts/test_cis_parity.py), [index.html](index.html), [METHODOLOGY.md](METHODOLOGY.md) §4 + Versioning section

### Reproducibility
```sh
python3 scripts/test_cis_parity.py --tol 1e-9
# Includes the P95 parity check, which exits non-zero if JS and Python
# implementations of populationWeightedPercentile diverge.
```

---

## v1.4 — 2026-05-07 — Stack-height dampener for tall-source facilities

### Added
- **`stack_height_class` and `stack_height_basis` on every feature in [facilities.json](facilities.json).** Three classes: `tall_stack` (18 facilities — refineries, incinerators, power plants, large chemical plants, fluorochemical/chlor-alkali process stacks, steel mills), `low_stack` (15 facilities — specialty chemicals, industrial gas, petroleum storage, hazardous-waste treatment, former plants with capped legacy vents), `ground_level` (21 facilities — CAFOs, traffic, post-industrial reuse, vacancies/redevelopment, contractor operations, WWTP, landfills, former MGP, brownfields, military bases).
- **[scripts/patch_facility_stack_height.py](scripts/patch_facility_stack_height.py)** — heuristic classifier driven by the existing `type` field; idempotent `--apply` patcher with a per-facility basis citation describing the typical stack height for that facility category.
- **STACK_HEIGHT_FACTOR = {tall: 0.7, low: 0.85, ground: 1.0}** in both [js/cis.js](js/cis.js) and [scripts/_cis_stats.py](scripts/_cis_stats.py); applied per-facility inside `rawProximityCIS()` AFTER the wind factor, BEFORE the distance-power division.

### Changed
- The IDW formula no longer treats every facility as a point source at its coordinates. Tall-stack sources (refineries, coal plants, incinerators) now contribute 30% less to nearby query points, reflecting the physical reality that elevated plumes disperse higher and farther — fenceline residents get less burden from a 100m-stack source than from a ground-level fugitive source emitting the same mass. See [METHODOLOGY.md §6c](METHODOLOGY.md).

### Quantitative impact
- Sensitivity rank-correlation across decay variants 1.0–2.0: minimum **ρ = 0.980** across 700 BG centroids (was 0.981 in v1.3) — rank-order is robust; the dampener doesn't shuffle severity ordering, it adjusts magnitudes.
- JS↔Python parity verified across 75 test points × 3 categories: max |Δ| = **1.6 × 10⁻¹²** (machine precision). Passes at tolerance 1e-9.
- The dampener is a first-order screening adjustment. A correct dispersion treatment would also SHIFT contribution downwind from tall sources (the 5-10km downwind region gets MORE burden than the fence); we don't add that. AERMOD remains the regulatory-grade alternative (see Tier 3.3 of the roadmap).

### Why
- Refineries are the largest emitters in the Delaware-region inventory. Without a stack-height adjustment, the IDW formula systematically over-attributes burden to refinery fencelines and under-attributes to communities 5-10 km downwind. The 0.7 dampener partially corrects this — modestly defensible in the regulatory dispersion literature (EPA SCREEN3 docs, OEHHA stack-height guidance suggest near-fence ground-level is 50-70% of a ground-level source's contribution for ≥30m stacks).
- Ground-level fugitive sources (CAFOs, traffic, post-industrial reuse on contaminated land) keep their full weight — those emissions DO mix at street level where residents breathe.

### Limitations
- **No downwind shift.** Tall-stack burden gets reduced near the fence but not added downwind. Communities 5-10 km from a refinery may be relatively under-attributed.
- **Hand-curated classes.** Classification is heuristic-driven from the `type` field text. Not all facilities have well-documented stack heights; the classifier defaults to `low_stack` for unmatched industrial sites. Per-facility verification against DNREC permits or TRI Form R stack columns is a candidate v1.5 refinement.
- **Multipliers are flat per class.** A 30m and a 100m stack get the same `tall_stack` weight. A more granular continuous multiplier could be derived from actual stack heights, given the data.

### Files affected
- New: [scripts/patch_facility_stack_height.py](scripts/patch_facility_stack_height.py)
- Modified: [js/cis.js](js/cis.js), [scripts/_cis_stats.py](scripts/_cis_stats.py), [scripts/test_cis_parity.py](scripts/test_cis_parity.py), [facilities.json](facilities.json) (stack_height_class + basis on every feature), [METHODOLOGY.md](METHODOLOGY.md) (new §6c)

### Reproducibility
```sh
python3 scripts/patch_facility_stack_height.py --apply
python3 scripts/test_cis_parity.py --tol 1e-9
python3 scripts/audit_cis_sensitivity.py --write
```

---

## v1.3 — 2026-05-07 — Multi-pollutant CIS variants (combined / cancer / respiratory)

### Added
- **Three CIS surfaces** instead of one. The floating "Facility burden" pill now carries a segmented "All / Cancer / Respiratory" control that selects which variant the rendered grid + click-to-score popups use. Default = combined (matches v1.0–v1.2.1 behavior). See [METHODOLOGY.md §7b](METHODOLOGY.md).
- **[scripts/fetch_tri_chemical_history.py](scripts/fetch_tri_chemical_history.py)** — pulls per-chemical-per-year TRI release data from EPA Envirofacts `tri_form_r_ez` for DE+PA+NJ. Captures TRI's own `caac_ind` (CAA §112 HAP) and `carc_ind` (EPA-classified carcinogen) flags so chemical classification doesn't depend on keyword guesswork.
- **[tri_chemical_history.json](tri_chemical_history.json)** (1.2 MB) — generated side-car with 1,680 facilities × 253 chemicals × 23,453 facility-year-chemical tuples for 2020-2024. 130 HAP-listed chemicals, 83 EPA-classified carcinogens.
- **[scripts/_chem_categories.py](scripts/_chem_categories.py)** — chemical → category classifier. Cancer category = TRI's `carc_ind=1` ∪ a curated CAS supplement covering well-documented carcinogens that older TRI submissions left unflagged (benzene, ethylene oxide, vinyl chloride, asbestos, formaldehyde, etc.). Respiratory category = a curated CAS list drawn from EPA IRIS RfC values, OEHHA RELs, and the criteria pollutants list (sulfuric acid mists, NOx, SO2, chlorine, hydrochloric acid, hydrogen fluoride, etc.). Each CAS entry carries a one-line provenance citation.
- **[scripts/build_facility_weights_v13.py](scripts/build_facility_weights_v13.py)** — extends v1.1's TRI-derived weights with per-category breakdowns. For each TRI-matched facility, sums the most-recent 5-year air releases (stack + fugitive) per category and allocates `weight_combined × (category_air_lbs / total_air_lbs)`. Patches both `facility_weights.json` and `facilities.json` with `weight_by_category: {combined, cancer, respiratory}`.

### Changed
- **[js/cis.js](js/cis.js)** — `rawProximityCIS` gains a `category` parameter ("combined" | "cancer" | "respiratory", default "combined"). Facilities with null/zero weight in the chosen category are skipped — they don't contribute to that surface.
- **[scripts/_cis_stats.py](scripts/_cis_stats.py)** — Python reference `raw_proximity_cis` mirrors the same category parameter for parity.
- **[scripts/test_cis_parity.py](scripts/test_cis_parity.py)** — battery extended to 75 points covering all three categories × all three wind modes; max |Δ| still 2.3 × 10⁻¹² at machine precision.
- **[index.html](index.html)** — `cisCategory` global, `CIS_P95_BY_CAT` (per-category normalization denominators), `setCISCategory(cat)` handler, `precomputeCISNorm` runs three times to compute all three P95s. The wrapper `rawProximityCIS(lat, lng, year)` threads the active category into `CIS.rawProximityCIS`. The segmented control under the pill toggles category and triggers a grid rebuild.

### Allocation discipline
- Cancer surface: 11 of 54 Delaware-region facilities contribute. Top contributors: Mexichem Vestolit (2.86 cancer-weight, vinyl chloride), Energy Transfer Marcus Hook (2.68, refinery benzene/toluene), Monroe Energy Trainer Refinery (1.83), Chemours Chambers Works (1.75), Dover AFB (1.54).
- Respiratory surface: 18 of 54 facilities contribute. Top contributors: Delaware City Refinery (2.81 respiratory-weight, sulfuric acid mists), Kuehne Chemical (2.76, chlorine manufacturer), Energy Transfer Marcus Hook (2.52), Paulsboro Refining (2.39), Indian River Power (2.16, coal-plant SO2/NOx).
- Combined surface: all 54 facilities (unchanged from v1.0).
- Non-TRI facilities (Superfund-only, traffic, legacy) are excluded from cancer and respiratory; they appear only on combined.

### Why
- Pollution health endpoints are pollutant-specific. Cancer epidemiology cares about benzene/EtO/vinyl chloride; asthma/COPD epidemiology cares about PM precursors and acid mists. A single weighted-sum surface conflates these into one number that says "lots of stuff" without saying "lots of WHAT." The v1.3 split lets a viewer ask "which neighborhoods sit in the highest cancer-relevant burden?" — and get an answer that's traceable to specific TRI-reported chemicals.
- Defensible to industry and regulatory critics: the cancer category uses EPA's own carcinogen flag plus a CAS supplement with citations; the respiratory category uses IRIS/OEHHA criteria. No keyword-matching guesswork.

### Limitations introduced
- **Air-only allocation.** Category shares use stack + fugitive air releases, ignoring water/landfill/transfer pathways. Defensible for proximity-mediated air burden but not for drinking-water or food-chain analysis.
- **No within-category toxicity weighting.** 100 lb of benzene and 100 lb of formaldehyde count equally in the cancer surface allocation. v1.5+ may add IRIS IUR-based weights.
- **5-year window.** Allocation uses TRI 2020-2024. Older closed facilities (pre-2020) get 0 in their category share even if they emitted heavily before; the combined surface still includes them via the rubric tier weight.
- **20 non-TRI facilities** (Superfund, traffic, legacy contamination) aren't attributed to cancer or respiratory. Documented in METHODOLOGY.md §7b as a known limitation; case-by-case category overrides could land in v1.4+.

### Files affected
- New: [scripts/fetch_tri_chemical_history.py](scripts/fetch_tri_chemical_history.py), [scripts/_chem_categories.py](scripts/_chem_categories.py), [scripts/build_facility_weights_v13.py](scripts/build_facility_weights_v13.py), [tri_chemical_history.json](tri_chemical_history.json)
- Modified: [js/cis.js](js/cis.js), [scripts/_cis_stats.py](scripts/_cis_stats.py), [scripts/test_cis_parity.py](scripts/test_cis_parity.py), [index.html](index.html), [facilities.json](facilities.json) (added weight_by_category to all 54 features), [facility_weights.json](facility_weights.json), [METHODOLOGY.md](METHODOLOGY.md)

### Reproducibility
```sh
python3 scripts/fetch_tri_chemical_history.py --years 2020-2024
python3 scripts/build_facility_weights_v13.py --patch
python3 scripts/test_cis_parity.py --tol 1e-9
```

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
