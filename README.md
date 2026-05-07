# CC4EJ Delaware Cumulative Impacts Map

An interactive environmental-justice map for Delaware. Click any neighborhood
to see wind-adjusted proximity burden scores, cumulative impact indices,
EJScreen indicators, and nearby industrial hazards.

Live site: deploys to Vercel from `main` (see `vercel.json`).

## Methodology — read first if you're reviewing the data

The **Facility Burden Index (CIS)** — the sub-neighborhood overlay you
toggle from the floating "Facility burden" pill — has a fully documented,
parity-tested methodology. Current version: **v2.0** (2026-05-07).

- **[METHODOLOGY.md](./METHODOLOGY.md)** — formula, parameters,
  normalization, wind treatment (NOAA wind rose), stack-height dampener,
  weighting rubric, multi-pollutant variants (Cancer / Respiratory /
  Combined), sensitivity analysis, limitations
- **[CHANGELOG.md](./CHANGELOG.md)** — version log v1.0 → v2.0 with
  per-release rationale, files affected, and reproducibility commands
- **[weighting_rubric.md](./weighting_rubric.md)** — six-tier hazard
  rubric; per-facility basis citations live in
  `facility_weight_tiers.csv` and `weight_provenance.csv`
- **[analyses/cis_places_correlation_2026.md](./analyses/cis_places_correlation_2026.md)**
  — empirical validation against CDC PLACES tract-level health prevalence
  (n=257)
- **[analyses/cis_monitor_correlation_2026.md](./analyses/cis_monitor_correlation_2026.md)**
  — empirical validation against EPA AQS measured air quality (n=11 DE
  monitors)

Every weight, score, and confidence interval is reproducible from public
inputs (EPA TRI, NOAA ISD, CDC PLACES, EPA AQS, US Census ACS) via the
`scripts/` pipeline. JS↔Python math parity is enforced by
`scripts/test_cis_parity.py`.

---

## License

**Code** — licensed under the
[PolyForm Noncommercial License 1.0.0](./LICENSE.md).
Free for nonprofit, academic, community, government, personal, and research
use. **Commercial use is not permitted** without a separate license.

**Curated data** (`pollutant_health_links.json`, verified facility
coordinates, community metadata, curated reports and disaster entries) —
licensed under
[CC BY-NC-SA 4.0](./DATA_LICENSE.md).

**Third-party data** (EPA ECHO, EJScreen, CDC PLACES, Census TIGER, Delaware
SLR Committee) is U.S. public domain or government work and is attributed in
[`NOTICE`](./NOTICE).

**Trademark** — "CC4EJ" and the CC4EJ logo are common-law trademarks. See
[TRADEMARK.md](./TRADEMARK.md). Forks must rename.

**Commercial licensing** — for commercial use of the code or curated data,
contact the maintainer at `<YOUR EMAIL>`.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). All contributions require a
Developer Certificate of Origin sign-off (`git commit -s`).

## Project structure

- `index.html` — main single-page app (Mapbox GL JS, no build step)
- `data_sources.html` / `data_sources.md` — human-readable data-sources pages
- `js/cis.js` — pure-functional Facility Burden Index math, loadable in
  the browser AND as a Node CommonJS module (parity-tested against the
  Python reference)
- `scripts/` — Python data pipeline:
  - `_cis_stats.py`, `_chem_categories.py` — shared helpers
  - `fetch_*.py` — public-data fetchers (EPA TRI, NOAA ISD, CDC PLACES,
    EPA AQS, US Census, NLCD)
  - `build_*.py`, `patch_*.py` — derived data builders, idempotent with
    `--dry-run` / `--apply` / `--patch` flags
  - `analyze_*.py` — empirical validation analyses
  - `audit_*.py` — sensitivity + integrity audits
  - `test_cis_parity.py` — JS↔Python parity test (Node-based)
- `analyses/` — empirical validation reports (Markdown)
- `*.json`, `*.geojson`, `*.csv` — static data assets and audit trails
- `climate/` — sea-level-rise scenario overlays
- `.github/workflows/refresh-ejscreen.yml` — annual EJScreen refresh
- `CONTEXT.md` — design notes, facility coordinate audit log, data-source
  rationale
- [METHODOLOGY.md](./METHODOLOGY.md) — Facility Burden Index (CIS)
  formula, parameters, normalization, limitations (v2.0)
- [CHANGELOG.md](./CHANGELOG.md) — methodology version log
- [weighting_rubric.md](./weighting_rubric.md) — six-tier weighting rubric
  for facility hazard weights (1.2–3.0)

## Running locally

Serve the repo root from any static web server, e.g.:

```sh
python3 -m http.server 8000
```

Then open <http://localhost:8000/>.

A Mapbox access token is required for map tiles; see Mapbox's terms at
<https://www.mapbox.com/legal/tos>.
