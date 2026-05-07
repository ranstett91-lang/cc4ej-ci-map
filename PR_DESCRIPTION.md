# Facility Burden Index (CIS) Methodology v1.0 → v2.0

A complete defensibility upgrade for the CIS / "Exposure Surface" overlay on cc4ej.org. Converts the index from an advocacy tool with hand-curated weights into a documented, reproducible, parity-tested screening proxy with empirical validation and a 2-page methodology document. **Same math at the core where it works; far better defenses around it.**

## Branch

`claude/ecstatic-snyder-bee91a` → `main`

## Summary

| | Before | After |
| --- | --- | --- |
| **Methodology document** | None | [METHODOLOGY.md](METHODOLOGY.md), 11 sections, ~9 KB |
| **Weighting rubric** | Hand-curated, 1.2–3.0 with no published basis | TRI-derived composite (rubric tier × log emissions × HAP × NAICS), `weight_provenance.csv` per facility |
| **Wind treatment** | Snapshot only (whatever the last weather fetch returned) | 10-year NOAA ISD climatology at KILG, chronic by default + snapshot when toggled |
| **CIS variants** | One surface | Three: Combined / Cancer drivers / Respiratory drivers, with EPA-flag-based chemical classification |
| **Stack-height treatment** | None — every facility a point source | Heuristic class dampener (refineries × 0.7, low-stack × 0.85, ground-level × 1.0) |
| **0-10 normalization** | 95th percentile by BG count (a 200-resident BG and a 5,000-resident BG counted equally) | Population-weighted percentile — anchored to "5% of *residents* live where CIS ≥ P95" |
| **Source of truth** | Inline JS in 9000-line `index.html` | Standalone `js/cis.js` + Python reference `scripts/_cis_stats.py` + parity test `scripts/test_cis_parity.py` |
| **Empirical validation** | None | Tract-level CDC PLACES correlation (n=257) + EPA AQS monitor correlation (n=11) |
| **Version log** | None | `CHANGELOG.md` with 7 entries |
| **Tagging plan** | N/A | Documented in `CHANGELOG.md` for post-merge `methodology-v1.0` … `methodology-v2.0` tags |

## Commits in this PR (chronological)

1. **`0bc507c` Add Facility Burden Index methodology (v1.0–v1.2)** — rubric, TRI-derived weights, wind rose, PLACES validation, user-facing rename "Exposure Surface" → "Facility Burden Index"
2. **`0a08dab` Harden service-worker cache fallback on HTTP 5xx** — audit fix; Vercel deploy windows no longer break cached users
3. **`3864db9` Methodology v1.2.1: extract CIS module + JS↔Python parity test** — single source of truth for production math
4. **`93d1620` Methodology v1.3: multi-pollutant CIS variants** — Combined / Cancer / Respiratory split with chemical classifier
5. **`0974f4d` Methodology v1.4: stack-height dampener for tall-source facilities** — refineries no longer over-attributed at fenceline
6. **`815ac71` Methodology v2.0: population-weighted P95 normalization (major bump)** — 0–10 scale anchored to where people actually live
7. **`adf8ba9` Tier 3.2: empirical validation against EPA AQS monitor data** — directional validation against measured air quality
8. **`8b2b7d3` Refresh in-app methodology section for v2.0** — site visitors clicking "How is this calculated?" see the v2.0 picture

## What's reproducible from public inputs alone

```sh
# Re-derive every facility weight from EPA TRI public records:
python3 scripts/fetch_tri_history.py
python3 scripts/fetch_tri_chemical_history.py --years 2020-2024
python3 scripts/patch_facility_weight_tier.py --apply --csv
python3 scripts/build_facility_weights.py --patch
python3 scripts/build_facility_weights_v13.py --patch
python3 scripts/patch_facility_stack_height.py --apply

# Re-derive the wind rose climatology:
python3 scripts/fetch_noaa_wind_rose.py --years 2015-2024

# Re-run the empirical validation analyses:
python3 scripts/build_places_tracts.py
python3 scripts/analyze_cis_places.py
python3 scripts/fetch_epa_aqs_monitors.py --years 2018-2024
python3 scripts/analyze_cis_monitors.py

# Verify JS↔Python math parity (75 points × 3 categories + P95):
python3 scripts/test_cis_parity.py --tol 1e-9
```

Every weight, every score, every confidence interval is reproducible from the EPA TRI database, NOAA ISD, CDC PLACES, EPA AQS, and US Census ACS — all public.

## Headline empirical findings

**Tract-level CIS × CDC PLACES health prevalence (n = 257 DE tracts):**

- Among Delaware's most SES-vulnerable tracts (Q4 SES, n=64): higher CIS positively associates with diabetes (ρ = +0.45), poor mental-health days (+0.35), stroke (+0.32), obesity (+0.28).
- **MHLTH** (poor mental-health days) is the most-robust positive finding overall — ρ = +0.28, 95% CI [+0.16, +0.41]. Consistent with peer-reviewed literature on the psychological burden of living near industrial facilities.
- Negative chronic-disease correlations in the unstratified analysis (CANCER, CHD, BPHIGH, COPD, STROKE) are demographic confounding (Sussex retirement tracts skew old, NCC industrial corridor skews young; PLACES uses crude prevalence). Disclosed transparently in the report.

**Direct CIS × EPA AQS monitor correlation (n = 11 DE monitors):**

- PM2.5 (n=7): ρ = +0.14 — directionally consistent with prediction.
- SO2 (n=5): ρ = +0.10 — directionally consistent.
- O3 (n=7): ρ = −0.45 — inverse, consistent with NOx-titration chemistry near urban industrial sources. Not a contradiction.
- NO2/CO have only 1 monitor each in DE; correlation undefined.
- Sample size limits power; report avoids "statistically significant" framing in favor of direction-of-effect testing.

Both reports published regardless of result direction. No cherry-picking.

## Verification (already done by Claude before this PR)

- ✅ JS↔Python parity test passes at tolerance 1e-9 across **75 test points × 3 categories × 3 wind modes** (max |Δ| = 1.6 × 10⁻¹², machine precision)
- ✅ P95 weighted percentile parity: JS and Python identical to 12 decimal places across 700 BGs
- ✅ Decay-sensitivity rank correlation ρ ≥ 0.98 across decay 1.0–2.0 (the headline rank-order is robust to the IDW choice)
- ✅ Snap-rule rank correlation between numeric weight and rubric tier ρ = 0.977 (>0.95 threshold)
- ✅ Inline JS in index.html parses cleanly under Node `--check`
- ✅ Backward compatibility: facilities without TRI matches keep their rubric tier weight; site degrades gracefully if `noaa_wind_rose.json` or `places_tracts.json` fail to load
- ✅ Code audit run on the diff — three real bugs found (spearman degenerate-case inconsistency, HAP keyword false-positive, sw.js 5xx fallback gap) and all three fixed

## Pre-merge smoke-tests for reviewers

1. **Run a local server:** `python3 -m http.server 8000` and open <http://localhost:8000/>
2. **Toggle the floating "Facility burden" pill** — confirm the segmented `All / Cancer / Respiratory` control appears below it
3. **Click each category button** — the grid should rebuild for the new variant; for Cancer and Respiratory the surface is sparser (fewer facilities contribute) and the per-category P95 normalization keeps the colors meaningful
4. **Open the Methods modal (📚 button)** → "How Facility Burden Index (CIS) is scored" — confirm it describes v2.0 with the variants, wind rose, stack-height factor, and links to the analyses
5. **Click any block group** — the popup should still show CIS readings; values shift slightly versus pre-PR (~5% higher across the map due to v2.0 population-weighting), but rank-order is unchanged
6. **Run `python3 scripts/test_cis_parity.py --tol 1e-9`** — should print "PASS" on both the 75-point CIS battery and the 700-BG P95 parity check; takes ~3 seconds
7. **Spot-check `weight_provenance.csv` and `facilities.json` `weight_basis` lines** against your domain knowledge — anything mis-classified for stack-height, regulatory class, or category allocation?

## Tagging plan after merge

```sh
# After merging this PR to main:
git tag -a methodology-v1.0 0bc507c -m "Initial published methodology"
git tag -a methodology-v1.1 0bc507c -m "TRI-derived weights"
git tag -a methodology-v1.2 0bc507c -m "Chronic wind-rose factor"
git tag -a methodology-v1.2.1 3864db9 -m "Standalone CIS module + parity test"
git tag -a methodology-v1.3 93d1620 -m "Multi-pollutant CIS variants"
git tag -a methodology-v1.4 0974f4d -m "Stack-height dampener"
git tag -a methodology-v2.0 815ac71 -m "Population-weighted normalization"
git push --tags
```

(The first three tags can co-locate on `0bc507c` because v1.0/v1.1/v1.2 landed in a single commit — CHANGELOG.md is the authoritative version log.)

## Limitations — disclosed in METHODOLOGY.md, summarized here

- CIS is a **screening proxy**, not a measured pollutant concentration. AERMOD remains the regulatory-grade alternative.
- TRI-derived weights use **air emissions only** (stack + fugitive). Water/landfill/transfer pathways aren't allocated.
- **No within-category toxicity weighting** in v2.0. 100 lb of benzene and 100 lb of formaldehyde count equally in the cancer surface. Roadmap candidate v2.1.
- **Single met station** (KILG) for the wind rose. Sussex County downstate has somewhat different climatology not yet reflected.
- **Stack-height classes are heuristic** from the `type` field, not measured stack heights from DNREC permits.
- **AQS monitor correlation has tiny n** (5–7 per parameter). A stronger empirical defense requires Delaware's monitor network to grow OR cross-state airshed pooling.
- **CDC PLACES is crude prevalence**, not age-adjusted. Chronic-disease correlations are confounded by Delaware's age structure (retirement coast vs urban industrial). Documented in the analysis report.

## What's NOT in this PR

- **AERMOD calibration** (Tier 3.3 of the original roadmap) — partner-dependent (UDel/Drexel collaboration or paid air-quality consultant). Tracked in NEXT_STEPS.md as future work.
- **External peer review** (Tier 4.1) — partner-dependent. Tracked in NEXT_STEPS.md.
- **Speed-weighted wind rose** (v2.1 candidate) — refinement; current chronic rose is already a major upgrade over snapshot.
- **Toxicity-weighted within-category scoring** (v2.2 candidate) — would need IRIS IUR / RfC lookup table.
- **Dasymetric within-BG sampling** (v2.3 candidate) — fine-grained refinement; Delaware's 700 BGs are already small enough that the centroid approximation is fine for most communities.

## Files changed in this PR

**New files (24):**
- `METHODOLOGY.md`, `CHANGELOG.md`, `weighting_rubric.md`, `PR_DESCRIPTION.md`
- `js/cis.js`
- `scripts/_cis_stats.py`, `scripts/_chem_categories.py`
- `scripts/patch_facility_weight_tier.py`, `scripts/build_facility_weights.py`, `scripts/build_facility_weights_v13.py`, `scripts/patch_facility_stack_height.py`
- `scripts/audit_cis_sensitivity.py`, `scripts/analyze_cis_places.py`, `scripts/analyze_cis_monitors.py`
- `scripts/fetch_noaa_wind_rose.py`, `scripts/fetch_tri_chemical_history.py`, `scripts/fetch_epa_aqs_monitors.py`
- `scripts/test_cis_parity.py`
- `noaa_wind_rose.json`, `tri_chemical_history.json`, `air_monitors.json`, `facility_weights.json`, `facility_weight_tiers.csv`, `weight_provenance.csv`
- `analyses/cis_places_correlation_2026.md`, `analyses/cis_monitor_correlation_2026.md`

**Modified files:**
- `index.html` — UI rename, methodology section refresh, segmented category control, wind-rose integration, stack-height dampener, population-weighted P95, internal comment consistency
- `facilities.json` — `weight_tier`, `weight_basis`, `weight_by_category`, `stack_height_class`, `stack_height_basis` on every feature; numeric `weight` updated by build script
- `places_tracts.json` — populated from CDC PLACES (was an empty stub)
- `data_sources.md`, `README.md` — link-outs to METHODOLOGY.md
- `sw.js` — 5xx cache fallback, KEEP_CACHES set, comment clarification
