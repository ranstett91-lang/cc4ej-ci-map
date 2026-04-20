# CC4EJ Delaware Cumulative Impacts Map

An interactive environmental-justice map for Delaware. Click any neighborhood
to see wind-adjusted proximity burden scores, cumulative impact indices,
EJScreen indicators, and nearby industrial hazards.

Live site: deploys to Vercel from `main` (see `vercel.json`).

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
- `data_sources.html` — human-readable data-sources page
- `scripts/` — Python data pipeline (EPA ECHO, EJScreen, CDC PLACES refresh)
- `*.json`, `*.geojson`, `*.yaml` — static data assets
- `climate/` — sea-level-rise scenario overlays
- `.github/workflows/refresh-ejscreen.yml` — annual EJScreen refresh
- `CONTEXT.md` — design notes, facility coordinate audit log, data-source
  rationale

## Running locally

Serve the repo root from any static web server, e.g.:

```sh
python3 -m http.server 8000
```

Then open <http://localhost:8000/>.

A Mapbox access token is required for map tiles; see Mapbox's terms at
<https://www.mapbox.com/legal/tos>.
