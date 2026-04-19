# Ingest Architecture

The goal of the ingest layer is survivability: every pixel the map paints must
be traceable to a raw file with a pinned SHA-256, and that raw file must be
re-obtainable from at least one mirror that isn't the federal agency that
published it. If EPA takes down a dataset tomorrow, CI still passes and the
map still rebuilds.

## The pieces

```
ingest/
  manifest.yaml            # canonical source + mirror registry (edit this)
  snapshots.py             # download + hash + lock (networked, human-run)
  verify.py                # hash-check lock vs disk (no network, CI-run)
  requirements.txt         # requests, PyYAML
snapshots/
  MANIFEST.lock.yaml       # one entry per (source, vintage): mirror, url,
                           # sha256, bytes, fetched_at
data_raw/                  # gitignored — rebuildable from lock via `make fetch`
  ejscreen/2023/EJSCREEN_2023_BG_with_AS_CNMI_GU_VI.csv.zip
scripts/
  fetch_ejscreen_history.py  # downstream transformer; calls ingest.snapshots
.github/workflows/
  verify.yml               # runs `python -m ingest.verify` on every PR
Makefile                   # unified entrypoint: fetch, verify, rebuild
```

## Why this shape

- **`manifest.yaml` is the only place mirrors live.** Adding a mirror
  (PEDP bucket URL, new Harvard Dataverse DOI, a fresh EDGI clone) is a
  one-line YAML edit, no code change.
- **`snapshots.py` is the only thing that writes the lock.** One file that
  both humans and downstream transformers call, so provenance always ends up
  in the same place.
- **`verify.py` never touches the network.** CI stays deterministic: it
  hashes what's on disk and compares to what's in the lock, nothing else. A
  CI runner in a political hurricane doesn't need a working EPA domain to
  keep the build green.
- **`data_raw/` is gitignored.** Large binaries don't belong in the repo.
  Anyone who wants to rebuild runs `make rebuild` and the lock pins exactly
  which file they should have received.

## Mirror priority model

Each source in `manifest.yaml` lists mirrors with an integer `priority` —
**lower is more trusted**. `snapshots.fetch_with_fallback` walks them in
order and returns the first one that succeeds. The priority ordering encodes
a political thesis:

| priority | mirror            | rationale                                                  |
|---------:|-------------------|------------------------------------------------------------|
| 1        | PEDP              | University-operated, actively mirroring EPA datasets as of 2025. |
| 2        | Harvard Dataverse | Versioned, DOI-pinned, institutionally redundant.          |
| 3        | EDGI              | Org set up specifically to archive endangered EPA data.    |
| 9        | gaftp.epa.gov     | Original upstream. Last resort — can disappear overnight.  |

If the primary goes dark, you don't edit code: you re-order priorities in
`manifest.yaml`, re-run `make fetch`, and the new source becomes canonical.

## How the lock works

```yaml
# snapshots/MANIFEST.lock.yaml
schema_version: 1
sources:
  ejscreen:
    "2023":
      mirror:     harvard_dataverse
      url:        https://dataverse.harvard.edu/api/access/datafile/...
      filename:   EJSCREEN_2023_BG_with_AS_CNMI_GU_VI.csv.zip
      sha256:     ab12...ef90
      bytes:      218943201
      fetched_at: 2026-04-19T15:30:12+00:00
updated_at: 2026-04-19T15:30:12+00:00
```

Once the lock has an entry for `ejscreen/2023`, every later run verifies
against that hash. A silent retroactive edit upstream (EPA mutates the file,
a mirror swaps in a revised version) fails CI immediately with an
"expected X, got Y" diff. That is the entire point.

## Day-one workflow

```bash
# Install deps once per clone.
make deps

# Fetch all configured vintages of EJScreen (hits mirrors in priority order,
# writes data_raw/ejscreen/<year>/, appends hash to the lock).
make fetch SOURCE=ejscreen

# Or one vintage:
make fetch SOURCE=ejscreen VINTAGES=2023

# Rebuild the downstream JSON the map loads.
make history

# End-to-end from a clean clone:
make rebuild
```

## CI model

`verify.yml` runs on every push and PR. It does not fetch. It reads the
lock, hashes anything still on disk in `data_raw/` (if present), and fails
on drift. On a fresh CI runner, `data_raw/` is empty and the lock is
checked for internal consistency only — that's the expected steady state.
The integrity-critical check happens locally before every merge: a
contributor who touched a raw file can't sneak a mutated hash past CI,
because the lock is in git and they'd have to commit the change explicitly.

## Adding a new source

1. Append a block under `sources:` in `ingest/manifest.yaml`:
   ```yaml
   tri:
     description: "EPA Toxics Release Inventory annual facility reports"
     vintages: {"1987": {}, "1988": {}, ...}
     mirrors:
       - id: epa_tri
         priority: 9
         url_template: "https://www.epa.gov/.../tri_{vintage}_us.csv"
         files: {"2023": "tri_2023_us.csv"}
       - id: harvard_tri_mirror
         priority: 2
         url_template: "..."
         files: {"2023": "..."}
   ```
2. `make fetch SOURCE=tri` — the lock picks up entries automatically.
3. Write a downstream transformer under `scripts/` that calls
   `snap.fetch_with_fallback("tri", vintage)` the same way
   `fetch_ejscreen_history.py` does. No new plumbing needed.

## Optional: off-site mirror

Nothing here requires cloud storage. But when you're ready to push raw
snapshots to S3 / Zenodo / IPFS, add an `offsite:` stanza per source in
`manifest.yaml` pointing at that bucket, and extend `fetch_with_fallback`
to cascade there before upstream. That's a ~20-line change because the
mirror loop already exists.

## What this does NOT do

- It doesn't transform data — that's `scripts/*`.
- It doesn't dedupe across sources.
- It doesn't decide which mirror is "correct" — it trusts the priority
  ordering you wrote.
- It doesn't push to off-site mirrors — that's a deliberate future step, not
  a dependency for day one.

The design is boring on purpose. Boring survives.
