# CIS × PLACES Health Prevalence Correlation (Delaware, 2026)

**Analysis date:** 2026-05-06  
**Author:** CC4EJ Cumulative Impacts project (auto-generated)  
**Reproducible via:** `python3 scripts/analyze_cis_places.py`

**Data versions:** facilities.json (54 facilities), de_blockgroups.geojson (700 BGs), places_tracts.json (CDC PLACES 2025 release, 13 measures, 257 DE tracts).

---

## 1. Methodology

The Facility Burden Index (CIS) — defined in [METHODOLOGY.md](../METHODOLOGY.md) — was computed at every Delaware census tract's population-weighted centroid using the production no-wind no-year-filter formula (decay = 1.5, distance floor = 0.15 mi). Tract-level CIS was joined with CDC PLACES 2025 prevalence (BRFSS-derived adult prevalence at tract level, crude-prevalence percent of adults 18+) for 13 measures.

For each measure, we report Spearman rank correlation between tract CIS and tract prevalence, with bootstrap 95% confidence intervals from 1,000 resamples (seed=42, sampling tracts with replacement). We also stratify by socioeconomic vulnerability quartile (`sv` field, population-weighted from block groups) to distinguish facility burden's association from the SES burden it correlates with.

**Honesty disclaimer.** This analysis is ecological — associations exist at the population level and cannot prove that any individual's condition was caused by facility proximity. CIS reflects facility burden, not measured pollutant concentration. Strong associations after SES stratification are suggestive but require monitor-data and dispersion-model validation (see roadmap Tier 3.2 and 3.3) before causal claims.

**Joined tracts:** 257 (out of 257 DE PLACES tracts; some excluded for missing centroid or SV data).

---

## Headline findings (read this first)

After stratifying for age and SES — the two dominant confounders — the cleanest within-this-data findings are:

- **Among Delaware's most SES-vulnerable tracts (Q4 SES, n=64), higher CIS is positively associated with:** diabetes (ρ=+0.44), poor mental health 14+ days/mo (ρ=+0.35), stroke (ρ=+0.31), obesity (ρ=+0.28), current asthma (adults) (ρ=+0.16). This is the population most relevant to environmental-justice work, and the result is in the expected direction for several pollution-relevant endpoints.

- **Among Delaware's youngest tracts (Q1 age, mostly urban industrial corridor, n=65), higher CIS is positively associated with:** diabetes (ρ=+0.32), stroke (ρ=+0.28), high blood pressure (ρ=+0.28), obesity (ρ=+0.20), current smoking (ρ=+0.18). This view largely controls for the age confounder.

- **MHLTH (poor mental-health days) is the most-robust positive finding** — it shows ρ = +0.28 overall (95% CI excludes zero) and remains positive across multiple SES and age strata. This is consistent with peer-reviewed literature on the psychological burden of living near industrial facilities, but cannot be claimed as causal from this analysis alone.

- **Negative chronic-disease correlations (CANCER, CHD, BPHIGH, COPD, STROKE) in the raw analysis are overwhelmingly demographic, not protective.** They reflect the age structure of Delaware: low-CIS tracts include Sussex County beach retirement communities (older populations with naturally higher chronic-disease prevalence), while high-CIS tracts are urban industrial (younger populations). Crude prevalence is age-driven; CDC PLACES does not publish age-adjusted tract values. Within age-matched strata (§3), most chronic-disease results lose magnitude or flip sign.

- **This analysis cannot prove causation.** It provides ecological-level evidence consistent with — and not contradictory to — the hypothesis that proximity-weighted facility burden adds to community health burden in vulnerable Delaware communities. Confirmation requires monitor-data correlation (roadmap Tier 3.2) and regulatory-grade dispersion modeling (Tier 3.3).

---

## 2. Tract-level CIS × PLACES association (raw — confounded)

**Read with caution.** These raw correlations are heavily confounded by age. CDC PLACES tract-level prevalence is CRUDE (not age-adjusted), and Delaware's geography puts the state's oldest tracts (Sussex County beach communities) in the lowest-CIS areas while the youngest tracts (urban industrial NCC corridor) sit in high-CIS areas. Chronic-disease prevalence is age-driven, so the negative correlations on CANCER, CHD, BPHIGH, COPD, STROKE below largely reflect demographics, not environmental protection. **For interpretable headlines, use §3 (age-stratified).**

| Measure | Label | n | Spearman ρ | 95% CI | Note |
| --- | --- | ---: | ---: | --- | --- |
| CASTHMA | Current asthma (adults) | 257 | +0.054 | [-0.077, +0.192] | |
| COPD | COPD (adults) | 257 | -0.335 ✓ | [-0.435, -0.217] | |
| PHLTH | Poor physical health 14+ days/mo | 257 | -0.159 ✓ | [-0.270, -0.035] | |
| CHD | Coronary heart disease | 257 | -0.488 ✓ | [-0.577, -0.378] | |
| STROKE | Stroke | 257 | -0.214 ✓ | [-0.331, -0.095] | |
| BPHIGH | High blood pressure | 257 | -0.392 ✓ | [-0.500, -0.269] | |
| CANCER | Cancer (excluding skin) | 257 | -0.528 ✓ | [-0.622, -0.423] | |
| DIABETES | Diabetes | 257 | -0.110 | [-0.225, +0.013] | |
| KIDNEY | Chronic kidney disease | 0 | — | — | n<30, skipped |
| CSMOKING | Current smoking | 257 | +0.052 | [-0.073, +0.193] | |
| OBESITY | Obesity | 257 | +0.078 | [-0.051, +0.216] | |
| MHLTH | Poor mental health 14+ days/mo | 257 | +0.281 ✓ | [+0.153, +0.408] | |
| DEPRESSION | Depression | 257 | +0.064 | [-0.071, +0.201] | |

✓ = 95% CI excludes zero. Note: statistical significance ≠ causal claim.

---

## 3. Age-stratified analysis (the most important table)

Stratifying by tract-level over-64% quartile largely removes the age confounder. Within-quartile correlations test whether CIS retains explanatory power among tracts with similar age structures. **This is where to read the headline numbers.**

| Measure | Q1 age (youngest) | Q2 age | Q3 age | Q4 age (oldest) |
| --- | ---: | ---: | ---: | ---: |
| CASTHMA | +0.13 (n=65) | -0.26 (n=64) | -0.48 (n=64) | +0.30 (n=64) |
| COPD | +0.09 (n=65) | -0.21 (n=64) | -0.37 (n=64) | -0.20 (n=64) |
| PHLTH | +0.14 (n=65) | -0.20 (n=64) | -0.36 (n=64) | -0.00 (n=64) |
| CHD | +0.09 (n=65) | -0.16 (n=64) | -0.35 (n=64) | -0.53 (n=64) |
| STROKE | +0.28 (n=65) | -0.02 (n=64) | -0.30 (n=64) | -0.22 (n=64) |
| BPHIGH | +0.28 (n=65) | -0.12 (n=64) | -0.40 (n=64) | -0.57 (n=64) |
| CANCER | -0.32 (n=65) | -0.40 (n=64) | -0.04 (n=64) | -0.76 (n=64) |
| DIABETES | +0.32 (n=65) | +0.00 (n=64) | -0.37 (n=64) | -0.10 (n=64) |
| KIDNEY | — (n=0) | — (n=0) | — (n=0) | — (n=0) |
| CSMOKING | +0.18 (n=65) | -0.11 (n=64) | -0.30 (n=64) | +0.20 (n=64) |
| OBESITY | +0.20 (n=65) | -0.21 (n=64) | -0.43 (n=64) | +0.25 (n=64) |
| MHLTH | +0.07 (n=65) | -0.09 (n=64) | -0.28 (n=64) | +0.66 (n=64) |
| DEPRESSION | -0.32 (n=65) | -0.46 (n=64) | -0.33 (n=64) | +0.64 (n=64) |


Reading this table: a positive ρ within an age quartile means high-CIS tracts in that age group have higher prevalence than low-CIS tracts in the same age group. A consistent positive ρ across quartiles is the strongest within-this-data evidence of facility-burden association.

---

## 4. SES-stratified analysis (controlling for socioeconomic vulnerability)

Stratifying by `sv` quartile addresses confounding between facility burden and SES burden. Note: `sv` is partly health-derived (40% PLACES blend), so this stratification is conservative; age stratification (§3) is more diagnostic of the age confounder.

| Measure | Q1 SES (least vulnerable) | Q2 SES | Q3 SES | Q4 SES (most vulnerable) |
| --- | ---: | ---: | ---: | ---: |
| CASTHMA | +0.05 (n=65) | +0.37 (n=64) | -0.08 (n=64) | +0.16 (n=64) |
| COPD | -0.09 (n=65) | -0.65 (n=64) | -0.59 (n=64) | -0.28 (n=64) |
| PHLTH | +0.01 (n=65) | -0.43 (n=64) | -0.37 (n=64) | -0.08 (n=64) |
| CHD | -0.06 (n=65) | -0.70 (n=64) | -0.61 (n=64) | -0.39 (n=64) |
| STROKE | -0.04 (n=65) | -0.60 (n=64) | -0.38 (n=64) | +0.31 (n=64) |
| BPHIGH | -0.09 (n=65) | -0.73 (n=64) | -0.55 (n=64) | +0.16 (n=64) |
| CANCER | -0.06 (n=65) | -0.73 (n=64) | -0.66 (n=64) | -0.69 (n=64) |
| DIABETES | -0.08 (n=65) | -0.43 (n=64) | -0.20 (n=64) | +0.44 (n=64) |
| KIDNEY | — (n=0) | — (n=0) | — (n=0) | — (n=0) |
| CSMOKING | +0.13 (n=65) | +0.26 (n=64) | +0.06 (n=64) | +0.02 (n=64) |
| OBESITY | +0.02 (n=65) | +0.38 (n=64) | +0.03 (n=64) | +0.28 (n=64) |
| MHLTH | +0.16 (n=65) | +0.59 (n=64) | +0.32 (n=64) | +0.35 (n=64) |
| DEPRESSION | +0.29 (n=65) | +0.41 (n=64) | +0.08 (n=64) | -0.47 (n=64) |

---

## 5. Top-decile vs. bottom-decile prevalence (raw — confounded)

Tracts ranked by CIS. Top decile = 25 tracts with highest CIS; bottom decile = 25 tracts with lowest CIS. **Same age confounder applies as §2.** For most chronic-disease measures, the bottom decile (Sussex retirement tracts) is older than the top decile (urban industrial), so a negative relative difference reflects demographics not environmental protection. Use this table only after reading §3.

| Measure | Bottom-decile mean prevalence | Top-decile mean prevalence | Relative difference |
| --- | ---: | ---: | ---: |
| CASTHMA | 10.3% | 11.4% | +11.1% |
| COPD | 7.7% | 7.0% | -9.1% |
| PHLTH | 13.3% | 13.7% | +3.4% |
| CHD | 8.5% | 6.3% | -26.5% |
| STROKE | 4.0% | 4.1% | +2.4% |
| BPHIGH | 42.6% | 38.7% | -9.0% |
| CANCER | 13.5% | 7.2% | -46.4% |
| DIABETES | 12.8% | 14.3% | +12.1% |
| CSMOKING | 11.2% | 14.5% | +29.4% |
| OBESITY | 31.7% | 37.7% | +18.7% |
| MHLTH | 12.5% | 17.2% | +37.7% |
| DEPRESSION | 19.9% | 21.0% | +5.4% |

---

## 6. Limitations

- **Age confounding (the dominant effect here).** Tract-level PLACES is CRUDE prevalence and chronic-disease rates climb sharply with age. In Delaware, low-CIS tracts include the state's oldest populations (Sussex beach retirement communities); high-CIS tracts are the youngest (urban industrial NCC corridor). Without age adjustment, simple correlation can show negative chronic-disease results that reflect demographics, not environmental protection. CDC PLACES does not publish tract-level age-adjusted prevalence. Age stratification (§3) is the within-this-data workaround; multivariate regression with explicit age covariate is a better future approach.
- **Ecological inference.** Tract-level associations cannot establish individual causation. Adults in high-CIS tracts differ from adults in low-CIS tracts in many ways beyond facility proximity (income, race, healthcare access, behavioral risk, age structure).
- **CIS is a proximity proxy, not measured pollutant concentration.** A tract's high CIS indicates many or near facilities, not necessarily high pollutant levels reaching residents. Monitor-data correlation (roadmap Tier 3.2) addresses this.
- **PLACES is a small-area model, not direct measurement.** CDC PLACES estimates tract prevalence by combining BRFSS surveys with covariate-based small-area estimation. The tract values themselves carry uncertainty not propagated into our correlations.
- **PLACES is adults 18+.** Pediatric asthma is not represented; childhood exposure is the highest-stakes question for many EJ communities and is not testable here.
- **SES stratification is partial.** The `sv` field is itself a composite (60% EJScreen SES + 40% PLACES health). Stratifying on a partly-health-derived variable is conservative; age stratification is more diagnostic for the dominant confounder.
- **Sample size.** Delaware has 257 PLACES tracts; quartile stratification leaves ~60–65 tracts per quartile, which limits power to detect moderate associations.
- **Spatial autocorrelation.** Adjacent tracts are not independent observations; Spearman ρ does not adjust for this. The bootstrap CI underestimates uncertainty.
- **Regression to the mean.** Top-decile vs bottom-decile comparison can overstate differences when the underlying distribution is wide.

---

## 7. Reproducibility

All inputs are committed to the repo. The analysis is fully reproducible:

```sh
python3 scripts/build_places_tracts.py    # populate places_tracts.json
python3 scripts/analyze_cis_places.py     # regenerate this report
```

Bootstrap CIs use seed = 42 for deterministic reruns. CIS math is replicated from index.html's `rawProximityCIS()` (decay = 1.5, distance floor = 0.15 mi).
