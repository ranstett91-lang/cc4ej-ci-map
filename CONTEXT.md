# CC4EJ CI Map — Session Context

> Written to preserve project state across Claude sessions. Update this file
> whenever a significant change is made so the next session can pick up fast.
> Last updated: 2026-04-18

---

## What This Map Is

Interactive EJ (environmental justice) map for Claymont/Delaware built with
Mapbox GL JS. Static site — deploys automatically to Vercel from `main` branch.
`index.html` is the entire app; `facilities.json` and `de_blockgroups.geojson`
are the two data files.

---

## Key Architecture Decisions

### Why `setPaintProperty` instead of `setFilter`

Mapbox GL JS has two filter parsers. `setFilter(['all', ...])` uses the
**legacy** parser which rejects expression arrays inside the filter (throws
`filter[N][1]: string expected, array found`). `setPaintProperty` with a
`['match', ...]` expression uses the **full** expression parser. All facility
visibility logic was converted to paint-property opacity expressions to avoid
this bug. See `applyFacilityFilter()` in `index.html`.

### Why `queryRenderedFeatures` guard on bg-fill click

`MapMouseEvent.stopPropagation` does not exist on Mapbox events. The block-
group fill click handler uses `queryRenderedFeatures` to check if a facility
dot is under the click point and returns early if so, preventing the BG panel
from opening when the user clicks a facility dot.

---

## Data Files

### `facilities.json`

GeoJSON FeatureCollection of point features. Key property fields:

| Field | Values | Notes |
|---|---|---|
| `name` | string | Display name |
| `type` | string | Facility type description |
| `impact` | `air`, `chemical`, `refinery`, `contamination`, `traffic`, `ag` | Controls dot color and filter toggle |
| `category` | `facility`, `warehouse`, `corridor` | Controls which layer renders it |
| `weight` | 1.0–3.0 | Circle radius |
| `fips` | 5-digit string | County FIPS |
| `state` | `PA`, `NJ`, `DE` | Only set for out-of-state facilities |
| `note` | string | Long-form EJ context shown in panel |

Warehouses and vacant sites use `category: "warehouse"` and are toggled
separately via the warehouse checkbox (which is also wired into Toggle All).

### `de_blockgroups.geojson`

Delaware block groups with EJ indicator properties including:

| Field | Source |
|---|---|
| `lowinc_pct` | EJScreen (low-income %) |
| `unemp_pct` | ACS (unemployment %) |
| `lingiso_pct` | EJScreen (linguistic isolation %) |
| `poc_pct` | EJScreen (people of color %) |
| `edu_nohsdip_pct` | EJScreen `LESSHSPCT` — **see Pending Tasks** |
| `total_pop` | 2020 Decennial (used for EFA splits) |

**Population note:** BG `100030101051` was previously 542 (ACS 5-yr estimate);
updated to 591 to match 2020 Decennial — consistent with the EFA splits already
integrated in the map.

---

## Facility Coordinate Verification Status

### Verified correct (do not change)
- Croda Atlas Point — 315 Cherry Lane, New Castle DE → `-75.541, 39.6915` ✓
- Kuehne Chemical — 1645 River Road, Delaware City DE → `-75.6297, 39.6056` ✓
- Nexpera Red Lion — 766 Governor Lea Road → `-75.6334, 39.5929` ✓
- Metachem Products — 745 Governor Lea Road → `-75.6483, 39.6033` ✓ (plausible)
- Monroe Energy Trainer Refinery — 4101 Post Road, Trainer PA → `-75.4037, 39.8210` ✓
- Energy Transfer Marcus Hook Complex — 100 Green St, Marcus Hook PA → `-75.4157, 39.8091` ✓
- ReWorld Chester Incinerator — 10 Highland Ave, Chester PA → `-75.3882, 39.8265` ✓
- Braskem Marcus Hook — south of Blue Ball Ave, west of W 10th → `-75.4200, 39.8135` ✓
- Honeywell Delaware Plant — just north of INEOS → `-75.4370, 39.8072` ✓
- Delaware City Refinery — 4550 Wrangle Hill Rd → `-75.5975, 39.5711` ✓

### Fixed this session (were wrong)
- **Lubrizol** was at `-75.392, 39.822` (Gibbstown NJ, no plant there) → corrected
  to 76 Porcupine Rd, Pedricktown NJ: `-75.423, 39.764`, fips `34033`
- **Energy Transfer Marketing & Terminals** (Claymont DE entry) was a **duplicate**
  of Marcus Hook Complex — removed
- **Sunoco Partners** was at `-75.449` (inland) → moved east to `-75.435` to sit
  on the Delaware River waterfront (described as "¼ mile east of Rt 13 on the river")

### Needs further verification
- **LANXESS Logan Township NJ** — current `-75.375, 39.75`. Address is
  "170 Route 130 South, Logan Township, Gloucester County NJ." Plausible but
  unconfirmed. Needs geocoding against the actual address.
- **Valtris Specialty Chemicals Marcus Hook** — current `-75.406, 39.823`.
  Rough placement, no address-level verify done yet.
- **Evonik Corp Marcus Hook** — current `-75.412, 39.821`. Same.
- **Mexichem/Vestolit Marcus Hook** — current `-75.404, 39.826`. Same.
- **Paulsboro Refinery** — current `-75.233, 39.843`. Seems right for Paulsboro NJ.
- **Infineum Paulsboro** — current `-75.243, 39.837`. Seems right.

---

## Data Pipeline Scripts

### `scripts/update_ejscreen.py` (NEW — supersedes patch_edu.py)

Fetches all 17 EJScreen EB + SV fields for DE block groups and patches them
into `de_blockgroups.geojson`. Run on a machine with internet access:

```bash
cd ~/Documents/cc4ej-ci-map
pip install requests
python3 scripts/update_ejscreen.py --dry-run  # preview first
python3 scripts/update_ejscreen.py            # apply all 17 fields
git add de_blockgroups.geojson
git commit -m "Refresh EJScreen 2023 data"
git push origin main
```

Field groups: `--fields all` (default) | `eb` | `sv` | `edu`

**Important:** Rate fields (LOWINCPCT, UNEMPPCT, LINGISOPCT, LESSHSPCT,
UNDER5PCT, OVER64PCT) are stored as percentages (×100). The old `patch_edu.py`
stored LESSHSPCT as a raw 0–1 value — running `--fields edu` will correctly
overwrite any old raw values with the proper percentage form.

Fields fetched:

| EJScreen field | GeoJSON property | Kind |
|---|---|---|
| P_PM25 | p_pm25 | percentile |
| P_OZONE | p_ozone | percentile |
| P_DSLPM | p_dslpm | percentile |
| P_CANCER | p_cancer | percentile |
| P_RESP | p_resp | percentile |
| P_PTRAF | p_ptraf | percentile |
| P_PNPL | p_pnpl | percentile |
| P_PTSDF | p_ptsdf | percentile |
| P_PRMP | p_prmp | percentile |
| P_PWDIS | p_pwdis | percentile |
| LOWINCPCT | lowinc_pct | rate (×100) |
| UNEMPPCT | unemp_pct | rate (×100) |
| LINGISOPCT | lingiso_pct | rate (×100) |
| LESSHSPCT | edu_nohsdip_pct | rate (×100) |
| UNDER5PCT | under5_pct | rate (×100) |
| OVER64PCT | over64_pct | rate (×100) |
| P_LIFEEXPPCT | p_lifeexppct | percentile |

### `scripts/verify_facilities.py` (NEW)

Queries EPA ECHO API to cross-check facility coordinates in `facilities.json`
against official EPA-registered locations. Flags any facility > 500 m off.

```bash
python3 scripts/verify_facilities.py                           # full check
python3 scripts/verify_facilities.py --output report.md       # save report
python3 scripts/verify_facilities.py --facility "LANXESS"     # single facility
python3 scripts/verify_facilities.py --threshold 250          # tighter check
```

Warehouses and corridors are skipped (not EPA point sources). NOT FOUND does
not necessarily mean coordinates are wrong — some older sites aren't in ECHO.

### `.github/workflows/refresh-ejscreen.yml` (NEW)

Runs `update_ejscreen.py` automatically each June 1 (when EJScreen typically
releases a new vintage) and commits any changed GeoJSON back to the branch.
Also triggerable manually from the Actions tab with `fields` and `dry_run`
inputs.

---

## Proximity-Weighted Cumulative Impact Score (2026-04-14)

### What it does

A new **Proximity Burden Score** now appears in the info panel whenever a user
clicks a block group. Unlike the EPA EJScreen EB/SV scores (which are averaged
across the entire census block group), this score is computed at the **exact
clicked lat/lng**, so two clicks in the same block group can return different
values if one is closer to a highway or industrial facility.

### Formula

```
CIS(point) = Σᵢ [ weightᵢ × windFactorᵢ ] / max(distᵢ, 0.15 mi)^1.5
```

- `weightᵢ` — facility weight (1.0–3.0) from `facilities.json`
- `windFactorᵢ` — continuous: 1.4 (directly upwind) → 1.0 (crosswind) →
  0.6 (downwind), using `1.0 + 0.4 × cos(angleDiff × π/180)`. Uses the live
  `windFromDeg` global already populated by `loadWindData()`.
- Distance floor 0.15 mi (~240 m) prevents singularity near facilities.

### Normalization

`precomputeCISNorm(bgFeatures)` is called once at load time. It computes the
no-wind raw CIS for all ~700 BG centroids, takes the 95th percentile, and
stores it in `CIS_P95`. At click time: `normalized = min(10, raw / CIS_P95 × 10)`.
The baseline is no-wind so the scale stays stable; wind adjustment shifts the
click-time score up or down relative to that baseline.

### Combined Impact Index

`(CIS_norm / 10) × (SV / 10) × 10` — combines the sub-BG proximity burden
with the block group's social vulnerability score. In SV mode the label
changes to "Vulnerability-Weighted Burden". This is the CC4EJ analogue of
CalEnviroScreen's cumulative impact model.

### Key functions added (`index.html`)

| Function | Purpose |
|---|---|
| `rawProximityCIS(lat, lng)` | Raw inverse-distance score for a point |
| `precomputeCISNorm(bgFeatures)` | Sets `CIS_P95` normalization constant |
| `normalizeCIS(raw)` | Maps raw → 0–10 |
| `cisScoreColor(n)` | Interpolates EB_COLORS palette for a 0–10 CIS value |
| `renderProximitySection(lat, lng, svScore)` | Populates `#proximity-section` in the panel |

### Click handler changes

All three click handlers that call `showInfo()` now pass `e.lngLat.lat` and
`e.lngLat.lng` so the score reflects the actual clicked point rather than the
BG centroid.

---

## Impact Map Accuracy Fixes (2026-04-14)

### Yellow circle — uninhabited industrial waterfront

Two data-gap block groups (100030101041 Addicks Estates, 100030101051 Aniline
Village / Hickman Row / Knollwood) previously had their full BG polygon colored
in the main EB/SV view, including the uninhabited industrial waterfront along
the Delaware River east of the residential streets.

**Fix:**
- `bg-fill` now has a filter that **excludes** GEOIDs 100030101041 and
  100030101051, so the industrial waterfront area is no longer painted orange.
- **BG 100030101041 replacement:** a new `addicks-eb-fill` layer colors only the
  hand-drawn residential box (`addicks-area` source, lat 39.7998–39.8038,
  lon −75.4528 to −75.4492 — centered on the Addicks Estates community marker
  at (−75.4510, 39.8018), south of the Wilmington Expy / I-495 where the homes
  actually sit) which is also used for the dashed data-gap border. The
  `addicks-area` GeoJSON feature now carries `eb: 7.37, sv: 2.65` so the
  standard `ebFillExpr()` / `svFillExpr()` expressions work.
- **BG 100030101051 replacement:** a new `bg-splits-eb-fill` layer colors only
  the two DelDOT EFA residential split polygons for this BG (the splits are
  clipped to residential LULC, so the waterfront strip east of the residential
  streets is left uncolored). The EFA splits are enriched with parent BG EB/SV
  scores at load time via a GEOID lookup.
- In **EFA mode**, both replacement layers are hidden (EFA splits already handle
  101051; the addicks tint + dashed border remain for 101041).
- `setLayer()` was updated to switch all three fill layers (bg-fill,
  addicks-eb-fill, bg-splits-eb-fill) together when toggling EB ↔ SV ↔ EFA.

### Green circle — Claymont residential less visually distinct from Addicks

`EB_COLORS` now has two additional stops at 6.5 (`#fc9e6a`) and 7.5
(`#f06844`). The extra stops spread the gradient across the 6–8 range so that
Claymont residential block groups (EB ~6.9–7.3) appear noticeably lighter than
Addicks Estates (EB 7.37). The CSS legend-bar gradient was updated to match.

---

## Chemical Disasters Layer + Temperature Pill (2026-04-16)

### chemical_disasters.json (NEW)

GeoJSON FeatureCollection of 10 documented chemical incident points for the
DE/PA/NJ tri-state region. Sources: EPA RMP accident history, PHMSA pipeline
incident database, NRC (National Response Center) reports, NTSB accident
reports, and DNREC emergency response records — the same methodology used by
Coming Clean's Chemical Disasters Snapshot.

Properties per feature:

| Field | Notes |
|---|---|
| `name` | Incident name |
| `date` | ISO date string |
| `year` | Integer year (used for map label) |
| `chemical` | Primary chemical(s) involved |
| `type` | Incident type (fire, release, derailment, etc.) |
| `severity` | `major` or `significant` — controls marker color/size |
| `consequences` | Human-readable description of injuries/evacuations |
| `health_risk` | Health effects from exposure |
| `ej_context` | Environmental justice context for the affected community |
| `source` | Citation string |
| `source_url` | Primary source URL |
| `rmp_id` | EPA RMP facility ID (if applicable) |
| `nrc_id` | NRC incident report number (if applicable) |
| `state` | `DE`, `PA`, or `NJ` |

Incidents included:

| Incident | Date | Severity |
|---|---|---|
| Paulsboro NJ vinyl chloride train derailment | 2012-11-30 | major |
| Delaware City Refinery hydrocracker fire | 2021-06-16 | significant |
| INEOS Chlor-Alkali New Castle chlorine release | 2019-03-14 | significant |
| Chemours Chambers Works PFAS enforcement | 2019-07-09 | major |
| Energy Transfer Marcus Hook LPG release | 2020-07-08 | significant |
| Perdue Georgetown ammonia shelter-in-place | 2025-01-31 | significant |
| Croda Atlas Point sulfuric acid release | 2019-09-25 | significant |
| Monroe Energy Trainer Refinery fire | 2019-03-06 | significant |
| Kuehne Chemical Delaware City chlorine emergency | 2004-05-22 | major |
| Lubrizol Pedricktown NJ chemical release | 2021-09-29 | significant |

### Map Layer (index.html)

Four new Mapbox layers added:
- `disaster-glow` — low-opacity outer ring (severity-colored)
- `disaster-markers` — core circle, red for major / orange for significant
- `disaster-icons` — `⚠` symbol on each marker
- `disaster-year-labels` — year label below marker at zoom ≥ 10

Click a disaster marker → `showDisasterPanel()` opens the info panel with:
- Incident date, chemical, type, consequences
- Health risk section
- EJ context
- Verification links (EPA RMP, NRC, primary source, Coming Clean report)

Toggle: "Chemical disasters (RMP)" checkbox in sidebar.
`toggleDisasters()` controls all four layers. `toggleAllImpacts()` also
includes disasters in its all-on/all-off sweep.

### Temperature Pill (index.html)

- New `#temp-widget` div below the AQI badge (top: 74px)
- `loadWindData()` now also fetches `temperature_2m` and `apparent_temperature`
  from Open-Meteo (added to existing forecast API call — same endpoint)
- `tempLevel(f)` returns `{ bg, color }` for 7 temperature bands (°F)
- Shows "72°F" or "72°F (feels 65°)" if feels-like differs by ≥ 3°F
- `hidden` class initially; shown only when API call succeeds

### Data Verification Features (index.html)

- **⬇ Report button** added to panel action buttons bar — calls `downloadReport()`
- `downloadReport()` generates a structured `.txt` advocacy report including:
  - Block group scores (EB, SV, Combined Burden)
  - All EJScreen percentiles  
  - Demographic indicators
  - Nearby facilities list (within 8 mi)
  - Nearby chemical disaster incidents (within 30 mi)
  - Full data source citations
  - Download as `CC4EJ_Report_[GEOID]_[date].txt`
- **Data source badges** now appear in the block-group info footnote:
  EPA EJScreen 2023, CDC PLACES 2022, DelDOT EFA 2024, ACS 2017–2021
- **Verify links** in the footnote: EJScreen, EPA ECHO, full data sources page
- Sidebar note updated to explain Coming Clean methodology for red circles

---

## Water Quality Resources Added (2026-04-16)

A **💧 Water Quality** card was added to the sidebar (between the Claymont Focus card
and the legend), containing:
- DNREC Water Quality Monitoring page
- DNREC Water Permits Search
- EPA ECHO DE water discharge permits (NPDES)
- EPA ATTAINS impaired waters
- Delaware River Basin Commission

The card includes a collapsible explanation of the key water quality concerns for
the region: PFAS contamination, Naamans Creek impairment, Delaware River industrial
discharge, and the invisibility of NPDES water permits in typical EJ reviews.

---

## First State Crossing Added (2026-04-16)

**First State Crossing** — commercial/industrial development adjacent to Knollwood —
was added to `facilities.json` and `PERMIT_DATA` so it appears on the map and shows
NCC permit tracking links when clicked.

- **Coordinates:** `-75.446, 39.808` (immediately adjacent to Knollwood/Worthland)
- **Category:** `warehouse` / `sub_cat: development`
- **Impact:** `contamination`
- **Permit panel:** Shows "NCC Land Use / Building Permit — Under Review" card with
  links to NCC Permits portal and NCC Parcel Map

NCC links (`NCC Permits ↗` and `NCC Parcel Map ↗`) were also added to:
1. The curated permit card renderer (`renderPermitSection`) — via `ncc_permits_url`
   and `ncc_parcel_url` fields in any PERMIT_DATA entry
2. The fallback search links for any uncurated DE facility with `fips === '10001'`
   (New Castle County)

The **Knollwood/Worthland** community note in `communities.json` was updated to
reference First State Crossing as a development CC4EJ is monitoring.

---

## Time Slider — Phase 1 (2026-04-18)

A bottom-floating time scrubber (`#time-slider`) lets users move through
2004–2026. Ships the first of three planned phases (see
`/root/.claude/plans/i-want-a-way-warm-zephyr.md`).

### What it drives

- **Chemical disasters** — rebuilds the `chemical-disasters` source via
  `setData` with features filtered by year. Filtering at the source (not per
  layer) is required because the source has `cluster: true`; clusters
  aggregate at the source level, so a layer-level `setFilter` would leave
  future-year incidents visible inside cluster bubbles when zoomed out. Two
  modes via the Cumulative / Single-year segmented control:
  - `cumulative`: `feature.properties.year <= currentYear`
  - `single`:     `feature.properties.year === currentYear`
- **EJScreen BG scores (`eb`, `sv`, 17 indicators)** — year-aware via a new
  per-year lookup. Re-applies feature properties and calls `setData()` on the
  `blockgroups` and `efa-splits` sources. Every existing paint expression
  (`ebFillExpr`, `svFillExpr`, `cbFillExpr`, `ciEbFillExpr`, …) keeps
  working unchanged because it still reads `['get','eb']` etc. — the data
  behind that getter just changes with the slider.
- **EFA split overlays** — `ci_eb`, `ci_sv`, `ci_cb` are recomputed per year
  from the refreshed parent `eb`/`sv` using the same formulas as load time.
  `cis` (proximity) is NOT recomputed — facilities are static.
- **Live weather widgets** — temp pill, AQI badge, wind arrow, and location
  caption all hide via `.time-hidden` when `currentYear !== TODAY_YEAR`, and
  `loadWindData()` short-circuits so no fetch fires.
- **Info panel footnote + `downloadReport()`** — EJScreen vintage tag
  updates to match the resolved year (2015 → 2024 or the nearest
  available). Download report includes "Slider view year" + "EJScreen
  vintage used" in the header.

### What stays static (and says so)

Facilities, communities, EFA designations, proximity CIS surface. The
slider note reads *"Facilities, communities, EFA shown at current state
across all years."*

### Data files

- `de_blockgroups_history.json` — year-major JSON. Current shape is
  `{ "2023": { "GEOID": { eb, sv, p_pm25, ... }, ... } }`. Running
  `scripts/fetch_ejscreen_history.py` populates 2015–2024.
- `scripts/fetch_ejscreen_history.py` — downloads each EJScreen vintage
  CSV from EPA gaftp, normalizes column drift (MINORPCT → PEOPCOLORPCT,
  FIPS → ID), optionally applies a 2010→2020 BG crosswalk
  (`scripts/bg10_to_bg20_DE.csv`) for pre-2021 vintages, derives `eb` as
  mean(p_\*) / 10. Requires internet + `pip install requests`.
- `scripts/seed_history_from_baseline.py` — extracts the 2023 baseline
  from `de_blockgroups.geojson` into the history file so the slider
  renders correctly *before* the full fetch is run.

### Key functions added (`index.html`)

| Function | Purpose |
|---|---|
| `onYearChange(year)` | Main dispatcher — fires on every slider tick |
| `applyYearToBG(year)` | Merges year record over baseline props, `setData`s both BG sources |
| `applyDisasterYearFilter()` | Rebuilds the `chemical-disasters` source via `setData` with year-filtered features so clusters stay year-aware |
| `applyWeatherGate()` | Adds/removes `.time-hidden` on live widgets |
| `_resolveHistoryYear(y)` | Clamps / nearest-neighbors the slider year to an available vintage |
| `_updateEraUI(year)` | Paints the era-tag pill (Pre-EJScreen / Observed / Uses 2024) |
| `setDisasterMode(mode)` | Swap cumulative/single and re-apply filter |
| `togglePlay()` | 1-sec/year auto-advance, loops 2004 → 2026 |

---

## Time Slider — Pre-industrial baseline (2026-04-18)

Extends the slider's lower bound to **1850** so users can scrub back to
before the Delaware River corridor was industrialized and watch the
"red" burden pattern assemble itself as each facility is founded.

### Data

- Every feature in `facilities.json` now carries a `founded` integer
  year — populated by `scripts/patch_facility_founded.py` (idempotent,
  name-keyed, re-runnable).
- Year sourcing (documented in the script):
  - High confidence: Sun Oil Marcus Hook 1902, DuPont Chambers Works
    1891, DuPont Edge Moor TiO2 1935, Delaware City Refinery 1957,
    I-95 DE segment 1963, Worth/Phoenix Steel 1917, Paulsboro Refinery
    1917, Chester Incinerator 1991.
  - Medium: corporate-lineage founding dates for older sites.
  - Estimate (~decade): a handful of late-20th-century plants where the
    exact start-of-operation is fuzzy. Order-of-magnitude correct.
- Warehouses + redevelopments on legacy industrial land (Pepsi, Agile,
  First State Crossing) use the *site's* industrial-use origin year
  (Worth Steel 1917), not the current tenant's year — so scrubbing back
  retires the *burden*, not just the current surface.

### Slider behavior

- `SLIDER_MIN_YEAR` 2004 → **1850**. Input `min` matches.
- New era label `Pre-industrial` (CSS `.era-preind`, tan tint) when
  `year < 1900`. Pre-EJScreen label still applies 1900–2014.
- `applyFacilityYearFilter()` applies `['<=', ['get','founded'], year]`
  (null-safe via `['any', ['!', ['has','founded']], ...]`) to all 6
  facility layers (`fac-circles`, `fac-icons`, `fac-warehouse-bg`,
  `fac-warehouse-label`, `fac-corridor-bg`, `fac-corridor`). Called
  from `onYearChange` alongside `applyYearToBG` / `applyDisasterYearFilter`.

### Scrub milestones (useful for screenshots)

| Year | Facilities visible |
|---|---|
| 1850 | 0 (pre-industrial baseline) |
| 1870 | 1 (Dover Gas Light) |
| 1900 | 2 (+ Chambers Works) |
| 1920 | 13 (WWI-era Allied Chemical / Worth Steel / Paulsboro jump) |
| 1960 | 31 |
| 2000 | 53 |
| 2025 | 54 (full current state) |

---

## Time Slider — Phase 2: Climate Projections (2026-04-18)

Extends the slider to **2100** with a projection-era controls row that
appears once the user scrubs past 2025.

### Slider changes

- `SLIDER_MAX_YEAR` bumped 2026 → 2100; input `max` matches.
- `togglePlay()` advances 5 yr/tick past 2025 so 2025 → 2100 plays in ~15 s.
- `_updateEraUI(year)` adds `era-proj` class past 2025 + tints the BG fill
  muted to signal "demographics held at 2024".

### Row 2 controls (visible only when `currentYear >= 2026`)

- **Scenario segmented toggle** — RCP 4.5 (Moderate) / RCP 8.5 (High).
- **Overlay checkboxes** — SLR · Heat · Precip · Infra assets.
- Footnote: "Projections: NOAA SLR + LOCA2, DE SLR Technical Committee
  2017, Amtrak CVA 2022 et al. Demographics held at 2024."

### New globals

```js
let scenario = 'rcp45';                                          // 'rcp45' | 'rcp85'
let overlayVisibility = { slr:true, heat:false, precip:false, infra:true };
let slrData, infraData, reportsMeta;
const SLR_YEAR_FT = [ {year:2030,rcp45:1,rcp85:1},
                      {year:2050,rcp45:1,rcp85:3},
                      {year:2075,rcp45:3,rcp85:5},
                      {year:2100,rcp45:3,rcp85:7} ];
const INFRA_BINS  = [2030, 2050, 2075, 2100];
```

SLR ft-per-year trajectories follow DE Sea-Level Rise Technical Committee
2017 (0.52 m / 0.99 m / 1.53 m by 2100, mapped to 1/3/5/7 ft brackets).

### New functions added

| Function | Purpose |
|---|---|
| `applyProjectionMode(year)` | Show/hide Row 2 + set `body.proj` class |
| `setScenario(sc)` | Update toggle state + refresh overlays |
| `setOverlay(key, on)` | Set checkbox + refresh layer visibility |
| `applyClimateOverlays(year, sc)` | Master dispatcher for SLR + infra + heat/precip |
| `_pickSlrFt(year, sc)` | Nearest year bin → ft bracket from `SLR_YEAR_FT` |
| `_pickVuln(vuln, year, sc)` | Nearest year bin lookup into per-asset `vuln` object |

### Data files

- `climate/slr.geojson` — 4 stub polygons at 1/3/5/7 ft along the DE River
  corridor (Marcus Hook → Delaware Memorial Bridge). Filtered via
  `['<=', ['get','ft'], pickedFt]` per year+scenario. **Replace with real
  NOAA SLR Viewer rasters** (`coast.noaa.gov/slrdata/`) vectorized to
  polygons.
- `climate/heat_{bin}_{scenario}.{png|geojson}` and
  `climate/precip_{bin}_{scenario}.{png|geojson}` — **not yet populated**;
  layer IDs `heat-raster` / `precip-raster` are wired in
  `applyClimateOverlays` but the source tiles need to be downloaded from
  NOAA LOCA2.

---

## Time Slider — Phase 3: Infrastructure Assets (2026-04-18)

Adds a point layer of DE-relevant critical infrastructure with per-year +
per-scenario vulnerability ratings and clickable source-report citations.

### Data files

- `infrastructure.geojson` — 12 hand-curated assets. Per feature:
  `asset_type`, `operator`, `name`, `summary`, `sources` (array of
  report_id keys), and a `vuln` object:

  ```json
  { "2030": {"rcp45":"low","rcp85":"moderate"},
    "2050": {"rcp45":"moderate","rcp85":"high"},
    "2075": {"rcp45":"high","rcp85":"severe"},
    "2100": {"rcp45":"high","rcp85":"severe"} }
  ```

  Ratings scale: `low` → `moderate` → `high` → `severe` (color-coded
  `#5aa450` → `#e6a43a` → `#e27138` → `#c0392b`). Seed ratings are
  first-pass synthesized from the source reports; **refine against the
  actual CVA / CRSP PDF figures** before citing in advocacy materials.

  Assets included:

  | Asset | Type | Operator |
  |---|---|---|
  | Wilmington Amtrak Station | rail_station | Amtrak |
  | Shellpot Creek Rail Bridge | rail_bridge | Amtrak |
  | Edgemoor Rail Yard | rail_yard | Amtrak |
  | Claymont SEPTA/Amtrak Station | rail_station | SEPTA/Amtrak |
  | Port of Wilmington | port | Diamond State Port Corp |
  | Delaware Memorial Bridge (I-295) | highway_bridge | DRBA |
  | I-95 @ Claymont | highway | DelDOT |
  | Delmarva Hay Road Power Complex | power_generation | Calpine / PJM |
  | Delmarva Edge Moor Substation | substation | Delmarva Power |
  | Wilmington Hospital | hospital | ChristianaCare |
  | Philadelphia International Airport | airport | City of Phila |
  | Southbridge Neighborhood | residential_area | City of Wilmington |

- `reports.yaml` (human-editable) + `reports.json` (runtime; keep in sync).
  Citation table keyed by `report_id` → `{ title, author, year, url }`.
  Includes: `amtrak_cva_2022`, `amtrak_crsp_2022`, `amtrak_phase_iii_2017`,
  `dnrec_cap_2021`, `de_slr_2017`, `deldot_sip_2017`, `resilient_wilmington`,
  `ncc_2050_el_l`, `nj_transit_rutgers_2014`, `phl_cva`, `usace_naccs_2015`,
  `drbc_building_blocks_2024`.

### Map layers

- `infra-markers` — circle layer, radius + color driven by
  `['get','currentVuln']`. `applyClimateOverlays` writes `currentVuln`
  onto each feature's properties then `setData`s the source — same pattern
  as `applyYearToBG`.
- `infra-labels` — asset name text at zoom ≥ 11.

### Click → `showInfrastructurePanel(props)`

Renders in the shared side panel:
- Current rating badge (color-coded).
- Full 4×2 year × scenario matrix (2030/2050/2075/2100 × RCP 4.5/8.5).
- Asset details: type, operator, ID.
- Source-report citations with external links, resolved via `reportsMeta`.

Handles both raw-object and string-flattened `vuln` / `sources` fields
since Mapbox `['get', ...]` sometimes flattens nested JSON to strings.

### `downloadReport()` extension

When `currentYear >= 2026`, the generated `.txt` advocacy report gets a
`CLIMATE PROJECTION CONTEXT` block listing:
- Scenario (RCP 4.5 or 8.5)
- Active overlays
- Nearby infrastructure assets within 30 mi + their rating
- Source-report citations for those assets

---

## Still to do (external, user-run)

1. Run `scripts/fetch_ejscreen_history.py` against EPA gaftp to populate
   real 2015–2024 EJScreen vintages into `de_blockgroups_history.json`.
2. Add `scripts/bg10_to_bg20_DE.csv` (Census 2010→2020 BG crosswalk).
3. Download real NOAA SLR rasters (`coast.noaa.gov/slrdata/`) and
   vectorize → replace `climate/slr.geojson` stub.
4. Download NOAA LOCA2 downscaled heat + precip rasters; populate
   `climate/heat_*.{png|geojson}` and `climate/precip_*.{png|geojson}`.
5. Refine per-asset `vuln` ratings against the actual figures in
   Amtrak CVA 2022, DNREC CAP 2021, and DelDOT SIP 2017.

---

## Pending Tasks

### 1. Run EJScreen data refresh (HIGHEST PRIORITY)

`de_blockgroups.geojson` still needs all EJScreen fields populated, including
`edu_nohsdip_pct`. Run the new script from your local Mac:

```bash
cd ~/Documents/cc4ej-ci-map
python3 scripts/update_ejscreen.py
git add de_blockgroups.geojson
git commit -m "Refresh EJScreen 2023 data"
git push origin main
```

The `index.html` panel already shows `—` for any unpopulated fields.

### 2. CAFO density layer (discussed, not built)

A block-group-level heatmap of chicken house density for Sussex County would
complement the 4 new processing plant dots. Source: DNREC CAFO permit list
(downloadable spreadsheet). Would need a script to join permit addresses to
block groups and add a `cafo_density` property to `de_blockgroups.geojson`.

### 3. Remaining facility coordinate verification

LANXESS, Valtris, Evonik, Mexichem/Vestolit still need address-level geocoding.
Run `scripts/verify_facilities.py --output report.md` to check all facilities
against EPA ECHO automatically, then manually confirm any flagged mismatches.

---

## CAFO Facilities Added (2026-04-13)

Four major Delaware poultry processors added to `facilities.json` with `impact: "ag"`:

| Name | Coordinates | Key EJ issue |
|---|---|---|
| Perdue Foods — Georgetown | `-75.3814, 38.6803` | ~50% Hispanic/Latino, 2025 hazmat shelter-in-place |
| Mountaire Farms — Millsboro | `-75.3432, 38.5784` | $650K DNREC consent agreement 2019, groundwater contamination |
| Mountaire Farms — Selbyville | `-75.2212, 38.4585` | ProPublica high-risk salmonella rates |
| Allen Harim — Harbeson | `-75.2887, 38.7192` | DNREC corrective action April 2021 |

Pre-existing CAFO dots: Perdue Milford (`-75.4348, 38.912`),
Allen Harim Millsboro (`-75.2708, 38.5697`), Indian River Power (`-75.2339, 38.5853`).

---

## Git / Deploy

- Auto-deploys to Vercel from `main`
- If push is rejected (non-fast-forward): `git pull origin main --rebase` then push again
- User's local clone is at `~/Documents/cc4ej-ci-map` on their Mac
