# Data Provenance

Where every number the map paints comes from, how confident we are in it,
and what has to be re-fetched if the upstream goes dark. Pair with
`snapshots/MANIFEST.lock.yaml` (the machine-readable version).

## Current state of the map (April 2026)

| Layer                       | Status | Source                                    | Years covered  | Confidence |
|-----------------------------|--------|-------------------------------------------|----------------|------------|
| Block-group EB (baseline)   | live   | EJScreen 2023 baked into `de_blockgroups.geojson` | 2023 only | high |
| Block-group SV (baseline)   | live   | EJScreen 2023 + CDC SVI 2020 blended      | 2023 only      | high       |
| History slider 2015–2024    | **stub**| `de_blockgroups_history.json` from `fetch_ejscreen_history.py` | 2023 row only | low until fetched |
| Facility markers            | live   | Hand-curated `facilities.json`            | 1850–2024      | medium     |
| Facility `tier` weights     | **stub**| `weight` hand-set, `tier` field empty     | —              | low        |
| TRI annual pounds           | **stub**| `tri_lbs_by_year` empty                   | —              | none yet   |
| Chronicle cards 1850–1969   | **stub**| `chronicle.json` does not exist yet       | —              | none yet   |
| Coming Clean disasters      | live   | `chemical_disasters.json`                 | 1979–2024      | high       |

"Stub" means the map renders a reasonable approximation from the baseline
but the slider does not yet tell a year-differentiated story.

## Source registry

Each row below is mirrored in `ingest/manifest.yaml`. The lock pins the
hash of whatever file the pipeline actually received; if the upstream
mutates, CI fails loudly.

### Tier A — Ingested today

**EJScreen (EPA Office of Environmental Justice)**
- Dataset: national block-group environmental-burden + demographic indices
- Vintages tracked: 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024
- Primary mirror: Penn EJ Data Portal (PEDP) — university-operated
- Fallback: Harvard Dataverse (DOI 10.7910/DVN/RLR5AX)
- Fallback: EDGI archive
- Last resort: `gaftp.epa.gov/EJScreen/` (subject to takedown)
- Known schema drift: `MINORPCT` → `PEOPCOLORPCT` at 2021; GEOID vintage
  shifts from 2010-BG to 2020-BG at 2021 — `scripts/fetch_ejscreen_history.py`
  applies the census crosswalk.
- Percentile anchor: **pin to EJScreen national** across all vintages. The
  EJScreen state-anchor default makes the slider lie (Delaware's 95th
  percentile in 2015 is not Delaware's 95th in 2024). Documented in
  `scripts/fetch_ejscreen_history.py`.

### Tier B — Planned ingest (manifest entries ready, not yet fetched)

**TRI (Toxics Release Inventory, 1987–)**
- Facility-level annual pounds-released by chemical.
- Why we want it: gives the slider an honest year-differentiated
  proximity-burden surface pre-2015 (EJScreen doesn't exist that far back).
- Mirror strategy: EPA Envirofacts upstream, Harvard Dataverse mirrors for
  older vintages, EDGI for long-tail.
- Integration point: extends `rawProximityCIS(lat, lng, year)` in
  `index.html` (already year-aware) to consult `tri_lbs_by_year[year]`
  when present, falling back to `tier`-based weight otherwise.

**RSEI (Risk-Screening Environmental Indicators, 1988–)**
- EPA's toxicity-weighted version of TRI. Preferred over raw pounds when
  available. One-to-one replacement inside `rawProximityCIS()`.

**LTDB (Longitudinal Tract Database, Brown University)**
- Normalizes 1970 / 1980 / 1990 / 2000 / 2010 decennial census tracts to
  2020 boundaries.
- Why: census block-group boundaries are not stable across decades.
  Pre-2010 BG data is noisy; pre-1990 BG data doesn't exist in any
  meaningful form. LTDB at the tract level is the defensible compromise.
- Integration point: compute tract-level demographic trajectories 1970→2010,
  carry forward into BGs by apportioning tract-relative-to-2020-BG weights.

**ACS 5-year (2009–2013 through 2019–2023)**
- Bridges the 2009–2014 gap between LTDB decennials and the first EJScreen
  vintage (2015). Only demographic fields; environmental fields stay null,
  so the map colors SV alone for those years.

### Tier C — Narrative sources (Chronicle mode, Phase 6)

Used for per-era cards 1850–1969. Non-quantitative by design. The UI
commits to "this is historical record, not a map coloring."

- University of Delaware Center for Community Research Service archives
- DNREC historical publications + 1970-era baseline reports
- HOLC redlining maps (University of Richmond, Mapping Inequality)
- Philadelphia Inquirer + Wilmington News Journal digitized archives
- EPA historical reports + Section 112 pre-TRI narrative filings
- Peer-reviewed Delaware-corridor environmental history

### Tier D — Health outcomes (partial / long-tail)

- Delaware DPH cancer registry (county, some tract — FOIA in ledger)
- CDC WONDER mortality 1979– (county)
- CDC EPHT asthma / birth-outcomes (county)
- Children's blood-lead screening (CDC + DE)

County-level data is stored as a fallback layer the map can opt into —
not merged into the BG schema.

### Tier E — Regulatory long-tail (pre-TRI, 1970–1986)

- DNREC Division of Air Quality permit archives (likely FOIA)
- Coastal Zone Act compliance records 1971– (scattered PDFs)
- HSCA hazardous-site list (portal, public)
- State NPDES equivalents (public)
- EPA AQS criteria-pollutant monitors 1970– (monitor-site; IDW to BGs)
- Superfund/NPL listings from 1980 (public)
- NJDEP DataMiner + NJDEP EJMAP (neighbor-state fenceline)
- PA DEP eFACTS + PA EJ Areas (neighbor-state fenceline)

## Confidence model

Every yearly coloring on the map carries (implicitly, via the meta sidecar)
one of:

- **high** — checksummed raw file, verified against the lock, transformed
  by a reviewed script.
- **medium** — checksummed raw, but aggregation or crosswalk is an
  approximation (e.g. ACS 5-year crosswalked to BG-20).
- **low** — data exists but the transformation inserts assumptions the
  author chose (e.g. IDW interpolation of a 1978 AQS monitor to a BG
  10 km away).
- **narrative** — chronicle cards. Explicitly not a coloring.

The info panel will eventually read this from the meta sidecar. Until the
UI lands, the data is still stamped — just not surfaced.

## Known gaps & decisions we've already made

- **Pre-1900 fade is a visual cliff, not data.** `applyEraFade()` in
  `index.html` knocks BG opacity to 0.3× below 1900 to signal "no data."
  Phase 6 (chronicle mode) replaces this with a UI handoff instead of a
  math fade.
- **CIS_P95 normalization is global, not per-year.** Recomputing per year
  is cleanest but makes cross-year comparison incoherent because the
  denominator moves. Decision: pin to 2024 ("fully industrialized
  baseline") once TRI lands in Phase 3. Documented here so future-us
  doesn't silently change it.
- **Facility closures are approximate.** Until TRI arrives (closures are
  implicit in zero annual pounds), facilities that actually closed still
  render at modern years. `closed_year` is the field to set when known.
- **Baseline bleed-through.** A partial year (ACS-only, no environmental)
  lets the 2023 baseline show through. The info panel should flag fields
  as "year-specific" vs. "baseline-carried." Tracked in `SCHEMA.md`.
