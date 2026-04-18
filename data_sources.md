# Delaware Cumulative Impacts Pipeline — Data Source Inventory

_Last updated: 2026-04-01_

---

## A. Environmental Burden (EB) — Block Group Level

### 1. EPA EJScreen 2023 Block Group State Percentiles
| Field | Value |
|---|---|
| **URL** | `https://services2.arcgis.com/iq8zYa0SRsvIFFKz/arcgis/rest/services/EJSCREEN_2023_BG_StatePct_with_AS_CNMI_GU_VI_gdb/FeatureServer/0/query` |
| **Vintage** | 2023 (ACS 2017–2021 base) |
| **Unit** | Census block group (12-char GEOID) |
| **Access** | Public ArcGIS FeatureServer; paginated 500 records |
| **Fields used** | `P_PM25`, `P_OZONE`, `P_DSLPM`, `P_CANCER`, `P_RESP`, `P_PTRAF`, `P_PNPL`, `P_PTSDF`, `P_PRMP`, `P_PWDIS` (all state percentile, 0–100) |
| **Notes** | `CNTY_NAME` field is mislabeled for DE (county FIPS digits in GEOID are swapped); pipeline uses `CNTY_NAME` directly to correct this. Original EPA MapServer at `geodata.epa.gov/OEI/EJSCREEN` was retired. |

### 2. EPA EJScreen 2024 (DNREC-hosted)
| Field | Value |
|---|---|
| **URL** | `https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Society/DE_EJScreen/FeatureServer` |
| **Layers** | 3: EJ Index 2022; 4: Supplemental Index 2023; 5: EJ Index 2024 |
| **Access** | Public FirstMap FeatureServer |
| **Notes** | DNREC-maintained mirror of official EJScreen for permit review use. More current than the AGOL source above. **Recommended for future pipeline upgrade.** |

---

## B. Social Vulnerability (SV) — Block Group Level

### 3. EJScreen Demographic / SV Fields
| Field | Value |
|---|---|
| **Source** | Same FeatureServer as item 1 above |
| **Fields used** | `LOWINCPCT`, `UNEMPPCT`, `LINGISOPCT`, `LESSHSPCT`, `UNDER5PCT`, `OVER64PCT`, `P_LIFEEXPPCT` |
| **Notes** | Raw decimal rates (0–1) except `P_LIFEEXPPCT` which is already a percentile. Multiplied ×100 in pipeline before scoring. |

### 4. CDC PLACES — Census Tract Health Outcomes
| Field | Value |
|---|---|
| **URL** | `https://chronicdata.cdc.gov/resource/cwsq-ngmh.json` |
| **Vintage** | 2025 release (BRFSS 2022 base) |
| **Unit** | Census tract (11-char GEOID) |
| **Access** | Socrata SoQL API; public |
| **Pipeline fields used** | `CASTHMA`, `CHD`, `DEPRESSION`, `COPD`, `CSMOKING`, `STROKE`, `MHLTH` (crude prevalence %) |
| **Filter** | `stateabbr='DE' AND length(locationname)=11` |
| **Notes** | `geographylevel` column does not exist in this dataset; filter by `length(locationname)=11` to select census tracts. Health data assigned to all child block groups within each tract (privacy floor — no sub-tract data available). Contributes 40% of SV score. |

### 4a. CDC PLACES — Observed Health Outcomes Side-Car (`places_tracts.json`)
| Field | Value |
|---|---|
| **Builder** | `scripts/build_places_tracts.py` (repo-local; requires `requests`) |
| **Output** | `places_tracts.json` — keyed by 11-char tract GEOID; joined to each block group at popup time by GEOID prefix |
| **Measures surfaced in UI** | `CASTHMA`, `CANCER`, `CHD`, `COPD`, `STROKE`, `DEPRESSION`, `BPHIGH`, `DIABETES`, `KIDNEY`, `OBESITY`, `CSMOKING`, `MHLTH`, `PHLTH` (crude prevalence %, adults 18+) |
| **Why a side-car** | The observed prevalence values were used inside the pipeline to compute the `sv_health` composite stored on each block group, but the individual prevalence fields were not persisted to `de_blockgroups.geojson`. The side-car restores them for display without a pipeline rebuild. |
| **Display conventions** | Rendered in a dedicated "Observed health outcomes" section of the block-group info panel, visually distinct from modeled EJScreen exposure percentiles. Persistent caveat copy notes tract-level resolution, adult-only scope, and the exposure-vs-observed distinction. Fallback label "—" shown when a tract has no PLACES row. |
| **Refresh cadence** | Annual, to track CDC PLACES releases (yearly since 2019). Stub ships empty so the UI degrades gracefully until `build_places_tracts.py` is run. |

### 4b. Pollutant → Health Linkage Table (`pollutant_health_links.json`)
| Field | Value |
|---|---|
| **Purpose** | Lets a resident see which observed health outcomes are epidemiologically linked to the specific pollutants they are exposed to in their block group (and which pollutants in their block group drive the observed outcomes they see). |
| **Accepted citation sources (peer-reviewed / regulator-grade only)** | EPA Integrated Science Assessments (ISA); EPA IRIS; IARC Monographs; ATSDR Toxicological Profiles; Health Effects Institute (HEI) reports and panels; California Air Resources Board (CARB) determinations; U.S. Surgeon General reports. No news media, blogs, advocacy syntheses, or modeled-only exposure indices are cited. |
| **Language policy** | Association-level only — "linked to", "associated with", "elevated risk in peer-reviewed epidemiology". No causal claim at the individual patient level; the map displays a persistent "Association, not individual causation" caveat in the narrative lede. |
| **Gating** | Pollutant-row annotations are only shown when that pollutant is at or above the 75th state percentile in this block group, so low-burden block groups are not labeled with scary endpoints they do not plausibly experience. Facility chemical annotations are unconditional (the chemical is, by definition, present). |
| **UI treatment** | All annotations are collapsed by default via `<details>`; clicking expands a small citation block with the source name, strength-of-evidence badge, and a direct link to the authoritative document. Designed to satisfy "supporting data accessible, not cluttering." |
| **Fields** | `pollutants{key: {endpoints[], places_measures[]}}`, `chemical_aliases`, `_meta.accepted_sources`, `_meta.strength_legend`, `_meta.endpoint_to_places_measure` |

---

## C. ZIP-Level Health (Further Research Needed)

### 5. DHSS My Healthy Community — Community Profile Reports
| Field | Value |
|---|---|
| **URL** | `https://myhealthycommunity.dhss.delaware.gov/cpr/zip-code-<ZIP>` |
| **Vintage** | 2020 BRFSS data; updated annually |
| **Unit** | ZIP code |
| **Access** | **Bot-protected (HTTP 999 / Cloudflare) — cannot be fetched programmatically.** Manual PDF or page export only. |
| **Key indicators** | Cancer, heart disease, COPD, depression, stroke, obesity, smoking, opioid overdoses |
| **Example (ZIP 19703 — Claymont)** | Heart disease 5.6% (state 4.2%), depression 17.9% (state 16.4%), smoking 15.9% (state 13.4%) |
| **Status** | **Not currently integrated.** No code path consumes DHSS data; the app's health indicators come from CDC PLACES (Section B) at census-tract / block-group resolution. |

#### Why this gap matters

Without DHSS ZIP-level integration, the app is missing:

- **Opioid overdose rates** — absent from CDC PLACES; central to cumulative-impact arguments in Delaware.
- **Specific cancer incidence** and **stroke** at sub-county resolution — DHSS publishes these; PLACES aggregates differently.
- **State-sourced benchmark** (`state_value`) — lets advocacy framing say "X% above the Delaware average" using DE's own numbers, which carries more weight with state policymakers than federal BRFSS estimates.
- **Delaware-branded narrative** — citing DHSS directly is harder to dismiss than out-of-state federal datasets.

#### Open questions for future investigation

1. **Bulk access.** Does [data.delaware.gov](https://data.delaware.gov) host the underlying BRFSS / Vital Statistics tables (Socrata API) that back the bot-protected My Healthy Community portal? A direct Socrata endpoint would bypass the Cloudflare block.
2. **FOIA / direct contact.** Would DHSS Division of Public Health provide a one-time CSV or recurring feed on request? Cite CC4EJ advocacy purpose.
3. **Geographic reconciliation.** ZIP codes don't nest into census block groups. Evaluate HUD USPS ZIP→tract crosswalks (area / population / residential weighting) to decide whether to (a) join ZIP values onto block groups with a documented apportionment method, or (b) keep ZIP data in a separate lookup panel to avoid introducing error.
4. **Priority ZIPs first.** If manual export is the only path, start with ZIPs overlapping priority communities (19703 Claymont, 19809 Edgemoor, 19720 New Castle, 19801 Wilmington Southbridge) rather than all 60+ DE ZIPs.
5. **Vintage alignment.** DHSS uses 2020 BRFSS; PLACES uses 2022 release (2020 base). Confirm comparable reference years before mixing in the same map layer.

#### Advocacy value if filled

State-sourced opioid and cancer indicators, paired with a DE benchmark, would let the EJ narrative point to Delaware's own health data — strengthening cumulative-impact claims in permit challenges and legislative testimony.

---

## D. Facility Proximity (EB — Point Sources)

### 6. DNREC Air Permitted Facilities
| Field | Value |
|---|---|
| **URL** | `https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Environmental/DE_DNREC_Facilities/FeatureServer/1` |
| **Count** | 1,504 total; 1,065 active (non-closed) |
| **Access** | Public FirstMap FeatureServer |
| **Fields** | `Site_Name`, `Operating_Status`, `Site_Type` (Title V / Synthetic Minor / Natural Minor / General Permit), `DocumentLink` |
| **Notes** | Pipeline uses 22 manually-weighted entries derived from Title V and Synthetic Minor facilities near population centers. Full layer available for distance queries. Source for 2026-04-01 facilities list update. |

### 7. DNREC Remediation (RS) Sites
| Field | Value |
|---|---|
| **URL** | `https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Environmental/DE_DNREC_Facilities/FeatureServer/4` |
| **Count** | 1,269 sites |
| **Geometry** | Polygon (site boundaries) |
| **Access** | Public FirstMap FeatureServer |
| **Notes** | State-level Superfund equivalents. Polygon centroids could supplement or replace `P_PNPL` (EPA NPL proximity) in EB scoring for DE-specific sites not on federal NPL. |

### 8. DNREC Hazardous Waste Generators
| Field | Value |
|---|---|
| **URL** | `https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Environmental/DE_DNREC_Facilities/FeatureServer/2` |
| **Count** | 624 generators |
| **Access** | Public FirstMap FeatureServer |
| **Fields** | `PiName`, `RegStatusDesc` (Large/Small/CESQG), coordinates |

### 9. DNREC Permits Stack
| Field | Value |
|---|---|
| **URL** | `https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Environmental/DE_DNREC_Permits/FeatureServer` |
| **Layers** | 0: UST; 1: LUST; 2: Septic permits; 3: Biosolids; 4: Large systems |
| **Access** | Public FirstMap FeatureServer |

### 10. DNREC Chemical Neighbors (Tier II)
| Field | Value |
|---|---|
| **URL** | `https://tierii.dnrec.delaware.gov/Account/Login.aspx` |
| **Access** | **Login required** — DE resident or registered user |
| **Notes** | EPCRA Tier II chemical inventory by facility. Contains stored chemical types and quantities not available through EJScreen or NavMap. Community right-to-know data. |

---

## E. Equity Classification Layers

### 11. DelDOT Equity Focus Areas 2024
| Field | Value |
|---|---|
| **URL** | `https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Society/DE_Equity_Focus_Areas/FeatureServer/1` |
| **Vintage** | 2024 (block group) |
| **Unit** | Census block group (GEOID) |
| **Access** | Public FirstMap FeatureServer |
| **Fields** | `GEOID`, `EFA_DESIGNATION` (Significant / Moderate / Not EFA), `TOTAL_POPULATION`, `HISPANIC_LATINO_POP_PERCENT`, `BLACK_POP_PERCENT` |
| **Pipeline use** | Module C; joined to block group scores → `de_efa_comparison.json/.csv` |
| **Key finding** | 72% of "Significant" EFA block groups have EB ≥ 6.0 vs 23% of "Not EFA" blocks — strong concordance with pipeline EB scores. |

### 12. Justice40 Disadvantaged Tracts
| Field | Value |
|---|---|
| **URL** | `https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/usa_november_2022/FeatureServer/0` |
| **Vintage** | Nov 2022 Version 1.0 |
| **Unit** | Census tract |
| **Access** | Public ArcGIS FeatureServer (Esri hosted) |
| **Notes** | Federal Justice40 initiative disadvantaged tract designations. Used by DNREC EJ Area Viewer. Tract-level; would need disaggregation to block group. |

---

## F. Environmental Hazard Context

### 13. DNREC Solid Waste Landfills and Dumps
| Field | Value |
|---|---|
| **URL** | `https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Environmental/DE_DNREC_Facilities/FeatureServer/6` |
| **Access** | Public FirstMap FeatureServer |

### 14. FEMA DFIRM (Flood Zones)
| Field | Value |
|---|---|
| **URL** | `https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Hydrology/DE_DFIRM/MapServer` |
| **Access** | Public FirstMap MapServer |
| **Notes** | Used in Module B (parcel scoring) for flood zone flag. |

### 15. Delaware Coastal Inundation
| Field | Value |
|---|---|
| **URL** | `https://www.dgs.udel.edu/projects/coastal-inundation-maps-delaware` |
| **Source** | University of Delaware, Delaware Geological Survey |
| **Notes** | Sea-level rise and storm surge inundation scenarios. More granular than FEMA DFIRM for coastal SLR risk. Not yet integrated into pipeline. |

---

## G. Reference / Comparison Tools

### 16. DNREC EJ Area Viewer v2
| Field | Value |
|---|---|
| **URL** | `https://experience.arcgis.com/experience/dbb99894d4ca4b1c81e675be184cca79?org=DNREC` |
| **Type** | ArcGIS Experience Builder |
| **Layers** | EJScreen 2024, Justice40, EFA 2024, all DNREC permit/facility layers, parcel layers |
| **Notes** | DNREC's official EJ tool used for permit review (Title VI, EJAV). Includes feedback form. **Useful as validation reference.** |

### 17. DNREC NavMap
| Field | Value |
|---|---|
| **URL** | `https://dnrec.maps.arcgis.com/apps/webappviewer/index.html?id=573d0ba17dd04c0eb2d7a8f15f74f5d4` |
| **Type** | ArcGIS WebApp Viewer |
| **Layers** | DE DNREC Facilities, Permits, Parcels, DFIRM, Wetlands, Watersheds, Contours |
| **Notes** | General-purpose DNREC environmental layers. Primary visual reference for facility siting. |

### 18. Drexel EJ Map
| Field | Value |
|---|---|
| **URL** | `https://storymaps.arcgis.com/stories/f6f0b2a6e02b4ed99bde53c36444f9e5` |
| **Type** | ArcGIS StoryMap |
| **Notes** | Drexel University EJ analysis for Delaware. Review for methodological comparison and community framing. |

### 19. PCIST — People's Cancer Incidence Screening Tool (Marcus Hook / SE Delco, PA)
| Field | Value |
|---|---|
| **URL** | `https://pcist.net/elementor-226/` |
| **Report** | `https://pcist.net/wp-content/uploads/2025/08/CCIR-Marcus-Hook.pdf` |
| **Vintage** | 2025 (20-year data: PA Cancer Registry 2002–2021) |
| **Geography** | Marcus Hook Borough, PA and SE Delaware County, PA municipalities |
| **Key findings** | Marcus Hook laryngeal cancer 280% above US rate; lung 129% above US; liver 168% above US; pediatric liver 2,362% above US. SE Delco region (Tinicum, Eddystone, Chester, Trainer, Marcus Hook) shows systematic elevation across multiple cancer types. |
| **Relevance** | Marcus Hook is immediately across the PA border from Claymont, DE — same industrial airshed. DNREC 2019 VOC study tested whether Marcus Hook emissions reach Claymont. CC4EJ community named "Marcus Hook refinery" as top air concern (Sept. 2025 listening session). PCIST data provides the downstream health outcome evidence for cross-state cumulative impacts. |
| **Contact** | PCIST@pm.me — citizens' project, open to collaboration |

### 20. Minnesota Cumulative Impacts Map (Reference Model)
| Field | Value |
|---|---|
| **URL** | `https://pca-gis02.pca.state.mn.us/ci-map/` |
| **Source** | Minnesota Pollution Control Agency |
| **Notes** | Permit-linked cumulative impacts tool. Used as design reference for DE pipeline. Key feature: CI scores are directly surfaced during permit application review. |

---

## Pipeline Output Files

| File | Description |
|---|---|
| `de_blockgroup_scores.json` / `.csv` | 700 DE block groups with EB/SV scores, indicators, CDC PLACES health |
| `de_efa_comparison.json` / `.csv` | Block group scores joined with DelDOT EFA 2024 designations |
| `de_parcel_scores.json` / `.csv` | NCC parcel-level EB scores (requires `--parcel` flag + geopandas) |
| `dhss_zip_health.csv` | _(not currently used)_ Placeholder slot for DHSS ZIP-level health data — see Section C for the research gap and open questions. |
