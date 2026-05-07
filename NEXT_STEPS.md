# Next steps — timeline info-panel data

Resume doc for the cc4ej-ci-map timeline-scrub project. Hand this to Claude in a fresh session and it should pick up without re-investigation.

Branch: `claude/timeline-scrub-panel-update-dw9y3`

---

## Subscriber notifications

`scripts/check_new_incidents.py` + `.github/workflows/notify-new-incidents.yml`
poll several sources weekly, diff against `notification_state.json`, and
email subscribers via Resend when new entries appear in `NOTIFY_STATES`
(default `DE,PA,NJ,MD`).

Each source lives in `scripts/notifiers/<name>.py` and exposes
`fetch(states) -> list[Alert]`. Adding a new source = drop in a new module
and append it to `SOURCES` in `check_new_incidents.py`.

**Wired sources:**
- `chemical_disasters` — diffs the in-repo `chemical_disasters.json`.
- `federal_register` — federalregister.gov JSON API; CERCLA RODs, RCRA
  permit notices, EPA cleanup actions filtered by state name + keyword.
- `epa_envirofacts` — EPA Envirofacts REST: SEMS_FAC_DETAIL (Superfund),
  RCR_HD_HANDLER (RCRA generators), RCR_CORRECT_EVENT (Corrective Action
  milestones).
- `epa_echo` — ECHO enforcement-case REST endpoint.
- `phmsa` — annual pipeline-incident CSVs (hazardous-liquid + gas-distribution).
- `nrc` — National Response Center annual CSV rollups.
- `dnrec` — HTML scrape of DNREC public notices + SIRS site list (DE only).

**Setup:**
1. Create a Resend account, verify a sending domain, generate an API key.
2. In repo settings → Secrets and variables → Actions:
   - **Secret** `RESEND_API_KEY` — the Resend API key.
   - **Variable** `NOTIFY_FROM` — e.g. `alerts@yourdomain.org` (must be on a verified Resend domain).
   - **Variable** `NOTIFY_RECIPIENTS` — comma-separated email list.
   - **Variable** `NOTIFY_STATES` *(optional)* — defaults to `DE,PA,NJ,MD`.
3. Trigger the workflow once manually. Sources not yet present in
   `notification_state.json` are seeded silently on first encounter, so the
   first cron run after a new source is added won't dump its full backlog.

**Known limitations:**
- The CSV/HTML sources (PHMSA, NRC, DNREC) are best-effort — column names
  and selectors will drift. Failures in one source don't block others.
- Envirofacts SEMS / RCRAInfo return facility-level records, not specific
  remedy decisions. New facility registrations fire alerts; intra-record
  status changes (e.g. CA725 → CA750) won't unless EPA assigns a new
  EVENT_ID.
- DNREC public-notice scraper relies on `<a>`-tag heuristics; if DNREC
  redesigns the page, expect false negatives.

**Future work:**
- Replace static `NOTIFY_RECIPIENTS` with a signup form (Formspree, Tally,
  or a Vercel Function backed by Supabase / Turso).
- Web Push (service-worker `push` listener + VAPID keys + subscription store)
  is the next tier up — worth doing once subscriber count exceeds what email
  can absorb.

---

## Where we are

**Done:**
- Vintage-badge system wired into Air, Demographics, Observed Health, EFA panels (frontend `index.html`). Scrubbing shows "EJScreen from YYYY (nearest available to SCRUB_YEAR)" when data isn't for the exact year.
- `_resolveHistoryYear()` + `__vintageYear` stash route nearest-year BG data into `applyYearToBG` automatically.
- `de_blockgroups_history.json` populated with **9 years (2016–2024)** at 99% coverage against the 2020 BG baseline. Every year has ~706 Delaware block-group records.
- `scripts/fetch_ejscreen_history.py`, `scripts/prep_crosswalk.py`, `scripts/audit_history.py`, `scripts/bg10_to_bg20_DE.csv` all committed.
- 2015 deliberately excluded (EJScreen v1 schema predates the P_* percentile system).

**Commit to ship the data file if not already pushed:**
```
cd ~/Desktop/cc4ej-ci-map
git add de_blockgroups_history.json scripts/bg10_to_bg20_DE.csv
git commit -m "Populate de_blockgroups_history 2016-2024 with fixed crosswalk"
git push -u origin claude/timeline-scrub-panel-update-dw9y3
```

---

## Phase 2 — CDC PLACES multi-year health data

**Current state:** `places_tracts.json` has only CDC PLACES 2022. Panel shows "CDC PLACES from 2022 (nearest available to YYYY)" for every other year.

**Goal:** Populate annual PLACES data (2020–2024 minimum) so Observed Health updates with the scrubber.

### Data acquisition
CDC publishes PLACES on Socrata. Each annual release has its own dataset ID (find them at https://chronicdata.cdc.gov/browse?q=places+tract):

- 2024: `cwsq-ngmh` (or whichever is tagged "2024 release")
- 2023: `yjkw-uj5s` (verify)
- 2022: (already have — currently in `places_tracts.json`)
- 2021, 2020: similar pattern

**Fetch endpoint pattern:**
```
https://chronicdata.cdc.gov/resource/<DATASET_ID>.json?stateabbr=DE&$limit=250
```

250 is above Delaware's ~218 census tracts. Returns tract-level prevalence for 30+ measures.

### Code to write (ask Claude)
1. `scripts/build_places_history.py` — fetches each year's Socrata dataset, normalizes column drift (measures renamed across years), writes `places_tracts_history.json` in year-major shape:
   ```json
   { "2022": { "TRACT_GEOID": { "arthritis": 24.1, "bphigh": 31.5, ... }, ... }, "2023": { ... } }
   ```
2. Patch `renderHealthSection` in `index.html` to read `placesHistory[year][tractGeoid]` with the same nearest-year fallback pattern.
3. Update vintage badge to report the resolved year per-lookup instead of the fixed 2022 constant.

### For Claude when resuming
- Ask user for the Socrata dataset IDs they want (or have Claude spawn a research agent to find them on chronicdata.cdc.gov).
- Write the script, have user run it on their Mac.
- Sandbox cannot reach chronicdata.cdc.gov.

---

## Phase 3 — EPA TRI history (1987–present)

**Current state:** Facility splashes and Proximity CIS use `facilities.json` with a single `founded` year. TRI (Toxics Release Inventory) annual emissions are not wired in.

**Goal:** Show "XX,XXX lbs released in YYYY" on facility splashes as the scrubber moves.

### Data acquisition
TRI Basic Plus files are published annually at https://www.epa.gov/toxics-release-inventory-tri-program/tri-basic-data-files-calendar-years-1987-present. Delaware subset is small.

**CSV columns to preserve:**
- `TRIFID` (facility ID — join key)
- `REPORTING YEAR`
- `CHEMICAL NAME`
- `TOTAL RELEASES` (lbs/year, the scrubber value)
- optional: `ON-SITE RELEASE TOTAL`, `OFF-SITE RELEASE TOTAL`

### Code to write
1. `scripts/fetch_tri_history.py` — pulls DE rows from each annual CSV, aggregates per facility per year, writes `tri_history.json`:
   ```json
   { "TRIFID1": { "1987": 45000, "1988": 41200, ..., "2023": 12100 }, ... }
   ```
2. Add TRI totals to `facilities.json` records OR load `tri_history.json` separately.
3. Patch facility splash renderer (search for `fac-nearby` / `prox-impact-score` in `index.html`) to show current-year release and a sparkline.

### For Claude when resuming
- TRI Basic Plus is ~100MB/year national → too large for sandbox. User downloads DE subset from the EPA envirofacts TRI.CSV endpoint (pre-filtered to state).
- Envirofacts TRI query pattern: `https://enviro.epa.gov/enviro/efservice/TRI_FACILITY/STATE_ABBR/DE/CSV`

---

## Phase 4 — NOAA climate history

**Current state:** Climate section uses a static SLR projection table. Historical observed temperature/precipitation is not shown.

**Goal:** Show observed annual temp + precip for each Delaware county/station, so scrubbing pre-2025 shows actual historical climate, post-2025 shows projection.

### Data acquisition
NOAA Climate Data Online (CDO) API. User has a token already.

**Annual summaries endpoint:**
```
GET https://www.ncei.noaa.gov/cdo-web/api/v2/data
?datasetid=GSOY&locationid=FIPS:10001&startdate=1970-01-01&enddate=2024-12-31
&datatypeid=TAVG,PRCP&limit=1000
```
Header: `token: <user's NOAA token>`

Delaware counties: `FIPS:10001` (Kent), `FIPS:10003` (New Castle), `FIPS:10005` (Sussex).

### Code to write
1. `scripts/fetch_noaa_climate.py` — reads token from `$NOAA_TOKEN` env var, paginates GSOY annual data, writes `noaa_climate_history.json`:
   ```json
   { "2020": { "10001": { "tavg_f": 56.2, "prcp_in": 44.1 }, ... }, ... }
   ```
2. Patch Climate panel in `index.html` to read historical year (pre-2025) from this file with vintage-badge fallback; keep SLR projection table for 2025+.

### For Claude when resuming
- Token is in user's env; ask them to paste it into a script or export it.
- Watch for rate limits (NOAA allows 1000/day, 5/sec).

---

## Phase 5 — CDC EPHT asthma utilization (in progress)

**Current state:** `epht_asthma.json` populated with two county-level measures (2022 only), surfaced in the Observed health outcomes panel via `renderHealthSection`:
- Measure 101 — Crude Rate of Hospitalizations for Asthma per 10,000 (Kent 5.1, NCC 6.7, Sussex 3.2)
- Measure 103 — Age-adjusted Rate, same shape (Kent 5.6, NCC 7.2, Sussex 4.0)

**Goal:** Add tract-level ED visit rates for Wilmington-specific resolution + multi-year history + pediatric prevalence.

### Discoveries (so the next session doesn't re-derive them)
- Base URL: `https://ephtracking.cdc.gov/apigateway/api/v1`
- `/geography/{measureId}/{geoTypeId}/0` is **deprecated (HTTP 410)** — don't use it. Pass FIPS strings directly in `geographicItemsFilter` instead.
- Data endpoint: `POST getCoreHolder/{measureId}/{stratLevelId}/{isSmoothed}/0` with JSON body. All body fields must be strings.
- `temporalItemsFilter` is **required** — empty list returns empty `tableResult`.
- Response field names: `geoId` (FIPS), `temporal` (year as string), `dataValue`, `suppressionFlag` ("0"/"1").
- Optional `EPHT_API_KEY` env var → query param `?apiToken=...` for higher rate limits. Token via email to trackingsupport@cdc.gov.
- Working geographicTypeIds: state=`1`, county=`2`. **Census tract ID is unknown** — see follow-up below.

### Follow-up A — Tract-level ED visit rates (897/894/900)
The big prize: would give Wilmington-specific resolution for ED visits.

**Blocker:** unknown `geographicTypeId` for census tract on EPHT. Tried `8`, `11`, `12`, `13` — all return empty stratification list for measure 897. The right ID likely exists but isn't documented in the EPHTrackR R package source either.

**How to unblock:**
1. Open the EPHT data explorer (https://ephtracking.cdc.gov/DataExplorer/) and select measure 897 with geographic type "Census Tract." Open browser dev tools → Network tab → look at the `getCoreHolder` POST request. The path will reveal the correct `stratLevelId`, and the request body will reveal the correct `geographicTypeIdFilter`.
2. Once known, extend `scripts/build_epht_asthma.py` with a `GEO_TYPE_TRACT` constant + a tract-fetch path that pulls all DE tract GEOIDs (11-char) and adds them to `epht_asthma.json` under a `tracts: { GEOID: { measures: ... } }` block.
3. Renderer pickup: `renderHealthSection` already takes the BG GEOID's first 11 chars for tract lookup (see existing `resolvePlacesTract`). A parallel `resolveEphtTract` helper would surface the row for Wilmington BGs.

### Follow-up B — BRFSS prevalence family (585/586/587/588)
Pediatric (587/588) + adult (585/586) asthma current/ever-diagnosed prevalence at state level. Would be the only EPHT path to pediatric data (county-level pediatric isn't published).

**Blocker:** all four measures return 0 rows under every stratification level we tried (1/3/4/8) and every `temporalTypeIdFilter` (1-6 + empty), with both `isSmoothed=0` and `1`.

**How to unblock:**
1. Email trackingsupport@cdc.gov: *"Are measures 585-588 (asthma BRFSS prevalence) currently published for Delaware via the public API? `getCoreHolder` returns empty `tableResult` for all stratification + temporal combinations."*
2. If answer is "yes, with token": add token via `EPHT_API_KEY` env var and re-test.
3. If answer is "no, deprecated": drop `588` from `SEED_MEASURES` in `scripts/build_epht_asthma.py` and document the gap.
4. Alternative path: **CDC PLACES Children's Data** if/when CDC publishes a youth current-asthma measure at tract level. Probe script stub already exists at `scripts/probe_places_children.py` (from the SOTA work).

### Follow-up C — More years of data for 101/103
Current populate only returned 2022. The script requested 2018-2023; older years may be gated.

**How to unblock:**
1. Get an EPHT API token (email above), set `EPHT_API_KEY`.
2. Re-run: `python3 scripts/build_epht_asthma.py --years 2015,2016,2017,2018,2019,2020,2021,2022`.
3. If older years come back, the renderer's nearest-year picker (`Math.abs(b - currentYear)` reducer in `renderHealthSection`) already handles multi-year data — no code change needed; just commit the refreshed `epht_asthma.json`.

### Files touched in Phase 5
- `scripts/build_epht_asthma.py` — EPHT fetcher with `--discover`, `--measure`, `--years`, per-measure error handling
- `epht_asthma.json` — county/state-keyed measures with year-major sub-buckets
- `index.html` — `ephtAsthma` global, fetch + parse in `Promise.all`, EPHT row injection in `renderHealthSection` after the CDC PLACES vintage badge

### For Claude when resuming
> Resume Phase 5 of cc4ej-ci-map — see `NEXT_STEPS.md`. Three follow-ups: (A) discover tract `geographicTypeId` for measure 897 via EPHT data explorer dev-tools, (B) email trackingsupport@cdc.gov about measures 585-588 returning empty, (C) re-run with EPHT_API_KEY and broader year range. Sandbox can't reach `ephtracking.cdc.gov` (host-allowlist blocked) — write scripts/probes for the user to run on their Mac.

---

## Quick re-entry prompt for a new Claude session

> I'm resuming the cc4ej-ci-map timeline-panel project on branch `claude/timeline-scrub-panel-update-dw9y3`. Phase 1 (EJScreen history 2016–2024) is complete — see `NEXT_STEPS.md` in the repo. Please start Phase 2 (CDC PLACES multi-year) per the plan in that doc. Sandbox can't reach external data hosts, so write scripts for me to run on my Mac.

---

## Frontend nearest-year pattern (reference)

Any new historical dataset should follow this shape in `index.html`:

1. Year-major JSON (`{ "YYYY": { "KEY": {...values...} } }`).
2. Loader that stashes on a shared module (like `_bgGeoJson.__vintageYear = resolvedYear`).
3. Helper `nearestYearWithData(years, scrubYear)` + `dataVintageBadge(panelYear, scrubYear, label)` already exist around line 4075 — reuse them.
4. Render path: read `data[resolvedYear][key]`, append `dataVintageBadge(resolvedYear, currentYear, 'CDC PLACES')` to the panel HTML.

---

## Files touched so far

- `index.html` — vintage badge system, `_resolveHistoryYear`, `applyYearToBG` stash, four panel patches
- `scripts/fetch_ejscreen_history.py` — EJScreen multi-year loader with EPA/Wayback/local-file fallbacks, crosswalk diagnostics, quality gate, stale-year pruning
- `scripts/prep_crosswalk.py` — Census block-level → BG 2010↔2020 crosswalk builder (BOM-safe, column-variant tolerant)
- `scripts/audit_history.py` — sanity-checks the history JSON against the live BG baseline
- `scripts/bg10_to_bg20_DE.csv` — 799 BG mappings for Delaware
- `de_blockgroups_history.json` — 9 years of EJScreen data

---

# Next steps — Facility Burden Index (CIS) methodology beyond v2.0

Tracked here so deferred work doesn't get forgotten. As of 2026-05-07 the
methodology is at **v2.0** on `claude/ecstatic-snyder-bee91a` (PR
description in `PR_DESCRIPTION.md`). Below are items the plan
deliberately deferred — not abandoned, just out of scope for the
current PR because they need partner relationships, more time, or
additional data curation.

## Tier 3.3 — AERMOD calibration (partner-dependent)

The gold-standard empirical defense. Pick 1–2 case-study facilities
(Delaware City Refinery and Citisteel are the obvious candidates — DCR
for the active refinery case, Citisteel for the long-term legacy
contamination case). Have a permitted air-quality consultant or an
academic partner (UDel public health, Drexel Dornsife, EPA Region 3
contact, Earthjustice technical staff) run AERMOD or AERSCREEN against
their reported emissions and met data. Compare AERMOD's annual-average
concentration grid to the CIS at every cell of the AERMOD grid.

Test: Spearman ρ > 0.7 across the AERMOD output cells means the CIS
is a defensible screening proxy for regulatory-grade dispersion. Below
0.7 = document where the model diverges and why.

Output: `analyses/cis_aermod_calibration_2026.md`. This becomes
**METHODOLOGY.md §8d** "Validation against regulatory dispersion
modeling."

Dependencies: a partner who can run AERMOD. The model itself is open
EPA software but requires meteorological pre-processing (AERMET) and
specialist setup. Not viable for the project team alone.

## Tier 4.1 — External peer review

Prepare a 4–6 page methods note drawn from `METHODOLOGY.md` and
circulate to:

- UDel Disaster Research Center / College of Health Sciences
- Drexel Dornsife School of Public Health (urban health)
- Existing CCEJ academic relationships
- Earthjustice / Clean Air Council technical staff

Goal: ≥1 external reviewer comment file (track in `peer_reviews/`).
Stretch: working-paper pre-print on SSRN or arXiv with a citable DOI.
One peer-reviewed citation changes the tool's status from "advocacy
site" to "documented methodology cited in the literature."

## v2.1 candidates (math refinements, no partner needed)

Each is independent — pick whichever has highest leverage when work
resumes.

1. **Speed-weighted wind rose.** The current `chronicWindFactor()`
   weights only by directional frequency. Multiply by mean speed in
   each bin to get kinematic flux (∝ frequency × speed). Cleaner
   physics; expected to shift factors by <5%. Easy: `noaa_wind_rose.json`
   already has `mean_speed_ms` per bin. Update `chronicWindFactor()`
   in `js/cis.js` and `_cis_stats.py` together; verify parity.

2. **Toxicity-weighted within-category scoring.** Currently 100 lb of
   benzene and 100 lb of formaldehyde count equally toward the cancer
   surface. Use EPA IRIS IUR (Inhalation Unit Risk) for cancer
   weighting and IRIS RfC (Reference Concentration) for respiratory
   weighting. A facility releasing high-IUR chemicals (e.g., ethylene
   oxide IUR ≈ 3×10⁻³) gets disproportionately more cancer-surface
   weight than one releasing low-IUR carcinogens (e.g., methylene
   chloride IUR ≈ 10⁻⁸).

   Implementation: build `scripts/_chem_toxicity.py` with a CAS →
   IUR/RfC lookup table for the ~50 chemicals that appear in
   `tri_chemical_history.json` with non-trivial Delaware volume.
   Then in `build_facility_weights_v13.py`, replace the mass-share
   allocation with a toxicity-weighted-share allocation:

   ```
   cancer_tox_emissions = Σ (lbs[c] × IUR_normalized[c]) for c in cancer chems
   weight_cancer_v21 = weight_combined × (cancer_tox_emissions / total_tox_emissions)
   ```

   Provenance: each chemical's IUR/RfC value gets a one-line citation
   to its IRIS Chemical Assessment Summary URL.

3. **Dasymetric within-BG sampling.** v2.0 normalization uses BG
   centroids weighted by BG population. A finer cut: distribute each
   BG's population across NLCD imperviousness pixels (already fetched
   via `fetch_nlcd_impervious.py`) so the normalization sample
   represents where residents *within* each BG actually live, not the
   geometric center. Mostly affects sparse rural BGs where the centroid
   lands in farmland.

4. **Multi-station wind blend.** v1.2 wind rose uses only KILG
   (Wilmington Airport). Sussex County downstate has different
   prevailing winds. Pull NOAA ISD for KGED (Georgetown, DE) and blend
   roses by latitude — northern DE uses KILG, central blends, southern
   uses KGED.

5. **Per-facility category override list.** Currently non-TRI
   facilities (Superfund, traffic, legacy contamination) appear only on
   the combined surface. A hand-curated `facility_category_overrides.csv`
   could let domain experts flag specific Superfund sites for the
   cancer surface (e.g., Citisteel for Cr(VI), AWE for fluorides) and
   for the respiratory surface (e.g., contaminated steel mill sites for
   particulate). Documented in METHODOLOGY.md §7b as the
   "category override path."

## Files to keep building toward

- `analyses/cis_aermod_calibration_2026.md` — Tier 3.3 deliverable
- `peer_reviews/<reviewer>_<date>.md` — Tier 4.1 deliverable per reviewer
- `scripts/_chem_toxicity.py` — v2.1 candidate #2
- `scripts/fetch_kged_wind.py` (or extension of `fetch_noaa_wind_rose.py`) — v2.1 candidate #4
- `facility_category_overrides.csv` — v2.1 candidate #5
