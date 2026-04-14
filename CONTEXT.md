# CC4EJ CI Map — Session Context

> Written to preserve project state across Claude sessions. Update this file
> whenever a significant change is made so the next session can pick up fast.
> Last updated: 2026-04-14

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
  hand-drawn residential box (`addicks-area` source, lat 39.8009–39.8049,
  lon −75.4514 to −75.4478) which was already used for the dashed data-gap
  border. The `addicks-area` GeoJSON feature now carries `eb: 7.37, sv: 2.65`
  so the standard `ebFillExpr()` / `svFillExpr()` expressions work.
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
