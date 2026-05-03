"""
_census_common.py -- shared helpers for building pre-EJScreen block-group
demographic history entries from US Census sources.

The goal is a single normalized record shape that de_blockgroups_history.json
accepts alongside existing EJScreen-sourced years. Pre-EJScreen vintages carry
ONLY demographic fields (lowinc_pct, unemp_pct, lingiso_pct, edu_nohsdip_pct,
poc_pct); every EJScreen-only field (p_* percentiles and the derived eb score)
is written as explicit null so the map's applyYearToBG overlay doesn't let the
2024 baseline air values bleed through to the painted BG features.

Separately, load/save and crosswalk helpers are factored out of
fetch_ejscreen_history.py so the new ACS/Decennial build scripts reuse the
same logic rather than duplicating it.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
HIST_FILE = ROOT / "de_blockgroups_history.json"

# Explicit null for every EJScreen-only field on pre-EJScreen records so the
# overlay doesn't leak the 2024 baseline air values through. Must match the
# field names produced by scripts/fetch_ejscreen_history.py (PROP_MAP).
EJSCREEN_ONLY_FIELDS = (
    "p_pm25", "p_ozone", "p_dslpm", "p_cancer", "p_resp",
    "p_ptraf", "p_pnpl", "p_ptsdf", "p_prmp", "p_pwdis",
    "under5_pct", "over64_pct",  # age fields only populated by EJScreen
    "eb",
)

# Canonical demographic field names rendered by the info panel. Any new build
# script must populate some subset of these (null allowed for vintages where
# a field is not comparably collected, e.g. lingiso_pct pre-1990).
DEMO_FIELDS = (
    "lowinc_pct",
    "unemp_pct",
    "lingiso_pct",
    "edu_nohsdip_pct",
    "poc_pct",
)


def load_history() -> dict:
    """Load de_blockgroups_history.json as a dict; returns {} if absent."""
    if not HIST_FILE.exists():
        return {}
    return json.loads(HIST_FILE.read_text())


def save_history(hist: dict) -> None:
    """Write with compact formatting to keep file size reasonable but still
    round-trippable (keys are year-strings preserved as-is)."""
    HIST_FILE.write_text(
        json.dumps(hist, separators=(",", ":"), sort_keys=False) + "\n"
    )


def build_demo_record(demo: dict) -> dict:
    """Return a per-geoid record dict with demographic fields from `demo`
    plus explicit null for every EJScreen-only field. `demo` keys should be
    a subset of DEMO_FIELDS; missing keys are written as null."""
    out: dict = {f: None for f in EJSCREEN_ONLY_FIELDS}
    for f in DEMO_FIELDS:
        out[f] = demo.get(f)
    # sv is an EJScreen-derived composite partly dependent on lowinc/poc but
    # also on CDC PLACES health-outcome side-cars (unavailable pre-2020), so
    # we null it rather than recomposing. The map's SV/CB fills already have
    # null guards — see ebFillExpr/svFillExpr at index.html:5788-5842.
    out["sv"] = None
    out["sv_health"] = None
    return out


def load_crosswalk(csv_path: Path) -> dict[str, list[tuple[str, float]]]:
    """Load a {source_geoid: [(target_geoid20, weight), ...]} crosswalk CSV.
    Accepts any two GEOID column names; weights default to 1.0 if absent or
    unparseable. Returns empty dict if the file is missing (caller decides
    how to handle that — typically: skip affected vintages)."""
    if not csv_path.exists():
        return {}
    out: dict[str, list[tuple[str, float]]] = {}
    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}
    # Identify source + target columns heuristically so one helper handles
    # bg10→bg20, bg00→bg20, tract70→bg20, etc.
    cols = rows[0].keys()
    src_col = next((c for c in cols if c.upper() in
                    ("GEOID10", "GEOID00", "GEOID90", "TRACT10",
                     "TRACT00", "TRACT90", "TRACT80", "TRACT70", "SOURCE")), None)
    dst_col = next((c for c in cols if c.upper() in
                    ("GEOID20", "BG20", "TARGET")), None)
    if not src_col or not dst_col:
        raise ValueError(f"cannot infer source/target columns in {csv_path}: {list(cols)}")
    for row in rows:
        src = (row.get(src_col) or "").strip()
        dst = (row.get(dst_col) or "").strip()
        if not src or not dst:
            continue
        try:
            w = float(row.get("WEIGHT", 1.0))
        except ValueError:
            w = 1.0
        out.setdefault(src, []).append((dst, w))
    return out


def apply_crosswalk(by_src: dict[str, dict], crosswalk: dict[str, list[tuple[str, float]]]) -> dict[str, dict]:
    """Allocate source-geoid records to bg20 targets using per-target weights.

    For rate-style fields (already expressed as percentages), the result is a
    population-weighted average across all source geoids that overlap a target
    bg20. Callers that want weights to reflect 2020 population under each
    source should ensure the crosswalk CSV's WEIGHT column is that population
    share (0..1). For raw counts, multiply weights through before allocation.

    Unknown source geoids are silently dropped (caller should spot-check via
    scripts/audit_history.py which reports coverage against the 2020 baseline).
    """
    # Accumulate {dst: {field: (sum, weight_sum)}}
    agg: dict[str, dict[str, list[float]]] = {}
    for src, rec in by_src.items():
        for dst, w in crosswalk.get(src, []):
            dst_rec = agg.setdefault(dst, {})
            for f, v in rec.items():
                if v is None:
                    continue
                slot = dst_rec.setdefault(f, [0.0, 0.0])
                slot[0] += float(v) * w
                slot[1] += w
    out: dict[str, dict] = {}
    for dst, fields in agg.items():
        rec: dict = {}
        for f, (s, wsum) in fields.items():
            rec[f] = round(s / wsum, 1) if wsum > 0 else None
        out[dst] = rec
    # Null-stub every field the consumer might read, so the UI's
    # Object.assign(base, yr) overlay can't leak 2024 baseline values for
    # any field that happens to be all-None across src records. Covers both
    # EJScreen-only fields (never populated pre-2016) AND demographic
    # fields that may be suppressed by ACS in some vintages (e.g. lingiso_pct
    # for tiny tracts, or pre-1990 decennials where the concept isn't
    # collected). Without DEMO_FIELDS in this loop, a src with lingiso_pct=None
    # across all bg10s would produce dst records missing the key, and the
    # frontend overlay would fall back to the 2024 baseline value.
    for dst in out:
        for f in EJSCREEN_ONLY_FIELDS:
            out[dst].setdefault(f, None)
        for f in DEMO_FIELDS:
            out[dst].setdefault(f, None)
        out[dst].setdefault("sv", None)
        out[dst].setdefault("sv_health", None)
    return out


def merge_year(hist: dict, year: int, records: dict[str, dict]) -> dict:
    """Upsert `year` into `hist` in-place; returns the same dict.

    Overwrites any existing records for that year. Callers SHOULD print a
    diff/summary before calling save_history (see build_acs5_history.py)."""
    hist[str(year)] = records
    return hist


def _census_clean(val) -> float | None:
    """Coerce a Census API cell to a float, filtering the suppression
    sentinel codes. ACS uses negative sentinels for suppressed/imputed
    cells (see Census ACS documentation, 'jam values'):
      -999999999  insufficient sample
      -888888888  no sample observations
      -666666666  ratio involves zero estimate (denom was 0)
      -555555555  median falls in upper interval (not usable as count)
      -333333333  value not imputed (rare, DHC)
      -222222222  value not computed (small geography)
    Any negative value is treated as a sentinel; real counts are non-negative.
    None, empty string, and the literal 'null' also map to None."""
    if val is None:
        return None
    if isinstance(val, str):
        s = val.strip()
        if s == "" or s.lower() == "null":
            return None
    try:
        n = float(val)
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    return n


def safe_pct(num, denom, digits: int = 1) -> float | None:
    """Return 100 * num/denom rounded to `digits`. None if denom is zero,
    either operand is missing/suppressed, or either is a Census sentinel."""
    n = _census_clean(num)
    d = _census_clean(denom)
    if n is None or d is None or d <= 0:
        return None
    return round(100.0 * n / d, digits)


__all__ = [
    "HIST_FILE",
    "EJSCREEN_ONLY_FIELDS",
    "DEMO_FIELDS",
    "load_history",
    "save_history",
    "build_demo_record",
    "load_crosswalk",
    "apply_crosswalk",
    "merge_year",
    "safe_pct",
]
