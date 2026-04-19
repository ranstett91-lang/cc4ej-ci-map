#!/usr/bin/env python3
"""
fetch_ejscreen_history.py — build de_blockgroups_history.json across vintages.

Powers the time-series slider. Downloads each published EJScreen state-level
CSV for Delaware (2015 → 2024) from the EPA gaftp archive, normalizes field
names across vintages, crosswalks 2010 BG GEOIDs to 2020 where needed, and
writes a single year-major JSON file that index.html loads at startup.

Output shape (year-major for fast per-tick lookup):
    { "2015": { "GEOID": {"eb": 3.4, "sv": 5.1, "p_pm25": 72, ... }, ... },
      "2016": { ... },
      ... }

Usage:
    python3 scripts/fetch_ejscreen_history.py                # all vintages
    python3 scripts/fetch_ejscreen_history.py --dry-run      # preview
    python3 scripts/fetch_ejscreen_history.py --years 2020,2021,2022
    python3 scripts/fetch_ejscreen_history.py --local-dir ~/ejscreen-zips

Data-source note:
    EPA took the gaftp.epa.gov/EJScreen archive offline in February 2025.
    Network fetches from the old URLs now 404. The canonical mirror is the
    Zenodo archive, DOI 10.5281/zenodo.14767363 (searchable as "EPA
    Environmental Justice Screening Tool (EJ Screen) data, 2015-2024").
    Download the per-year .zip files to a folder, then pass --local-dir.
    The script finds each year's zip by matching the year number in the
    filename.

Notes:
- 2015\u20132020 vintages use 2010 BG GEOIDs; 2021+ use 2020 GEOIDs. Script
  applies a Census 2010\u21922020 relationship crosswalk (bg10_to_bg20_DE.csv)
  with population-weighted allocation for 1\u2192many splits.
- Column names drift across vintages (e.g. MINORPCT \u2192 PEOPCOLORPCT in 2021).
  Handled by VINTAGE_COLMAP below.
- Rate fields are stored \u00d7100 to match the convention in update_ejscreen.py.
- `eb` derived as mean of the 10 environmental-burden state percentiles / 10.
  (Matches the approximation baked into de_blockgroups.geojson to within ~0.1.)
- `sv` is NOT derived here; the baseline geojson's sv is carried forward at
  Phase 1 \u2014 the index.html loader falls through to the baseline when a
  year's sv is missing.

Requires: requests  (pip install requests)
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zipfile
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip install requests first")


ROOT = Path(__file__).parent.parent
OUT_FILE = ROOT / "de_blockgroups_history.json"
CROSSWALK_FILE = ROOT / "scripts" / "bg10_to_bg20_DE.csv"

GAFTP_BASE = "https://gaftp.epa.gov/EJScreen"

# Each vintage has its own archive layout. URLs below were observed on gaftp
# as of this writing; if a vintage 404s the fallback is the USEPA GitHub
# mirror, then the Wayback Machine.
# 2015 is excluded: it uses the original EJScreen v1 schema (lowercase
# `pctile.pm`, `pctlowinc`, `ST`/`statename`, rates as raw percents) that
# predates the v2 national-percentile methodology used from 2016 onward.
# A partial adapter would be methodologically misleading.
VINTAGES: dict[int, dict] = {
    2016: {"url": f"{GAFTP_BASE}/2016/EJSCREEN_V3_USPR_090216_CSV.zip", "geoid_vintage": 2010},
    2017: {"url": f"{GAFTP_BASE}/2017/EJSCREEN_2017_USPR_Public.csv.zip", "geoid_vintage": 2010},
    2018: {"url": f"{GAFTP_BASE}/2018/EJSCREEN_Full_USPR_2018.csv.zip", "geoid_vintage": 2010},
    2019: {"url": f"{GAFTP_BASE}/2019/EJSCREEN_2019_USPR.csv.zip",     "geoid_vintage": 2010},
    2020: {"url": f"{GAFTP_BASE}/2020/EJSCREEN_2020_USPR.csv.zip",     "geoid_vintage": 2010},
    2021: {"url": f"{GAFTP_BASE}/2021/EJSCREEN_2021_USPR.csv.zip",     "geoid_vintage": 2020},
    2022: {"url": f"{GAFTP_BASE}/2022/EJSCREEN_2022_with_AS_CNMI_GU_VI.csv.zip", "geoid_vintage": 2020},
    2023: {"url": f"{GAFTP_BASE}/2023/2.22_September_UseMe/EJSCREEN_2023_BG_with_AS_CNMI_GU_VI.csv.zip", "geoid_vintage": 2020},
    2024: {"url": f"{GAFTP_BASE}/2024/2.3_August_UseMe/EJSCREEN_2024_BG_with_AS_CNMI_GU_VI.csv.zip", "geoid_vintage": 2020},
}

# Canonical field name \u2192 per-vintage override. Most vintages match the
# canonical name; only the drift cases are listed here.
CANONICAL = [
    "ID", "ST_ABBREV",
    "P_PM25", "P_OZONE", "P_DSLPM", "P_CANCER", "P_RESP",
    "P_PTRAF", "P_PNPL", "P_PTSDF", "P_PRMP", "P_PWDIS",
    "LOWINCPCT", "UNEMPPCT", "LINGISOPCT", "LESSHSPCT",
    "UNDER5PCT", "OVER64PCT", "PEOPCOLORPCT",
]
VINTAGE_COLMAP: dict[int, dict[str, str]] = {
    2016: {"ID": "FIPS", "PEOPCOLORPCT": "MINORPCT"},
    2017: {"ID": "ID",   "PEOPCOLORPCT": "MINORPCT"},
    2018: {"ID": "ID",   "PEOPCOLORPCT": "MINORPCT"},
    2019: {"ID": "ID",   "PEOPCOLORPCT": "MINORPCT"},
    2020: {"ID": "ID",   "PEOPCOLORPCT": "MINORPCT"},
    2021: {},
    2022: {},
    2023: {},
    2024: {},
}

# Output property names (match de_blockgroups.geojson convention)
PROP_MAP = {
    "P_PM25": "p_pm25", "P_OZONE": "p_ozone", "P_DSLPM": "p_dslpm",
    "P_CANCER": "p_cancer", "P_RESP": "p_resp", "P_PTRAF": "p_ptraf",
    "P_PNPL": "p_pnpl", "P_PTSDF": "p_ptsdf", "P_PRMP": "p_prmp", "P_PWDIS": "p_pwdis",
    "LOWINCPCT": "lowinc_pct", "UNEMPPCT": "unemp_pct", "LINGISOPCT": "lingiso_pct",
    "LESSHSPCT": "edu_nohsdip_pct", "UNDER5PCT": "under5_pct", "OVER64PCT": "over64_pct",
    "PEOPCOLORPCT": "poc_pct",
}
PERCENTILE_FIELDS = {"P_PM25","P_OZONE","P_DSLPM","P_CANCER","P_RESP",
                     "P_PTRAF","P_PNPL","P_PTSDF","P_PRMP","P_PWDIS"}


def resolve_col(vintage: int, canonical: str) -> str:
    return VINTAGE_COLMAP.get(vintage, {}).get(canonical, canonical)


def load_crosswalk() -> dict[str, list[tuple[str, float]]]:
    """Return {geoid10: [(geoid20, weight), ...]}. Empty dict if file absent."""
    if not CROSSWALK_FILE.exists():
        print(f"  (no crosswalk at {CROSSWALK_FILE.name} \u2014 2015\u20132020 rows will be skipped)")
        return {}
    out: dict[str, list[tuple[str, float]]] = {}
    with CROSSWALK_FILE.open() as f:
        for row in csv.DictReader(f):
            g10 = row["GEOID10"].strip()
            g20 = row["GEOID20"].strip()
            try:
                w = float(row.get("WEIGHT", 1.0))
            except ValueError:
                w = 1.0
            out.setdefault(g10, []).append((g20, w))
    return out


def _read_csv_or_zip(path: Path) -> list[dict]:
    """Reads EJScreen rows from either a .csv.zip, a .zip containing a CSV,
    or a plain .csv file. Uses utf-8-sig so byte-order marks (which EPA
    ships in 2024's CSV header) don't end up baked into the first column
    name as a literal \\ufeff prefix."""
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", errors="replace") as f:
            return list(csv.DictReader(f))
    return _read_zip(path)


def _read_zip(path_or_bytes) -> list[dict]:
    """Accepts a Path to a .zip OR bytes; returns parsed rows from the first CSV."""
    src = (path_or_bytes if isinstance(path_or_bytes, bytes)
           else Path(path_or_bytes).read_bytes())
    with zipfile.ZipFile(io.BytesIO(src)) as zf:
        csv_name = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
        if not csv_name:
            raise RuntimeError("no CSV inside zip")
        with zf.open(csv_name) as f:
            text = io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace")
            return list(csv.DictReader(text))


def fetch_zip_csv(url: str, timeout: int = 60) -> list[dict]:
    print(f"  downloading {url}")
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return _read_zip(resp.content)


def find_local_zip(local_dir: Path, vintage: int) -> Path | None:
    """Locate the BG-level EJScreen CSV for a given vintage inside local_dir.

    The Zenodo record organizes data as local_dir/{YEAR}/... with each year
    holding a mix of the main CSV.zip (or raw CSV), ACS input tables, gdb
    exports, tech documents, and sometimes versioned sub-folders (2024 has
    2.30_DoNotUse, 2.31_useMe, 2.32_UseMe). We recursively walk the year
    folder, accept either .zip or plain .csv, exclude non-data files and
    "DoNotUse" paths, and prefer the main block-group dataset over
    state-percentile / tract variants.
    """
    if not local_dir.is_dir():
        return None
    year_str = str(vintage)
    year_root = local_dir / year_str
    search_root = year_root if year_root.is_dir() else local_dir

    EXCLUDE_NAME = ("acs", "race", "ethnicity", "subgroup", "inputs_raw",
                    "moe", "fieldnames", "technical", "userguide",
                    "readme", "regions", "states", ".gdb.zip", ".gdb",
                    "how_to_upload", "_lookup", "_columns",
                    "descriptions", "field")
    EXCLUDE_PATH = ("donotuse",)

    candidates: list[Path] = []
    for p in search_root.rglob("*"):
        if not p.is_file():
            continue
        suf = p.suffix.lower()
        full = p.name.lower()
        # Accept *.zip and *.csv — EJScreen vintages ship either.
        if suf not in (".zip", ".csv"):
            continue
        # .csv.zip has suffix .zip; the combined check below handles both.
        if any(x in full for x in EXCLUDE_NAME):
            continue
        if any(x in str(p).lower() for x in EXCLUDE_PATH):
            continue
        candidates.append(p)

    if not candidates:
        return None

    def rank(p: Path) -> tuple:
        s = str(p).lower()
        n = p.name.lower()
        return (
            1 if "tract" in n else 0,             # prefer BG over tract
            1 if "statepct" in n else 0,          # prefer national percentiles
            0 if "useme" in s else 1,             # prefer UseMe over useMe/other
            -p.stat().st_size,                    # prefer larger (main CSV)
        )
    candidates.sort(key=rank)
    return candidates[0]


def coerce(val: str, kind: str) -> float | None:
    if val is None or val == "" or val.lower() == "null":
        return None
    try:
        n = float(val)
    except ValueError:
        return None
    return round(n, 1) if kind == "percentile" else round(n * 100, 1)


def _sniff_col(rows: list[dict], candidates: list[str]) -> str | None:
    """Return the first column name from candidates that matches a header,
    case-insensitively and tolerant of a leading BOM or whitespace."""
    if not rows:
        return None
    headers = list(rows[0].keys())
    norm = {h.strip().lstrip("\ufeff").upper(): h for h in headers}
    for c in candidates:
        key = c.strip().lstrip("\ufeff").upper()
        if key in norm:
            return norm[key]
    return None


def _match_de(row: dict, st_col: str) -> bool:
    """Row belongs to Delaware? Accepts DE abbreviation or full state name."""
    val = (row.get(st_col) or "").strip().upper()
    return val in ("DE", "DELAWARE")


def build_year(vintage: int, spec: dict, crosswalk: dict,
               local_dir: Path | None = None) -> dict:
    # Prefer a locally-downloaded zip if the user pointed us at one. EPA took
    # the gaftp archive offline in Feb 2025, so network fetches from the old
    # URLs 404. Zenodo DOI 10.5281/zenodo.14767363 mirrors every year as a
    # single .zip — download once, drop into --local-dir, run this script.
    local_path = find_local_zip(local_dir, vintage) if local_dir else None
    if local_path:
        print(f"  reading local {local_path.name}")
        rows = _read_csv_or_zip(local_path)
    else:
        rows = fetch_zip_csv(spec["url"])

    # Sniff state + ID columns from the actual header rather than trusting
    # the per-vintage COLMAP, which goes stale as EPA renames columns.
    st_col = _sniff_col(rows, [
        resolve_col(vintage, "ST_ABBREV"),
        "ST_ABBREV", "STATE_ABBR", "STATE_NAME", "STATE", "STATEABBREV",
        "stabbrev", "state_abbrev", "stname", "stateabrv",
    ])
    id_col = _sniff_col(rows, [
        resolve_col(vintage, "ID"),
        "ID", "FIPS", "GEOID", "BLOCK_GROUP_FIPS", "BLOCKGROUP_FIPS",
        "BLKGRP_FIPS", "BG_FIPS", "GEO_ID",
    ])
    if not st_col or not id_col:
        hdrs = list(rows[0].keys()) if rows else []
        print(f"  could not locate state/ID columns in {vintage}")
        print(f"  state matched: {st_col}; id matched: {id_col}")
        print(f"  full headers ({len(hdrs)}): {hdrs}")
        return {}
    print(f"  using columns: state={st_col}, id={id_col}")

    de_rows = [r for r in rows if _match_de(r, st_col)]
    print(f"  {len(de_rows)} Delaware rows")

    by_geoid: dict[str, dict] = {}
    for r in de_rows:
        geoid_raw = str(r.get(id_col, "")).strip()
        # Some vintages store FIPS as a float like "100030101051.0" — strip
        # the trailing .0 so zfill doesn't pad a garbage string.
        if geoid_raw.endswith(".0"):
            geoid_raw = geoid_raw[:-2]
        geoid = geoid_raw.zfill(12)
        if geoid == "000000000000":
            continue  # empty row
        targets = [(geoid, 1.0)]
        if spec["geoid_vintage"] == 2010 and crosswalk:
            mapped = crosswalk.get(geoid)
            if mapped:
                targets = mapped

        record: dict[str, float | None] = {}
        p_vals: list[float] = []
        for ej in PROP_MAP:
            src = resolve_col(vintage, ej)
            kind = "percentile" if ej in PERCENTILE_FIELDS else "rate"
            val = coerce(r.get(src), kind)
            record[PROP_MAP[ej]] = val
            if ej in PERCENTILE_FIELDS and val is not None:
                p_vals.append(val)
        if p_vals:
            record["eb"] = round(sum(p_vals) / len(p_vals) / 10, 2)

        for (g20, w) in targets:
            existing = by_geoid.get(g20)
            if not existing:
                by_geoid[g20] = {k: v for k, v in record.items()}
            else:
                for k, v in record.items():
                    if v is None:
                        continue
                    cur = existing.get(k)
                    existing[k] = v if cur is None else round(cur + v * w, 2)
    return by_geoid


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--years", default="",
                    help="Comma-sep list, e.g. 2020,2021 (default: all)")
    ap.add_argument("--local-dir", default="",
                    help="Folder of downloaded EJSCREEN_{YEAR}*.zip files "
                         "(e.g. from Zenodo DOI 10.5281/zenodo.14767363). "
                         "If set, used instead of network fetch.")
    args = ap.parse_args()

    years = (
        [int(y) for y in args.years.split(",") if y.strip()]
        if args.years else sorted(VINTAGES.keys())
    )

    local_dir = Path(args.local_dir).expanduser() if args.local_dir else None
    if local_dir and not local_dir.is_dir():
        sys.exit(f"--local-dir does not exist: {local_dir}")

    crosswalk = load_crosswalk()
    out: dict[str, dict] = {}
    if OUT_FILE.exists():
        out = json.loads(OUT_FILE.read_text())

    for y in years:
        spec = VINTAGES.get(y)
        if not spec:
            print(f"skip {y}: no vintage URL configured")
            continue
        print(f"\nEJScreen {y}:")
        try:
            out[str(y)] = build_year(y, spec, crosswalk, local_dir=local_dir)
            print(f"  -> {len(out[str(y)])} GEOIDs stored")
        except Exception as e:
            print(f"  FAILED: {e}")

    if args.dry_run:
        print("\nDRY RUN \u2014 not writing.")
        return

    OUT_FILE.write_text(json.dumps(out, separators=(",", ":")))
    total_keys = sum(len(v) for v in out.values())
    print(f"\nWrote {OUT_FILE.name}  ({len(out)} years, {total_keys} GEOID-year rows)")


if __name__ == "__main__":
    main()
