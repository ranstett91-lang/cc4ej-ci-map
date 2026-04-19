# FOIA / DUA Ledger

Public records and data-use agreements that back the map's historical
layers. This is a human-maintained registry — update it when you file,
receive, or get denied a request. The pipeline doesn't read this file;
it's for humans to keep track of the long tail.

## Legend

- **state** — one of: `drafted`, `submitted`, `acknowledged`,
  `partial`, `received`, `denied`, `appealed`, `closed`
- **tier** — ingest tier per `DATA_PROVENANCE.md` (B / C / D / E)
- **date** — most recent state change

## Template row

```
- [ ] <agency> — <description>
       tier:   <B|C|D|E>
       state:  drafted
       date:   YYYY-MM-DD
       ref:    <tracking number or internal id>
       notes:  <what we asked for, scope, expected fields>
```

## Open requests

(none filed yet — seed rows below are drafts.)

### Delaware DNREC

- [ ] DNREC Division of Air Quality — permit archive 1970–1986
       tier:   E
       state:  drafted
       date:   —
       ref:    —
       notes:  Scan or index of Title V precursors + early state permits for
               the Claymont/Edgemoor/Delaware City/New Castle City corridor.
               Asking for operator, pollutant, annual tonnage if recorded,
               start + termination dates. Accept PDF scans; scope by
               facility address range if agency prefers.

- [ ] DNREC — Coastal Zone Act compliance records 1971–
       tier:   E
       state:  drafted
       date:   —
       ref:    —
       notes:  All §7-a permits, modifications, and enforcement actions for
               industrial facilities in the coastal zone. Expect PDF-heavy.

- [ ] DNREC — HSCA hazardous-site list metadata
       tier:   E
       state:  drafted
       date:   —
       ref:    —
       notes:  Public portal exists; FOIA only if historical de-listings or
               internal site-characterization reports aren't posted.

### Delaware DPH (Division of Public Health)

- [ ] DPH — Cancer registry, Delaware corridor, 2000–present
       tier:   D
       state:  drafted
       date:   —
       ref:    —
       notes:  Tract-level incidence for lung, leukemia, bladder, breast.
               Likely requires a DUA, not pure FOIA. Aggregate only; we
               are not asking for person-level.

- [ ] DPH — Asthma ED visits + hospitalizations, tract-level, 2005–
       tier:   D
       state:  drafted
       date:   —
       ref:    —
       notes:  Supplements CDC EPHT which is county-only.

- [ ] DPH — Childhood blood-lead screening, tract-level, 2000–
       tier:   D
       state:  drafted
       date:   —
       ref:    —
       notes:  CDC provides aggregated; state has finer geography.

### EPA Region 3

- [ ] EPA R3 — Pre-TRI §112 air toxics narrative filings, DE corridor
       tier:   E
       state:  drafted
       date:   —
       ref:    —
       notes:  Covers 1977–1986 window where we need qualitative release
               data for chronicle cards and tier-weight calibration.

- [ ] EPA R3 — Superfund pre-listing site investigation reports
       tier:   E
       state:  drafted
       date:   —
       ref:    —
       notes:  Fills the "what did anyone know in 1978?" gap.

### Neighbor states

- [ ] NJDEP — Pre-1987 air permit + enforcement archive, Salem/Gloucester Cos.
       tier:   E
       state:  drafted
       date:   —
       ref:    —
       notes:  Fenceline to Wilmington / Claymont / Delaware City.

- [ ] PA DEP — Pre-1987 air permit + enforcement archive, Delaware County
       tier:   E
       state:  drafted
       date:   —
       ref:    —
       notes:  Marcus Hook / Chester fenceline.

### Archival / academic

- [ ] UD Library — CCRS pre-1970 environmental-health file series
       tier:   C
       state:  drafted
       date:   —
       ref:    —
       notes:  Not a FOIA; a finding-aid request + possible on-site scan.
               Feeds chronicle cards.

- [ ] Wilmington News Journal — digitized archive access (institutional)
       tier:   C
       state:  drafted
       date:   —
       ref:    —
       notes:  Fish-kill / smokestack reporting 1950–1969 for chronicle.

## Received / closed

(none yet)

## Denied / appealed

(none yet)
