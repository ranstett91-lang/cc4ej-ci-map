# Data Schemas

Reference for the JSON files `index.html` loads at startup. Keeping these
shapes stable is how the map survives an ingest pipeline rewrite.

## `de_blockgroups_history.json`

Year-major, GEOID-indexed. Every known block-group-year gets one record.

```jsonc
{
  "2023": {
    "100030101011": {
      "eb":            3.4,     // environmental burden, 0–10
      "sv":            5.1,     // social vulnerability, 0–10 (carried from baseline if null)
      "p_pm25":        72,      // EJScreen percentile 0–100
      "p_ozone":       65,
      "p_dslpm":       81,
      "p_cancer":      70,
      "p_resp":        68,
      "p_ptraf":       55,
      "p_pnpl":        30,
      "p_ptsdf":       22,
      "p_prmp":        44,
      "p_pwdis":       18,
      "lowinc_pct":    38.2,    // percent, 0–100
      "poc_pct":       61.7,
      "lingiso_pct":   4.9,
      "under5_pct":    6.3,
      "over64_pct":    14.1,
      "edu_nohsdip_pct": 11.8,
      "unemp_pct":     6.2,
      "sv_health":     null     // reserved
    }
  },
  "2024": { ... }
}
```

Rules the map relies on:
- Keys are strings. Years, GEOIDs, nested field names — all string.
- `eb` / `sv` are floats on 0–10; `p_*` are integers or floats on 0–100;
  `*_pct` are percent (0–100).
- A missing field is `null` or absent; the loader's `applyYearToBG()`
  merges yearly values over the baseline geojson, so absent fields fall
  through to the baseline value.
- Percentiles can be anchored nationally or to state — pick one per vintage
  and record it in the provenance sidecar. Mixing anchors across years
  breaks the "got redder faster" story.

## `de_blockgroups_history.meta.json` *(sidecar, new)*

Parallel file emitted by `fetch_ejscreen_history.py`. Not loaded by the map
(yet) — exists so a future info-panel can surface "which mirror + hash
backed this coloring."

```jsonc
{
  "schema_version": 1,
  "updated_at":     "2026-04-19T15:30:12+00:00",
  "years": {
    "2023": {
      "dataset":    "ejscreen",
      "vintage":    "2023",
      "mirror":     "harvard_dataverse",
      "url":        "https://dataverse.harvard.edu/...",
      "sha256":     "ab12...ef90",
      "bytes":      218943201,
      "fetched_at": "2026-04-19T15:30:12+00:00"
    }
  }
}
```

## `facilities.json`

Per-feature record. Time-aware fields were added for the slider; older
records may lack them and that's fine — the loader treats missing fields as
"use the static default."

```jsonc
{
  "name":     "Delaware City Refinery",
  "lat":      39.5743,
  "lng":     -75.5916,
  "type":     "refinery",
  "founded":  1956,
  "closed":   null,           // reserved, not yet authoritative
  "weight":   3.0,            // static exposure weight, fallback when tier absent
  "tier":     3.0,            // Phase 4: honest tier (see DATA_PROVENANCE.md)
  "severity": "high",
  "category": "industry",
  "tri_lbs_by_year":    null, // Phase 3: { "2023": 412000, ... }
  "chem_tox_modifier":  null  // Phase 3: RSEI-style multiplier or null
}
```

Year-filtering rule (as implemented in `index.html` today): a facility is
"present" at year Y if `founded <= Y`. `closed_year` is honored when the
data has it; until Phase 3 lands, closures are approximate.

## `chronicle.json` *(reserved, Phase 6)*

Hand-curated pre-1970 narrative cards for the chronicle mode. Shape TBD
when the UI lands; the rough intent is:

```jsonc
[
  {
    "year":       1899,
    "region":     "Claymont",
    "headline":   "Worth Steel opens along the Delaware River",
    "communities": ["Claymont"],
    "pollutants": ["PM", "SO2"],
    "sources":    [{"cite": "...", "url": "..."}]
  }
]
```

## Versioning

Every schema above carries an implicit `schema_version: 1` (explicit in the
sidecar + lock). Bump the version when a field's **meaning** changes, not
when adding optional fields. The loader is additive-tolerant; subtract or
redefine a field and you break it.
