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
