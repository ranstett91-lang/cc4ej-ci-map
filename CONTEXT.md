# CC4EJ CI Map — Session Context

> Written to preserve project state across Claude sessions. Update this file
> whenever a significant change is made so the next session can pick up fast.
> Last updated: 2026-04-14

---

## Vision

This map has two co-equal goals:

**Advocacy tool** — rigorous enough to use in DNREC permit hearings, legislative
testimony, and public comment periods. Scores must be defensible, sourced, and
comparable to tools regulators already accept (EJScreen, CalEnviroScreen).

**Community empowerment tool** — usable by a resident who has never heard of
EJScreen but knows exactly what it smells like at 2am when the wind shifts. The
map should end with action, not just awareness.

The gap between these two goals is the design challenge. Every feature decision
should be evaluated against both.

---

## What This Map Is

Interactive EJ (environmental justice) map for Claymont/Delaware built with
Mapbox GL JS. Static site — deploys automatically to Vercel from `main` branch.
`index.html` is the entire app; `facilities.json` and `de_blockgroups.geojson`
are the two data files.

---

## Granularity Principle

**Census block groups are too coarse.** This is not a data quality problem — it
is a structural injustice problem. Block groups that include uninhabited
industrial waterfront dilute the pollution burden score for adjacent residential
streets. Three distinct communities (Aniline Village, Hickman Row, Knollwood)
averaged into one number hides each community's specific vulnerability.

Every architectural decision should push toward finer-grained representation:

- EFA residential splits show only inhabited land (not waterfront)
- Proximity CIS computed at exact clicked lat/lng (not BG centroid)
- CIS grid (pending) replaces flat BG color with a continuous exposure surface
- Future: address-level entry point so residents see their specific location

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

### Why EFA splits are colored by proximity CIS, not parent BG EB

EJScreen block-group averages include uninhabited land and smooth over intra-BG
variation. The 88 DelDOT EFA residential split polygons are LULC-clipped to
inhabited areas. Coloring them by a pre-computed proximity CIS (inverse distance
from all weighted facilities) gives a more accurate picture of what residents in
that specific residential patch actually experience. The CIS uses the same
EB_COLORS ramp so the scale is directly comparable.

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
| `weight` | 1.0–3.0 | Circle radius and CIS contribution |
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
| `edu_nohsdip_pct` | EJScreen `LESSHSPCT` |
| `total_pop` | 2020 Decennial (used for EFA splits) |

**Population note:** BG `100030101051` was previously 542 (ACS 5-yr estimate);
updated to 591 to match 2020 Decennial — consistent with the EFA splits already
integrated in the map.

### `efa_splits.geojson`

88 features representing the residential sub-area polygons for 44 Delaware block
groups, clipped to residential LULC by DelDOT for the Equity Focus Area
analysis. Properties include `GEOID`, `efa`, `pop`, `sub_idx`, `neighborhoods`.

At load time, each split is enriched with:
- `eb`, `sv` from the parent BG (for SV mode coloring and panel display)
- `cis` — proximity CIS pre-computed at the split polygon centroid

---

## Layer Architecture

```
bg-fill              — all BGs at 0.30 (EFA split BGs) or 0.72 (all others)
bg-splits-eb-fill    — 88 EFA residential splits at 0.72, colored by cis (EB mode)
                       or parent sv (SV mode); hidden in EFA mode
addicks-eb-fill      — hand-drawn Addicks Estates residential box at 0.72
data-gap-fill        — orange tint over 101051 full polygon (data-gap marker)
addicks-fill         — orange tint over 101041 full polygon (data-gap marker)
bg-outline           — block group borders
```

### Opacity logic

`bgFillOpacityExpr()` fades two groups to 0.30:
- `100030101041` (Addicks Estates) — no EFA split, handled by addicks-eb-fill
- All 44 EFA split GEOIDs (stored in `EFA_SPLIT_GEOIDS` module var)

All other BGs render at 0.72. Residential highlight layers paint on top at 0.72.

---

## Proximity-Weighted Cumulative Impact Score

### Formula

```
CIS(point) = Σᵢ [ weightᵢ × windFactorᵢ ] / max(distᵢ, 0.15 mi)^1.5
```

- `weightᵢ` — facility weight (1.0–3.0) from `facilities.json`
- `windFactorᵢ` — `1.0 + 0.4 × cos(angleDiff × π/180)`: 1.4 upwind → 0.6 downwind
- Distance floor 0.15 mi (~240 m) prevents singularity near facilities
- `haversineKm()` returns miles (R=3958.8) — naming inconsistency, but since
  normalization uses the same function, relative scores are unaffected

### Normalization

`precomputeCISNorm(bgFeatures)` runs at load time. Computes no-wind raw CIS for
all ~700 BG centroids, takes 95th percentile → stored as `CIS_P95`. Click-time:
`normalized = min(10, raw / CIS_P95 × 10)`. No-wind baseline keeps the scale
stable; wind shifts individual scores up/down from that baseline.

### Combined Impact Index

`(CIS_norm / 10) × (SV / 10) × 10` — proximity burden × social vulnerability.
Shown in vulnerability mode as "Vulnerability-Weighted Burden." This is the
CC4EJ analogue of CalEnviroScreen's cumulative impact model.

### Advocacy defensibility

The proximity model mirrors CalEnviroScreen's proximity scores, which have
survived legal scrutiny in California. The 0–10 normalized scale is directly
comparable to EJScreen. Wind adjustment adds a physical basis (prevailing SW
winds funneling emissions toward Claymont) that can be cited in permit comments.

**Limitation to disclose:** This is a proximity model, not a measured
concentration model. It shows who is *near* sources, not monitored pollution
levels. Pair with monitored air quality data and health outcome data when
available. The facility weights (1.0–3.0) are CC4EJ's own classification — a
strength (community-defined) and a vulnerability (challengeable in hearings).

---

## Pending Features (Priority Order)

### 1. CIS Grid — continuous exposure surface (NEXT BUILD)

Replaces flat BG coloring with a sub-BG continuous surface visible at any zoom.

**Steps:**
1. Generate a 0.05° grid of lat/lng points covering Delaware's bounding box
   (~1,400 points)
2. At load time, run `rawProximityCIS` + `normalizeCIS` on each point (reuses
   existing functions — no new math)
3. Build a GeoJSON FeatureCollection of small square polygons, each carrying
   its `cis` score
4. Add as a Mapbox `fill` layer using `cisFillExpr()` at 0.55 opacity, below
   the BG outline layer
5. Hide `bg-fill` when this layer is active (replaces, does not overlay)
6. Wire to EB mode button; SV mode keeps BG fill (no sub-BG SV analog)
7. Add "Proximity grid" checkbox in Layers panel

**What it will look like:** Industrial clusters and highway corridors appear as
dark red hotspots that fade to lighter orange/peach with distance. The Delaware
River corridor from Marcus Hook through Claymont reads as a single burn of high
burden crossing BG boundaries. The pale BG in central Claymont will show the
gradient within it — darker near I-495, lighter toward residential center.
It will look less like a census map and more like a pollution exposure surface.

**Advocacy value:** Shows burden crossing political and census boundaries.
Regulators cannot dismiss a community's exposure by pointing to a favorable
BG average.

### 2. Address-level entry point

"Type your address" → show proximity CIS score, nearest facilities, plain-
language explanation. Most residents will not navigate a map to find themselves.
Required for the tool to be genuinely community-accessible.

### 3. "What this means for you" language

Replace score numbers with plain-language interpretation:
- Not "EB score 7.4"
- Instead: "Your neighborhood ranks higher in pollution burden than 74% of
  Delaware. Here's what's near you: [3 nearest facilities with distance]."

### 4. Action pathway

After the score: open DNREC comment periods, how to submit a comment, contact
info for state reps and DNREC district staff. Without this the map ends at
awareness, not action. This is the difference between an information tool and
an empowerment tool.

### 5. Spanish language

Aniline Village and Knollwood have flagged linguistic isolation scores. The
communities most in need of this tool cannot fully use it in English-only form.
Priority for those two Claymont neighborhoods at minimum.

### 6. Community story layer

The Hickman Row history (first school integration in 17 segregated states), the
Aniline Village naming (National Aniline → Allied Chemical → Honeywell Superfund
lineage), the Great Migration workers at Worth Steel — this context should be on
the map, not buried in a CONTEXT.md file. Residents seeing their own
neighborhood's story on a map is qualitatively different from seeing a score.
Suggested implementation: clickable neighborhood markers with expandable
historical narrative.

### 7. Shareable output / one-page report

A resident should be able to generate: "My neighborhood's burden, what's
causing it, what I can do" — and send it to a city council member or paste it
into a public comment. PDF or shareable link. Makes the tool actionable beyond
the screen.

### 8. Run EJScreen data refresh

`de_blockgroups.geojson` still needs all EJScreen fields populated. Run from
local Mac with internet access:

```bash
cd ~/Documents/cc4ej-ci-map
python3 scripts/update_ejscreen.py
git add de_blockgroups.geojson
git commit -m "Refresh EJScreen 2023 data"
git push origin main
```

### 9. CAFO density layer

Block-group heatmap of chicken house density for Sussex County. Source: DNREC
CAFO permit list. Would need a script to join permit addresses to BGs and add
`cafo_density` property to `de_blockgroups.geojson`.

### 10. Remaining facility coordinate verification

LANXESS, Valtris, Evonik, Mexichem/Vestolit need address-level geocoding.
Run `scripts/verify_facilities.py --output report.md` to check all facilities
against EPA ECHO, then manually confirm flagged mismatches.

---

## Data Pipeline Scripts

### `scripts/update_ejscreen.py`

Fetches all 17 EJScreen EB + SV fields for DE block groups and patches them
into `de_blockgroups.geojson`. Run on a machine with internet access.

Fields fetched: P_PM25, P_OZONE, P_DSLPM, P_CANCER, P_RESP, P_PTRAF, P_PNPL,
P_PTSDF, P_PRMP, P_PWDIS, LOWINCPCT, UNEMPPCT, LINGISOPCT, LESSHSPCT,
UNDER5PCT, OVER64PCT, P_LIFEEXPPCT.

Rate fields (LOWINCPCT, UNEMPPCT, etc.) stored as percentages (×100).

### `scripts/verify_facilities.py`

Queries EPA ECHO API to cross-check facility coordinates against official EPA-
registered locations. Flags any facility > 500 m off. Warehouses and corridors
skipped. NOT FOUND does not mean wrong — some older sites aren't in ECHO.

---

## Facility Coordinate Verification Status

### Verified correct
- Croda Atlas Point — 315 Cherry Lane, New Castle DE → `-75.541, 39.6915` ✓
- Kuehne Chemical — 1645 River Road, Delaware City DE → `-75.6297, 39.6056` ✓
- Nexpera Red Lion — 766 Governor Lea Road → `-75.6334, 39.5929` ✓
- Metachem Products — 745 Governor Lea Road → `-75.6483, 39.6033` ✓
- Monroe Energy Trainer Refinery — 4101 Post Road, Trainer PA → `-75.4037, 39.8210` ✓
- Energy Transfer Marcus Hook Complex — 100 Green St, Marcus Hook PA → `-75.4157, 39.8091` ✓
- ReWorld Chester Incinerator — 10 Highland Ave, Chester PA → `-75.3882, 39.8265` ✓
- Braskem Marcus Hook — south of Blue Ball Ave, west of W 10th → `-75.4200, 39.8135` ✓
- Honeywell Delaware Plant — just north of INEOS → `-75.4370, 39.8072` ✓
- Delaware City Refinery — 4550 Wrangle Hill Rd → `-75.5975, 39.5711` ✓

### Fixed previously (were wrong)
- **Lubrizol** corrected to 76 Porcupine Rd, Pedricktown NJ: `-75.423, 39.764`
- **Energy Transfer Marketing & Terminals** (Claymont duplicate) — removed
- **Sunoco Partners** moved east to `-75.435` (Delaware River waterfront)

### Needs verification
- LANXESS Logan Township NJ — current `-75.375, 39.75`
- Valtris Specialty Chemicals Marcus Hook — current `-75.406, 39.823`
- Evonik Corp Marcus Hook — current `-75.412, 39.821`
- Mexichem/Vestolit Marcus Hook — current `-75.404, 39.826`

---

## CAFO Facilities Added

Four major Delaware poultry processors with `impact: "ag"`:

| Name | Coordinates |
|---|---|
| Perdue Foods — Georgetown | `-75.3814, 38.6803` |
| Mountaire Farms — Millsboro | `-75.3432, 38.5784` |
| Mountaire Farms — Selbyville | `-75.2212, 38.4585` |
| Allen Harim — Harbeson | `-75.2887, 38.7192` |

---

## Git / Deploy

- Auto-deploys to Vercel from `main`
- Feature branch: `claude/fix-impact-map-accuracy-ewlOW`
- If push is rejected: `git pull origin main --rebase` then push again
- User's local clone: `~/Documents/cc4ej-ci-map` on their Mac
