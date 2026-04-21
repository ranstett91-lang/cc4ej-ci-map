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
# NOTE: 2015 (EJScreen v1) is deliberately excluded. Its schema predates the
# P_* state-percentile system entirely -- only raw rates (pctmin, pctlowinc)
# exist, so the `eb` composite can't be computed. Scrubs to 2015 snap to 2016.
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


def _try_url(url: str, timeout: int) -> list[dict] | None:
    """Download + unzip + parse CSV. Prints diagnostics on failure so the
    caller (and operator) can tell WHY it failed: HTTP status, content-type,
    payload size, and whether the body was actually a zip."""
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
    except requests.RequestException as e:
        print(f"    network error: {e}")
        return None
    if resp.status_code >= 400:
        print(f"    HTTP {resp.status_code} ({len(resp.content)} bytes, "
              f"content-type={resp.headers.get('content-type','?')})")
        return None
    body = resp.content
    if not body[:2] == b"PK":
        ctype = resp.headers.get("content-type", "?")
        print(f"    not a zip: HTTP {resp.status_code}, {len(body)} bytes, "
              f"content-type={ctype}, first-bytes={body[:16]!r}")
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            csv_name = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
            if not csv_name:
                print(f"    zip contains no .csv (members: {zf.namelist()[:5]})")
                return None
            with zf.open(csv_name) as f:
                text = io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace")
                return list(csv.DictReader(text))
    except (zipfile.BadZipFile, OSError) as e:
        print(f"    zip/parse error: {e}")
        return None


def _wayback_lookup(url: str, timestamp: str, timeout: int = 30) -> str | None:
    """Ask the Wayback availability API for the closest snapshot of `url` to
    `timestamp` (YYYYMMDD). Returns a raw-mode (`id_`) archive URL, or None
    if IA has no snapshot. Prevents us from blindly guessing a timestamp
    that was never crawled."""
    api = "https://archive.org/wayback/available"
    try:
        resp = requests.get(api, params={"url": url, "timestamp": timestamp},
                            timeout=timeout, allow_redirects=True)
        if resp.status_code >= 400:
            print(f"    availability API HTTP {resp.status_code}")
            return None
        snap = resp.json().get("archived_snapshots", {}).get("closest") or {}
        if not snap.get("available"):
            return None
        archive_url = snap.get("url")
        if not archive_url:
            return None
        # Availability API returns "https://web.archive.org/web/<TS>/<orig>".
        # Convert to raw-mode by inserting `id_` after the timestamp so we
        # get the original ZIP bytes instead of IA's HTML wrapper.
        parts = archive_url.split("/web/", 1)
        if len(parts) != 2:
            return archive_url
        ts_and_rest = parts[1].split("/", 1)
        if len(ts_and_rest) != 2:
            return archive_url
        ts, rest = ts_and_rest
        return f"{parts[0]}/web/{ts}id_/{rest}"
    except (requests.RequestException, ValueError) as e:
        print(f"    availability API error: {e}")
        return None


def fetch_zip_csv(url: str, timeout: int = 120) -> list[dict]:
    """Fetch a ZIP-wrapped CSV. Tries the original URL first; on failure,
    queries the Wayback Machine availability API to find the closest real
    snapshot (not a guessed timestamp). EPA decommissioned gaftp.epa.gov/
    EJScreen in early 2025, so direct URLs 404 but Wayback may still have
    pre-decom snapshots for some vintages."""
    print(f"  downloading {url}")
    rows = _try_url(url, timeout)
    if rows is not None:
        return rows

    year = next(
        (p for p in url.split("/") if p.isdigit() and len(p) == 4 and 2014 < int(p) < 2030),
        "2024",
    )
    # Try a few timestamps: year of vintage, year after, and just before
    # EPA's early-2025 decom. Availability API picks the closest real snap.
    for ts in (f"{year}1201", f"{int(year)+1}0601", "20250101"):
        wb_url = _wayback_lookup(url, ts)
        if not wb_url:
            print(f"  no Wayback snapshot near {ts}")
            continue
        print(f"  retry via Wayback: {wb_url}")
        rows = _try_url(wb_url, timeout)
        if rows is not None:
            return rows

    raise RuntimeError(f"could not fetch {url} (tried direct + Wayback)")


def coerce(val: str, kind: str) -> float | None:
    if val is None or val == "" or val.lower() == "null":
        return None
    try:
        n = float(val)
    except ValueError:
        return None
    return round(n, 1) if kind == "percentile" else round(n * 100, 1)


_SKIP_NAME_FRAGS = (
    "fieldnames", "readme", "userguide", "user_guide", "technical",
    "lookup", "regions_", "states_", "usa_",
    "acs2008", "race_ethnicity", "_moe_", "statepctile",
    "donotuse", ".gdb",
)

def _is_skip(name: str) -> bool:
    s = name.lower()
    return any(frag in s for frag in _SKIP_NAME_FRAGS)


def _open_zip_csv(zip_path: Path) -> list[dict]:
    """Pick the largest non-metadata CSV inside a ZIP and parse it."""
    with zipfile.ZipFile(zip_path) as zf:
        candidates = [
            zf.getinfo(n) for n in zf.namelist()
            if n.lower().endswith(".csv") and not _is_skip(n)
        ]
        if not candidates:
            raise RuntimeError(f"no data CSV inside {zip_path}")
        best = max(candidates, key=lambda i: i.file_size)
        print(f"    using {zip_path.name}:{best.filename} "
              f"({best.file_size:,} bytes)")
        with zf.open(best.filename) as f:
            text = io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace")
            return list(csv.DictReader(text))


def read_local_zip(path: Path) -> list[dict]:
    """Read a locally-provided EJScreen dataset. Accepts:
      - a .zip file (as on gaftp/Zenodo)
      - a .csv file
      - a directory (recursively searched; picks largest data CSV,
        descending into nested ZIPs, skipping metadata/readme files,
        DoNotUse variants, and the ACS-companion ZIPs).
    """
    print(f"  reading local {path}")
    if path.is_file():
        if path.suffix.lower() == ".csv":
            with path.open(encoding="utf-8-sig", errors="replace") as f:
                return list(csv.DictReader(f))
        return _open_zip_csv(path)

    # Directory — score every CSV (direct) and every CSV inside every ZIP,
    # take the largest. Nested ZIPs get scanned via zipfile info, no extract.
    best: tuple[int, Path, str | None] | None = None  # (size, container, inner_or_None)
    for p in path.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(path))
        if _is_skip(rel) or "__macosx" in rel.lower():
            continue
        suf = p.suffix.lower()
        if suf == ".csv":
            size = p.stat().st_size
            if size < 100_000:
                continue
            if best is None or size > best[0]:
                best = (size, p, None)
        elif suf == ".zip":
            try:
                with zipfile.ZipFile(p) as zf:
                    for name in zf.namelist():
                        if not name.lower().endswith(".csv") or _is_skip(name):
                            continue
                        info = zf.getinfo(name)
                        if info.file_size < 1_000_000:
                            continue
                        if best is None or info.file_size > best[0]:
                            best = (info.file_size, p, name)
            except zipfile.BadZipFile:
                continue

    if best is None:
        raise RuntimeError(
            f"no plausible data CSV found under {path} "
            f"(searched recursively, skipped metadata files)"
        )
    size, container, inner = best
    if inner is None:
        print(f"    using {container.relative_to(path)} ({size:,} bytes)")
        with container.open(encoding="utf-8-sig", errors="replace") as f:
            return list(csv.DictReader(f))
    print(f"    using {container.relative_to(path)}:{inner} ({size:,} bytes)")
    with zipfile.ZipFile(container) as zf, zf.open(inner) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace")
        return list(csv.DictReader(text))


def _is_de(val) -> bool:
    """Accept either EJScreen v2's 'DE' abbreviation or v1's full
    'Delaware' state name. Case-insensitive, tolerant of surrounding
    quotes and whitespace."""
    s = str(val or "").strip().strip('"').strip("'").upper()
    return s == "DE" or s.startswith("DELAWARE")


def build_year(vintage: int, spec: dict, crosswalk: dict,
               local_path: Path | None = None) -> dict:
    rows = read_local_zip(local_path) if local_path else fetch_zip_csv(spec["url"])
    st_col  = resolve_col(vintage, "ST_ABBREV")
    id_col  = resolve_col(vintage, "ID")
    de_rows = [r for r in rows if _is_de(r.get(st_col))]
    print(f"  {len(de_rows)} Delaware rows")
    if not de_rows and rows:
        # Surface the column we looked at + available columns to make
        # schema-drift diagnosis one paste away.
        sample_keys = list(rows[0].keys())[:12]
        print(f"  no DE matches against column {st_col!r}; "
              f"first cols: {sample_keys}")

    by_geoid: dict[str, dict] = {}
    crosswalk_hits = 0
    for r in de_rows:
        geoid_raw = str(r.get(id_col, "")).strip().strip('"').strip("'").strip()
        if not geoid_raw:
            continue
        geoid = geoid_raw.zfill(12)
        targets = [(geoid, 1.0)]
        if spec["geoid_vintage"] == 2010 and crosswalk:
            mapped = crosswalk.get(geoid)
            if mapped:
                targets = mapped
                crosswalk_hits += 1

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
    if spec["geoid_vintage"] == 2010 and de_rows:
        print(f"  crosswalk matched {crosswalk_hits}/{len(de_rows)} "
              f"2010 GEOIDs -> {len(by_geoid)} 2020 GEOIDs")
    return by_geoid


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--years", default="",
                    help="Comma-sep list, e.g. 2020,2021 (default: all)")
    ap.add_argument("--local", action="append", default=[],
                    metavar="YEAR=PATH",
                    help="Use a locally-downloaded ZIP for YEAR instead of "
                         "fetching (repeatable). Example: "
                         "--local 2015=~/Downloads/ejscreen_2015.zip")
    args = ap.parse_args()

    local_map: dict[int, Path] = {}
    for spec_str in args.local:
        if "=" not in spec_str:
            sys.exit(f"--local value must be YEAR=PATH, got {spec_str!r}")
        yr_s, path_s = spec_str.split("=", 1)
        p = Path(path_s).expanduser()
        if not p.exists():
            sys.exit(f"--local path does not exist: {p}")
        local_map[int(yr_s)] = p

    years = (
        [int(y) for y in args.years.split(",") if y.strip()]
        if args.years else sorted(VINTAGES.keys())
    )
    # If --local was passed without --years, restrict to those years.
    if local_map and not args.years:
        years = sorted(local_map.keys())

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
            result = build_year(y, spec, crosswalk, local_map.get(y))
            if len(result) < MIN_GEOIDS_PER_YEAR:
                print(f"  REJECTED: {len(result)} GEOIDs is below the "
                      f"{MIN_GEOIDS_PER_YEAR} threshold -- not storing. "
                      "Previous data for this year (if any) is preserved.")
                # Keep whatever was there before; do not overwrite with garbage.
            else:
                out[str(y)] = result
                print(f"  -> {len(result)} GEOIDs stored")
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
