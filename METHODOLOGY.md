# Methodology — Facility Burden Index (CIS)

**Methodology version:** v1.4 (2026-05-07). See [CHANGELOG.md](CHANGELOG.md) for the version history.

**Plain-English audience:** the same content in lower-fidelity, resident/legislator-friendly form is rendered in the "How burden is calculated" chapter of the live site. This document is the technical source of truth.

---

## 1. What the Facility Burden Index measures (and what it does NOT measure)

The Facility Burden Index — internally referenced as CIS, *Cumulative Impact Score* — is a continuous proximity-weighted measure of how many permitted-emission and contaminated-site sources surround a given location, weighted by hazard severity. It is rendered as a sub-neighborhood (~1 km grid) raster overlay on top of the block-group EJ choropleth.

**It IS:**
- A screening proxy for cumulative facility burden in the EPA EJScreen tradition (proximity indicators)
- A way to visualize where multiple permitted sources stack up, including across BG/county/state lines
- A time-aware view: the surface shrinks/grows as the year slider regresses through facility founding dates
- A reproducible computation: same inputs → same scores

**It is NOT:**
- A measured pollutant concentration (that would require monitor data or AERMOD-grade dispersion modeling)
- A predictor of any individual's health outcome
- A regulatory exposure assessment
- Calibrated against atmospheric dispersion physics (no plume modeling, no stack-height adjustment in v1)
- Pollutant-differentiated in v1 (cancer-driver vs respiratory-driver separation lands in a future version — see roadmap)

The site framing throughout the application reinforces "modeled, not observed" and "association, not individual causation"; this document is the technical reason that framing is honest.

---

## 2. Formula

For any geographic point `(lat, lng)` and an optional year `y`:

```
score(lat, lng, y) = Σ_facilities ( weight_f / max(distance_f, floor)^decay × wind_factor_f )

where the sum is over facilities whose `founded` ≤ y (or unfiltered if y is None)
```

The raw score is then normalized to a 0–10 scale (see §4).

Implementation: [index.html:8999-9099](index.html:8999), function `rawProximityCIS()`.

---

## 3. Parameters and rationale

| Parameter | Value | Rationale |
| --- | --- | --- |
| `CIS_DECAY` | 1.5 | Inverse-distance-weighting decay exponent. Common defensible choices in EJ proximity literature are 1.0, 1.5, 2.0. 1.5 sits in the middle: a lower exponent weights regional dispersion too heavily; a higher exponent over-emphasizes the immediate fence. Chosen as a defensible compromise. Sensitivity to this choice is reported in §8. |
| `CIS_MIN_MI` | 0.15 mi (~240 m) | Numerical floor on the distance term to prevent divide-by-zero / score blow-up when a query point lies right at a facility's coordinates. 240 m is small enough that fenceline points still get the highest scores in the raster, but not so small that the result becomes singular. |
| Drop threshold | 0.5 (normalized) | Grid cells with normalized CIS < 0.5 are omitted from the rendered overlay. Keeps the overlay sparse in clean areas; visually emphasizes the burdened zones. |
| Grid resolution | ~0.01° (~1 km) | Compromise between fenceline detail and rendering cost (the raster is ~18,000 cells over Delaware's bbox, rebuilt on time-slider changes). |

**Distance metric.** `haversineKm()` in [index.html](index.html) returns *miles* despite its name (documented at [index.html:9001](index.html:9001)). Unit consistency is what matters: units cancel in the normalization step (§4).

---

## 4. Normalization

The raw score has no upper bound. It is normalized to a 0–10 scale by:

1. At application load time, compute `rawProximityCIS()` (with no wind adjustment) at every Delaware block-group geometric centroid
2. Sort and take the **95th percentile** of those scores → store as `CIS_P95`
3. For any query point, return `min(10, raw / CIS_P95 × 10)`

Implementation: [index.html:9037](index.html:9037), function `precomputeCISNorm()`.

A normalized score of 10 means "matches or exceeds the 95th-percentile block-group statewide." This anchors the 0–10 scale to a fixed Delaware-wide reference, comparable across years (see §5) and consistent with how EJScreen presents its percentile-based indicators.

**v1 limitation:** BG-centroid sampling underweights fenceline pockets in sparse rural BGs where the centroid is far from where people actually live. Population-weighted normalization is scheduled for a Tier 2 methodology version.

---

## 5. Time filter

The map's time slider passes a `year` parameter to `rawProximityCIS()`. When set:

- Only facilities with `founded ≤ year` contribute to the score
- Facilities missing a `founded` value are always included (null-safe behavior matching the choropleth's `_foundedFilter`)

`CIS_P95` (the normalization denominator) is computed once at load time using the **present-day** facility set. This is intentional: it means a 1950 normalized-CIS of 4 represents "the same absolute burden a 2026 score of 4 represents," not "burden relative to 1950's lower baseline." Cross-year comparison is the desired behavior.

---

## 6. Wind factor

As of v1.2 the wind factor has three modes, applied in priority order inside `rawProximityCIS()`:

**Mode 1 — Snapshot (`windFromDeg !== null`).** Used by the live wind toggle and the address-search popup so a resident can see "what's the burden right now given today's wind?" Same math as v1.0–v1.1:

```
wind_factor(facility) = 1 + 0.4 × cos(angle_diff(bearing_to_facility, windFromDeg))
```

Range: 0.6× (directly downwind) to 1.4× (directly upwind).

**Mode 2 — Chronic / wind rose (`windFromDeg === null` and `windRose` loaded).** Used by the static rendered grid and CIS_P95 normalization, so the published map reflects a 10-year climatology rather than a momentary snapshot. Frequency-weighted sum across a 16-direction wind rose:

```
wind_factor_chronic(bearing) = 1 + 0.4 × Σ_d freq[d] × cos(angle_diff(bearing, deg_center[d]))
```

where `freq[d]` is the directional frequency from the NOAA ISD wind rose at KILG (Wilmington/New Castle Airport, [noaa_wind_rose.json](noaa_wind_rose.json)). The factor is a stable per-(query→facility) scalar that doesn't change with the live weather.

**Mode 3 — Baseline (`windFromDeg === null` and rose not loaded).** Pure proximity, no directional adjustment. Equivalent to the v1.0 no-wind behavior; only used as a fallback if `noaa_wind_rose.json` failed to load.

Implementation: [index.html:9023-9087](index.html:9023). The data side-car is generated by `scripts/fetch_noaa_wind_rose.py` (10-year window, default 2015–2024).

**KILG climatology summary** (10y, n ≈ 99,800 directional + 11,500 calm observations):

| Direction | Frequency | Mean speed |
| --- | ---: | ---: |
| NW  | 9.92% | 5.0 m/s |
| S   | 9.10% | 3.9 m/s |
| WNW | 8.39% | 5.2 m/s |
| W   | 8.15% | 4.2 m/s |
| N   | 7.30% | 3.7 m/s |
| Other 11 bins (each <8%) | sum ≈ 57% | — |
| Calm (no direction) | 10.3% | — |

Predominant directions are NW and S, consistent with mid-Atlantic synoptic patterns: northwesterly behind cold-front passages, southerly ahead of low-pressure systems.

**v1.2 limitations:**

- **Single station.** KILG is the only NWS observation point in upstate Delaware. Downstate (Sussex County) sites will have somewhat different climatologies; the rose is applied uniformly statewide. A multi-station blend (KILG + KGED Georgetown) is a candidate v1.4 refinement.
- **No speed weighting.** The rose only weights by direction frequency; a facility upwind under low-frequency-but-high-speed conditions contributes the same as one upwind under high-frequency-but-low-speed conditions. Speed-weighted weighting (kinematic-flux-based) is a candidate v1.5 refinement.
- **No diurnal or seasonal variation.** A 10-year mean rose smooths over sea-breeze patterns and seasonal differences. For most chronic-burden purposes this is appropriate; for episodic exposure modeling it is not.

---

## 6c. Stack-height factor (v1.4+)

The IDW formula in §2 treats each facility as a point source at its coordinates. For ground-level fugitive sources that's reasonable. For tall stacks (refineries 60–100m, coal-plant stacks 80m+, large chemical-process stacks 30–60m) the assumption overstates near-fence ground-level concentration: the plume disperses higher and farther, so a fenceline resident gets less burden from a tall-stack source than from a ground-level fugitive source emitting the same mass.

v1.4 introduces a class-based dampener applied per facility inside `rawProximityCIS()` after the wind factor:

| Class | Multiplier | Typical examples |
| --- | ---: | --- |
| `tall_stack` | 0.7 | Petroleum refineries (60–100m), incinerators / cogeneration, coal/gas power plants, large chemical plants, fluorochemical / chlor-alkali process stacks, LNG flares, steel mills |
| `low_stack` | 0.85 | Specialty chemical plants (<25m), industrial gas plants, petroleum storage tanks, RCRA hazardous-waste treatment, former chemical plants with capped legacy vents |
| `ground_level` | 1.0 | CAFOs / poultry processing (fugitive ammonia + dust), traffic corridors, post-industrial reuse on contaminated land, vacancies / redevelopments, contractor operations, WWTP, landfills, former MGP, contaminated brownfields, military bases |

Each facility's `stack_height_class` and a one-line `stack_height_basis` citation are stored in [facilities.json](facilities.json) (added by `scripts/patch_facility_stack_height.py`). 18 of 54 Delaware-region facilities classify as tall_stack (refineries, large chemicals, power plants), 15 as low_stack, 21 as ground_level (Superfund, traffic, post-industrial reuse).

**Important caveat — what the dampener doesn't do.** A correct dispersion treatment would also SHIFT contribution downwind from the source: a 100m-stack refinery delivers more burden 5-10 km downwind than at the fence, because the plume has had time to descend and disperse over that distance. Our formula reduces near-fence contribution but doesn't add far-field contribution. This is a screening-grade approximation; AERMOD would be the regulatory-grade alternative (see roadmap Tier 3.3).

**Choice of multipliers.** The 0.7 / 0.85 / 1.0 trio is a defensible first-order approximation; literature reviews (EPA SCREEN3 docs, OEHHA stack-height guidance) suggest near-fence ground-level concentration is roughly 50–70% of a ground-level source's contribution at the same distance for stacks ≥30m. The 0.7 multiplier sits within that range. Sensitivity to this choice should be tested if a future audit raises concern.

---

## 7. Weighting rubric

Facility weights (range 1.2–3.0) are documented in [weighting_rubric.md](weighting_rubric.md), which defines six rubric tiers (3.0 / 2.5 / 2.0 / 1.8 / 1.5 / 1.2) and the inferred regulatory class for each facility.

In [facilities.json](facilities.json), each facility carries:

- `weight` — numeric value used in the formula (§2)
- `weight_tier` — closest rubric tier center, formalizing the assignment
- `weight_basis` — short citation (regulatory class, source, TRI ID where applicable)

Snap-rule rank correlation between `weight` and `weight_tier`: ρ = 0.992 (well above the 0.95 threshold required by the rubric).

**As of v1.1, weights are TRI-derived from a composite formula:**

```
weight = clamp(1.2, 3.0,
    base_tier × (1 + α · log10(1 + recent_5yr_avg_lbs / 1000))
              × (1 + β · HAP_flag)
              × (1 + γ · NAICS_high_risk_flag))
```

with α = 0.03, β = 0.05, γ = 0.05 (calibrated so the modifier maximum ~ 1.27 keeps the output within the original 1.2–3.0 rubric span). For 34 of 54 facilities with a `trifid` join, this replaces the v1.0 hand-curated value. The remaining 20 facilities (Superfund-only, traffic corridors, legacy contamination) keep the rubric tier weight unchanged and `weight_basis` flags this with `"|| rubric tier (no TRI match)"`.

**HAP detection** matches `top_chemicals.name` against ~45 keyword markers covering the substantial majority of Clean Air Act §112 HAPs that appear in DE/PA/NJ TRI submissions (benzene, formaldehyde, sulfuric acid, manganese, chromium, etc.). See `scripts/build_facility_weights.py` for the full keyword list.

**NAICS high-risk flag** triggers on prefixes 324 (petroleum/coal), 325 (chemicals), 331 (primary metals), 562 (waste management).

**Reproducibility.** Weights are deterministic from `tri_history.json`, `tri_facilities.json`, the keyword and NAICS lists, and the three coefficients. Per-facility provenance is written to `weight_provenance.csv` (one row, all inputs and the derived weight) every time the script runs. Re-running the script regenerates identical values.

```sh
python3 scripts/build_facility_weights.py            # dry-run + audit files
python3 scripts/build_facility_weights.py --patch    # write to facilities.json
```

**v1.1 limitation (resolved in v1.3):** total annual TRI release pounds entered the formula without pollutant-toxicity differentiation. A facility releasing 1M lb of low-toxicity solvent and a facility releasing 1M lb of HAP got the same `recent_5yr_avg_lbs` multiplier. v1.3 introduces multi-pollutant separation (see §7b) that allocates each TRI-matched facility's combined weight by its share of cancer-driver vs respiratory-driver air emissions.

## 7b. Multi-pollutant CIS variants (v1.3+)

The Facility Burden Index ships in three category variants, selectable from the segmented control under the floating "Facility burden" pill:

- **Combined** — every facility contributes via the rubric tier × TRI-derived multiplier (v1.0–v1.2 behavior). Default.
- **Cancer drivers** — only TRI-matched facilities with EPA-classified carcinogen air emissions in the recent 5-year window. Each such facility's combined weight is multiplied by its `cancer_air_lbs / total_air_lbs` share.
- **Respiratory drivers** — only TRI-matched facilities with respiratory-irritant air emissions (sulfuric acid mists, NOx, SO2, chlorine, hydrochloric acid, etc.). Same allocation logic against the curated respiratory CAS list.

**Allocation formula:**

```
weight_cancer       = weight_combined × (cancer_air_lbs_5yr / max(total_air_lbs_5yr, 1))
weight_respiratory  = weight_combined × (respiratory_air_lbs_5yr / max(total_air_lbs_5yr, 1))
```

A facility with no recent cancer-classified emissions gets `weight_cancer = 0` and is excluded from the cancer surface. Same for respiratory. The combined surface is unaffected.

**Chemical classification source:** `scripts/_chem_categories.py`. Cancer category combines TRI's `carc_ind=1` flag (EPA classification) with a curated CAS supplement covering well-documented carcinogens that older TRI submissions sometimes left unflagged (benzene, formaldehyde, ethylene oxide, vinyl chloride, asbestos, etc.). Respiratory category is a curated CAS list drawn from EPA IRIS RfC values, OEHHA RELs, and the criteria pollutants list.

**Per-category normalization:** each category has its own `CIS_P95_BY_CAT[cat]` value computed at load time across all BG centroids. Without per-category normalization, the cancer surface (sparser — fewer contributing facilities) would render systematically pale against the combined surface even at fenceline locations.

**Limitations specific to v1.3:**

- **Non-TRI facilities don't appear in cancer/respiratory.** Superfund-only sites, traffic corridors, and legacy contamination get `weight_cancer = weight_respiratory = null`. They're documented as contributors only to the combined surface. A future refinement (v1.4+) could allow hand-flagging of category contribution for sites with documented contamination types (e.g., Citisteel for Cr(VI) → cancer).
- **Air emissions only.** Category allocation uses `stack_tot_rel + fugitive_tot_rel`, ignoring water/landfill/transfer pathways. Defensible for proximity-mediated air-burden scoring but not for community drinking-water or food-chain pathway analysis.
- **No toxicity weighting within category.** A facility releasing 100 lb of benzene and a facility releasing 100 lb of formaldehyde are weighted identically under the cancer category. Toxicity-weighted scoring (using IRIS IUR or OEHHA cancer slope factors) is a candidate v1.5 refinement.
- **5-year window.** Category allocation uses TRI 2020-2024 data. Pre-2015 emissions are not retro-allocated; older closed facilities (pre-2020) get 0 in their category share.

---

## 8. Sensitivity analysis

Decay-exponent sensitivity is the most-asked question; if the result depends sharply on the choice of 1.5, the headline scores would not be defensible.

To test, the tool's CIS is recomputed at every Delaware BG centroid for `decay ∈ {1.0, 1.25, 1.5, 1.75, 2.0}` and Spearman rank correlation is taken between each variant and the production decay (1.5). Reproducible via `scripts/audit_cis_sensitivity.py`.

| Decay | Spearman ρ vs production (1.5) | Interpretation |
| --- | --- | --- |
| 1.0 | 0.980 | Regional-dispersion emphasis |
| 1.25 | 0.995 | Mild regional emphasis |
| **1.5** | **1.000** (production) | Production parameter |
| 1.75 | 0.995 | Mild local emphasis |
| 2.0 | 0.983 | Hyper-local emphasis |


**Result:** all variant decays show ρ ≥ 0.980 against the production decay (1.5) across 700 Delaware block-group centroids. The rank-order of burdened communities is **robust** to the choice of decay within the standard IDW range; the headline result does not depend on the parameter choice.

**Interpretation rule:** if all reported ρ ≥ 0.95, the rank-order of burdened communities is robust to the choice of decay within the standard IDW range, and the headline result does not depend on the parameter choice. If any reported ρ < 0.95, the methodology must explicitly disclose where the rank-order changes and why.

---

## 8b. Empirical validation against observed health prevalence

A tract-level Spearman correlation analysis between CIS and CDC PLACES 2025 prevalence has been published at [analyses/cis_places_correlation_2026.md](analyses/cis_places_correlation_2026.md). Headline findings, after stratifying for the dominant age confounder:

- Among Delaware's most SES-vulnerable tracts (Q4 SES, n = 64), higher CIS is positively associated with diabetes (ρ = +0.45), poor mental-health days (ρ = +0.35), stroke (ρ = +0.32), and obesity (ρ = +0.28).
- Poor mental-health prevalence (MHLTH) is the most-robust positive finding overall (ρ = +0.28, 95% CI [+0.16, +0.41]) and remains positive across multiple SES and age strata. Consistent with peer-reviewed literature on industrial-proximity psychosocial burden.
- Raw chronic-disease correlations (CANCER, CHD, BPHIGH, COPD, STROKE) are negative in the unstratified analysis but this is overwhelmingly age confounding — CDC PLACES tract values are crude prevalence and Delaware's lowest-CIS tracts are Sussex retirement communities. Age-stratified results recover or attenuate the demographic artifact.
- The analysis cannot prove causation; ecological-level association is the ceiling. Confirmation requires monitor-data correlation (Tier 3.2) and AERMOD calibration (Tier 3.3).

## 9. Limitations

The CIS is a screening proxy. Specifically:

- **No atmospheric dispersion physics.** Real exposure depends on stack height, plume buoyancy, mixing height, atmospheric stability class, and pollutant decay/transformation rates. AERMOD or similar regulatory tools model these; the CIS does not. The CIS is in the same family of math as EJScreen's proximity indicators, not as AERMOD's concentration estimates.
- **No pollutant differentiation.** All facilities sum into one score. A facility emitting benzene (cancer driver) and one emitting PM2.5 (respiratory driver) contribute identically per unit weight.
- **Wind snapshot, not climatological.** §6 limitation.
- **BG-centroid normalization.** §4 limitation.
- **1 km grid resolution.** Coarse for fenceline-level claims about specific dwellings.
- **No uncertainty bands.** A score of 7.2 is presented as cleanly distinct from 6.8; uncertainty in the underlying weight choices and distance approximations is not propagated to error bars in v1.
- **Static weighting in v1.** Weights are time-invariant; a facility that has reduced emissions over decades carries the same weight as one that hasn't. Tier 2.1 (TRI-derived weights) addresses this by using recent-5yr-average release pounds.
- **Hand-curated facility list.** [facilities.json](facilities.json) is hand-maintained. Sources missing from the list (e.g., upstream facilities in Maryland or further into Pennsylvania, smaller permitted sources below the team's curation threshold) do not contribute. `verify_facilities.py` cross-checks coordinates against EPA ECHO; that does not address completeness, only positional accuracy of included entries.

---

## 10. Precedent and citation

The CIS sits in the established family of EJ-screening proximity indicators. In particular:

- **EPA EJScreen Technical Documentation v2.3 §4.2** — defines the proximity indicators (Risk Management Plan facility proximity, Treatment/Storage/Disposal facility proximity, NPL Superfund proximity, traffic proximity) using analogous inverse-distance approaches with their own decay treatments. The CIS combines the same family of math across all permitted sources rather than reporting them as separate indicators. See: <https://www.epa.gov/ejscreen/technical-documentation-ejscreen>
- **CalEnviroScreen 4.0 methodology** — California's analogous tool; uses different specific math (population-weighted) but the same basic premise that proximity to permitted sources is a defensible burden indicator.

When citing CC4EJ Facility Burden Index values in external work:

> *Facility burden values from CC4EJ Cumulative Impacts Map (CC4EJ, 2026), Methodology v1.0; weights per CC4EJ Weighting Rubric v1.0. Underlying formula and parameters documented at <https://cc4ej.org/METHODOLOGY> (or equivalent in the repo).*

---

## 11. Versioning

This document is part of a versioned methodology that updates with each substantive change to the formula, parameters, weights, normalization, or wind treatment.

Current version: **v1.4** (2026-05-07). Stack-height class dampener (§6c) — refineries, incinerators, power plants, and large chemical plants get a 0.7× multiplier on their proximity contribution; low-stack permitted sources get 0.85×; ground-level / fugitive / contamination sites stay at 1.0×. Reduces over-attribution of near-fence burden from tall-stack sources; AERMOD remains the regulatory-grade alternative.

Previous: **v1.3** (2026-05-07). Multi-pollutant CIS variants (§7b) — combined / cancer drivers / respiratory drivers, selectable from a segmented control under the floating pill.

Previous: **v1.2.1** (2026-05-07). CIS math extracted into [js/cis.js](js/cis.js) with a Node-based parity test against the Python reference.

Previous: **v1.2** (2026-05-06). Chronic wind-rose factor (§6) replacing the snapshot-only behavior of v1.0–v1.1.

Planned future version bumps (per the roadmap):

- **v1.5** — Speed-weighted wind rose (kinematic-flux refinement)
- **v1.6** — Toxicity-weighted within-category scoring (IRIS IUR / oral slope factors)
- **v2.0** — Population-weighted normalization (Tier 2.5)

See [CHANGELOG.md](CHANGELOG.md) for the authoritative version log.

---

## Files referenced by this methodology

- [index.html](index.html) — production CIS implementation, lines 2989-9099
- [facilities.json](facilities.json) — facility list with weights, tiers, bases, founded years
- [weighting_rubric.md](weighting_rubric.md) — tier rubric source-of-truth
- `facility_weight_tiers.csv` — generated audit trail for tier assignments
- [scripts/patch_facility_weight_tier.py](scripts/patch_facility_weight_tier.py) — patcher
- `scripts/audit_cis_sensitivity.py` — sensitivity analysis (Tier 1.4 of roadmap, populates §8)
- [CHANGELOG.md](CHANGELOG.md) — version history (Tier 4.3 of roadmap)
