# Data follow-ups — CC4EJ Delaware Cumulative Impacts Map

Tracking issues found during the 2026-05-03 data spot-check (Claymont area, 33 BGs sampled; statewide field census across 700 BGs). Sorted by severity. Each item has a one-line "what to do" so you can pick one up cold.

---

## P0 — visible to users today

### 1. "At-risk populations" section is a stub — all 12 rows render as `pending —`

**Where:** Info panel → "At-risk populations" section, every BG, every county.

**Root cause chain:**
- [`at_risk_populations.json`](at_risk_populations.json) — every numeric value is `null` with `"source": "pending"`. Counties Kent (10001), New Castle (10003), Sussex (10005), and Wilmington city (1077580). File last generated `2026-04-23`.
- [`scripts/sota_de_2025.csv`](scripts/sota_de_2025.csv) — has the air-quality grades (Ozone C/C/B, PM2.5-daily D/D/D) but the seven at-risk count columns are blank: `pediatric_asthma`, `adult_asthma_pct`, `copd_pct`, `cvd_pct`, `lung_cancer`, `poverty`, `people_of_color`.
- [`scripts/build_at_risk_populations.py`](scripts/build_at_risk_populations.py) — wired up and ready; the comment in the CSV says "transcribe from the SOTA county PDFs/HTML tables when confirmed", then re-run.

**User impact:** the section header reads "Populations in New Castle County most vulnerable to the ozone and particle pollution measured by the American Lung Association State of the Air report" and then 12 dashes. Looks like a broken loader. Erodes trust on every panel open.

**To fix (pick one):**
- (a) Transcribe the 2025 SOTA county tables into `scripts/sota_de_2025.csv`, run `python3 scripts/build_at_risk_populations.py`, commit the regenerated JSON.
- (b) Until (a) lands, hide the section instead of showing pending dashes — add a `display: none` until at least one row has a non-null value.

---

### 2. `over64_pct` data quality bug in 2024 history file

**Where:** [`de_blockgroups_history.json`](de_blockgroups_history.json) → `2024` block.

**Evidence:**
- BG `100030101063` (Claymont, Moderate EFA) shows `over64_pct: 87.0` for 2024, but:
  - Source [`de_blockgroups.geojson`](de_blockgroups.geojson) has `66.9`
  - 2023 history has `66.9`, 2022 had `66.3`, 2020 had `17.1`
  - 30%-point year-over-year jump is implausible for a stable BG
- Statewide in `2024`: **26 of 700 BGs** report `over64_pct ≥ 60%` (vs. 17 in 2023)
- BG `100050512043` (Sussex) reports **`over64_pct: 100.0`** in 2024 — mathematically impossible (no BG is 100% senior)
- Other anomalies in 2024: `100030166131` at 92.8, `100050512022` at 88.0

**Likely culprit:** [`scripts/build_acs5_history.py`](scripts/build_acs5_history.py) — check whether the 2024 ACS year is using a different table or normalization than 2023.

**To fix:**
- Audit the 2024 row in `build_acs5_history.py` against the raw ACS B01001 pull
- Spot-check a handful of BGs against api.census.gov directly
- Either regenerate `de_blockgroups_history.json` for 2024 or apply a manual correction

---

## P1 — investigate, may or may not be a bug

### 3. `cancer_pct = 0` in 351 of 700 BGs (50% of state)

**Where:** [`de_blockgroups.geojson`](de_blockgroups.geojson) `cancer_pct` field (EJScreen cancer-risk percentile).

**Question:** is this real EJScreen behavior (the NATA cancer-risk dataset has thresholds and many BGs come back at 0 percentile because they're below the screening floor), or a data-pipeline bug where a join failed and NULLs got coerced to 0?

**Why it matters:** if half the state shows "0 cancer risk" the layer doesn't communicate anything outside the high-burden cluster. If those should be NULLs, the panel should say "no data" instead of "0".

**To check:**
- Pull EPA EJScreen 2024 raw data for Delaware, compare `CANCER` field per BG against this file
- If they match: leave as-is, but consider a "no data below screening threshold" footnote in the panel
- If they don't match: fix the join in [`scripts/fetch_ejscreen_history.py`](scripts/fetch_ejscreen_history.py)

---

### 4. `under5_pct = 0` in 103 BGs

**Where:** Same file. Some are tiny BGs (367–990 pop), some larger (1178, 2254). 

**Question:** real demographic reality (no children counted in ACS sample) or institutional/commercial BGs where the denominator is dominated by group-quarters population?

**UX impact:** the panel currently shows "Children under 5: 0%" without distinguishing "ACS sampled zero" from "no kids actually live here". For a school-zone or pollution-near-children analysis, that's misleading.

**To fix:**
- Cross-reference the 103 BGs against ACS group-quarters flag
- Add a footnote on the panel for `under5_pct = 0` BGs: "ACS sample did not record children under 5" (or similar honest framing)

---

### 5. `lingiso_pct = 0` in 417 BGs (60% of state)

**Where:** Same file.

**Concentration:** 240 of 409 New Castle BGs show 0. Heavy in Sussex/Kent (rural).

**Question:** plausible for English-dominant rural BGs, but 60% of the state seems high. Worth a sanity check against ACS B16005 (linguistic isolation table).

**To check:** pull ACS B16005 for a sample of 10 BGs and compare. If the data agrees, fine. If not, fix the loader.

---

### 6. `efa_mhhi` (median household income) null in 25 BGs

**Where:** Same file.

**Likely cause:** ACS suppresses median income for BGs with very small household counts.

**UX impact:** EFA detail panel currently just omits the income line silently. A "income suppressed by Census" label would be more honest.

**To fix:** in `showInfo()`, render "Income: not published (Census privacy threshold)" when `efa_mhhi` is null instead of skipping the row.

---

## P2 — copy + UI polish around data

### 7. Hospitalization-rate row labels are too long for mobile

**Where:** Info panel → Observed health outcomes section.

**Current:** "Crude Rate of Hospitalizations for Asthma per 10,000 Population CDC EPHT · 2022    6.7"

**Issue:** wraps to 3 lines on a phone, dense, technical phrasing.

**Fix:** "Asthma hospitalizations (crude / age-adj) — 6.7 / 7.2 per 10K · CDC EPHT 2022" on a single line, or split into two short rows.

**Source of the label:** wherever the EPHT renderer lives in [`index.html`](index.html) (search `Crude Rate of Hospitalizations`).

---

### 8. No outlier asterisks / no statewide ranking context

**Issue:** the panel shows raw percentiles and percentages but never says "this BG is in the top 5% statewide for X" or "highest in Sussex County". For an advocacy tool, "this is unusual" is more valuable than the raw number.

**Fix idea:** for each indicator, compute statewide quartile rank at data-load time and add a small ★ or "top 10% in DE" tag next to values in the upper quartile.

---

### 9. EJScreen cancer + traffic + superfund rows just say "Above median"

**Where:** Info panel → Air & pollution section.

**Issue:** rows render as e.g. "PM2.5 air pollution — Above median". A 10th grader (or anyone) doesn't know "above median compared to what" — Delaware? US? National percentile? The `_pct` field is a national percentile but the label hides that.

**Fix:** "PM2.5 — 96th percentile nationally (worse than 96 of 100 places in the US)". Or use the same phrasing the wind-adjusted-proximity row uses ("Very High — extreme clustering").

---

### 10. "vintage" / "data_year" caption uses jargon

**Where:** Info panel → "Showing 2024 data (nearest available to 2050)" pill.

**Issue:** "vintage" is jargon; "nearest available" is opaque.

**Fix:** "We're showing 2024 numbers (the most recent we have) for a 2050 view".

---

## Method notes

- All findings reproducible by running `python3 -m http.server 8765` from the repo root, opening `http://localhost:8765/`, navigating to Claymont, tapping any colored BG, and inspecting the info panel.
- Statewide field census reproducible via the Python snippet at the bottom of this file (uses only `json` + `collections`).
- Mobile audit fixes already landed in this branch: see [`MOBILE_AUDIT.md`](MOBILE_AUDIT.md) for the original 30 findings and which 18 are fixed.
- This file should grow as new data issues surface — keep one section per issue, lead with severity, end with "to fix".

```python
# Statewide field census — paste into a python REPL from repo root
import json
from collections import Counter
with open('de_blockgroups.geojson') as f:
    d = json.load(f)
n = len(d['features'])
fields = ['eb','sv','pop','pm25_pct','diesel_pct','cancer_pct','traffic_pct',
          'superfund_pct','lowinc_pct','poc_pct','unemp_pct','lingiso_pct',
          'edu_nohsdip_pct','under5_pct','over64_pct','sv_health','efa',
          'efa_mhhi','efa_poverty_pct','efa_combined_minority']
print(f'Total BGs: {n}')
for fld in fields:
    vals = [feat['properties'].get(fld) for feat in d['features']]
    nulls = sum(1 for v in vals if v is None)
    zeros = sum(1 for v in vals if v == 0 or v == 0.0)
    print(f'{fld:<25} null={nulls:<4} zero={zeros:<4}')
print('EFA dist:', dict(Counter(f['properties'].get('efa') for f in d['features'])))
```
