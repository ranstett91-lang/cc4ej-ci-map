# CIS × EPA AQS Monitor Correlation (Delaware, 2026)

**Analysis date:** 2026-05-07  
**Reproducible via:** `python3 scripts/analyze_cis_monitors.py`

**Data versions:** 11 DE monitors over years 2018-2024; facilities.json with v2.0 weights; CIS computed at each monitor's coordinates with the no-wind/chronic-rose default.

---

## Headline

If the CIS captures real proximity-mediated air burden — and not just an opinion about which neighborhoods have the most facility density — we'd expect monitors near high-CIS locations to register higher annual mean concentrations of facility-emitted criteria pollutants. This analysis tests that prediction directly against EPA AQS pre-generated annual-mean concentrations at all 11 active EPA AQS monitor sites in Delaware.

**Sample-size caveat (read first).** Delaware has 11 active EPA AQS monitors total. For O3 and PM2.5 (the two most-deployed parameters), n = 7. For SO2, n = 5. For NO2 and CO, n = 1 (single monitor; correlation is undefined). Spearman ρ at n = 5–7 has very wide confidence intervals; we report observed ρ but explicitly avoid 'statistically significant' language. The headline framing is **direction of effect**, not p-values.

---

## Spearman correlation (CIS vs annual mean concentration)

| Parameter | n | Observed ρ | Expected sign | Direction matches? | Note |
| --- | ---: | ---: | ---: | --- | --- |
| PM2.5 (local conditions) | 7 | +0.143 | +1 | ✓ yes |  |
| Nitrogen dioxide (NO2) | 1 | — | +1 | — | n<4, skipped — not enough monitors measure this in DE |
| Ozone (O3) | 7 | -0.450 | +1 | ✗ no |  |
| Sulfur dioxide (SO2) | 5 | +0.100 | +1 | ✓ yes |  |
| Carbon monoxide (CO) | 1 | — | +1 | — | n<4, skipped — not enough monitors measure this in DE |

Direction match means: observed ρ has the same sign as the directional hypothesis (positive correlation between CIS and concentration for facility-emitted pollutants).

---

## Per-monitor data (for transparency)

CIS values are RAW (un-normalized) production scores at each monitor's coordinates. Higher = more facility burden in proximity. Concentrations are annual arithmetic means averaged across the 2018-2024 window where data is available.

### PM2.5 (local conditions) (n = 7, units μg/m³)

| Site | CIS (raw) | Mean concentration |
| --- | ---: | ---: |
| Bellefonte River Road Park | 10.27 | 6.556 |
| MLK  CORNER OF MLK BLVD AND JUSTISON ST | 5.98 | 7.186 |
| PLATFORM IN FIELD BEHIND DELAWARE FED. CREDIT UNIO | 5.81 | 5.660 |
| Seaford Shipley State Service Center | 3.03 | 6.121 |
| Lums Pond | 1.50 | 6.667 |
| Newark  PARKING LOT LAIRD CAMPUS | 1.36 | 6.957 |
| PROPERTY OF KILLENS POND STATE PARK; BEHIND FARM B | 0.46 | 5.901 |

### Ozone (O3) (n = 7, units ppm)

| Site | CIS (raw) | Mean concentration |
| --- | ---: | ---: |
| BELLEVUE STATE PARK, FIELD IN SE PORTION OF PARK | 9.04 | 0.043 |
| MLK  CORNER OF MLK BLVD AND JUSTISON ST | 5.98 | 0.038 |
| BCSP | 3.52 | 0.042 |
| Seaford Shipley State Service Center | 3.03 | 0.043 |
| Lums Pond | 1.50 | 0.043 |
| PROPERTY OF KILLENS POND STATE PARK; BEHIND FARM B | 0.46 | 0.043 |
| Lewes SPM SITE, NEAR UD ACID RAIN/MERCURY COLLECTO | 0.43 | 0.042 |

### Sulfur dioxide (SO2) (n = 5, units ppb)

| Site | CIS (raw) | Mean concentration |
| --- | ---: | ---: |
| Route 9 Delaware City | 9.09 | 0.182 |
| BELLEVUE STATE PARK, FIELD IN SE PORTION OF PARK | 9.04 | 0.209 |
| MLK  CORNER OF MLK BLVD AND JUSTISON ST | 5.98 | 0.404 |
| Lums Pond | 1.50 | 0.242 |
| Lewes SPM SITE, NEAR UD ACID RAIN/MERCURY COLLECTO | 0.43 | 0.088 |

---

## Limitations

- **Sample size.** 11 monitors statewide; per-parameter n = 1-7. Even a strong observed ρ has wide statistical uncertainty at this n. We report directional findings, not p-values.
- **Monitor placement is non-random.** EPA AQS monitors are sited for regulatory purposes (NAAQS compliance, urban-airshed coverage), not for randomized burden sampling. This means the monitors that exist tend to BE in or near high-burden areas — restricting our ability to test the low-burden tail of the relationship.
- **Annual arithmetic means.** Each pollutant has a parameter-specific health benchmark (O3 4th-highest 8-hour daily max, NO2 98th percentile, etc.). For correlation with chronic facility burden, the year-averaged mean is sufficient — we don't need NAAQS exceedance counts. But peak exposure is not captured.
- **CIS is a proximity proxy, not an emissions transport model.** AERMOD-grade dispersion modeling would be the gold standard here; this analysis only tests whether a screening proxy correlates with what monitors measure.
- **No wind correction in this comparison.** The CIS at each monitor uses the v2.0 production default (chronic rose if loaded, else no wind). Per-monitor wind-adjusted CIS would refine the test, but the rose factor varies <10% across DE so we don't expect a meaningful shift.
- **CO and NO2 have only 1 monitor each in DE.** Their entries are skipped (correlation undefined for n=1).
- **Ozone is regional and partially anti-correlated with NOx.** Near major NOx sources, freshly-emitted NO can titrate O3 (NO + O3 → NO2 + O2), causing local O3 concentration to be *lower* than regional background. So a NEGATIVE CIS-O3 correlation is not necessarily a contradiction — it's chemistry. PM2.5 and SO2 don't have this complication.

---

## Reproducibility

```sh
python3 scripts/fetch_epa_aqs_monitors.py --years 2018-2024
python3 scripts/analyze_cis_monitors.py
```

Inputs: facilities.json (v2.0 weights), air_monitors.json (EPA AirData annual_conc_by_monitor pre-generated files for DE state code 10).
