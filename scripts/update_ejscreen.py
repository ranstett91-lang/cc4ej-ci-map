#!/usr/bin/env python3
"""
update_ejscreen.py — refresh all EJScreen indicators in de_blockgroups.geojson

Supersedes scripts/patch_edu.py (which only updated a single field).
Fetches all environmental burden (EB) and social vulnerability (SV) fields
from the EPA EJScreen ArcGIS FeatureServer for Delaware block groups and
patches them into the local GeoJSON.

Usage:
    python3 scripts/update_ejscreen.py              # refresh all fields
    python3 scripts/update_ejscreen.py --dry-run    # preview changes, no write
    python3 scripts/update_ejscreen.py --fields edu # only the education field
    python3 scripts/update_ejscreen.py --fields sv  # all SV fields

Field groups:
    all   — all 15 EB + SV fields (default)
    eb    — environmental burden percentiles only
    sv    — social vulnerability rates only
    edu   — LESSHSPCT only (backward-compat with patch_edu.py)

Requires: requests  (pip install requests)
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip install requests first")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EJSCREEN_URL = (
    "https://services2.arcgis.com/iq8zYa0SRsvIFFKz/arcgis/rest/services/"
    "EJSCREEN_2023_BG_StatePct_with_AS_CNMI_GU_VI_gdb/FeatureServer/0/query"
)

GEOJSON = Path(__file__).parent.parent / "de_blockgroups.geojson"

# EJScreen field → (GeoJSON property name, value kind)
# kind "percentile": stored as-is (0–100, state rank)
# kind "rate":       EJScreen returns 0–1; we store ×100 as a percent
FIELD_MAP: dict[str, tuple[str, str]] = {
    # Environmental burden — state percentiles (higher = worse off)
    "P_PM25":       ("p_pm25",          "percentile"),
    "P_OZONE":      ("p_ozone",         "percentile"),
    "P_DSLPM":      ("p_dslpm",         "percentile"),
    "P_CANCER":     ("p_cancer",        "percentile"),
    "P_RESP":       ("p_resp",          "percentile"),
    "P_PTRAF":      ("p_ptraf",         "percentile"),
    "P_PNPL":       ("p_pnpl",          "percentile"),
    "P_PTSDF":      ("p_ptsdf",         "percentile"),
    "P_PRMP":       ("p_prmp",          "percentile"),
    "P_PWDIS":      ("p_pwdis",         "percentile"),
    # Social vulnerability — raw rates (0–1 → stored as %)
    "LOWINCPCT":    ("lowinc_pct",      "rate"),
    "UNEMPPCT":     ("unemp_pct",       "rate"),
    "LINGISOPCT":   ("lingiso_pct",     "rate"),
    "LESSHSPCT":    ("edu_nohsdip_pct", "rate"),
    # Life expectancy — state percentile (lower = worse off)
    "P_LIFEEXPPCT": ("p_lifeexppct",    "percentile"),
}

FIELD_GROUPS: dict[str, list[str]] = {
    "all": list(FIELD_MAP.keys()),
    "eb":  [
        "P_PM25", "P_OZONE", "P_DSLPM", "P_CANCER", "P_RESP",
        "P_PTRAF", "P_PNPL", "P_PTSDF", "P_PRMP", "P_PWDIS",
    ],
    "sv":  ["LOWINCPCT", "UNEMPPCT", "LINGISOPCT", "LESSHSPCT", "P_LIFEEXPPCT"],
    "edu": ["LESSHSPCT"],
}


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_ejscreen(fields: list[str], state: str = "DE") -> dict[str, dict]:
    """
    Fetch EJScreen records for all block groups in *state*.

    Returns a dict keyed by 12-char GEOID, values are {ejfield: float|None}.
    Handles pagination automatically (EJScreen caps at 500 records per request).
    """
    lookup: dict[str, dict] = {}
    offset = 0
    batch = 500
    out_fields = ",".join(["ID"] + fields)

    while True:
        resp = requests.get(EJSCREEN_URL, params={
            "where":             f"ST_ABBREV='{state}'",
            "outFields":         out_fields,
            "returnGeometry":    "false",
            "f":                 "json",
            "resultOffset":      offset,
            "resultRecordCount": batch,
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            break

        for feat in features:
            attrs = feat["attributes"]
            geoid = str(attrs.get("ID", "")).strip()
            if not geoid:
                continue
            record: dict = {}
            for field in fields:
                val = attrs.get(field)
                record[field] = float(val) if val is not None else None
            lookup[geoid] = record

        print(f"  fetched {len(lookup)} records (offset={offset})...")

        if not data.get("exceededTransferLimit"):
            break
        offset += batch

    return lookup


# ---------------------------------------------------------------------------
# Patching
# ---------------------------------------------------------------------------

def _coerce(raw: float | None, kind: str) -> float | None:
    """Convert a raw EJScreen value to the stored representation."""
    if raw is None:
        return None
    return round(raw * 100, 1) if kind == "rate" else round(raw, 1)


def apply_to_geojson(
    gj: dict,
    lookup: dict[str, dict],
    fields: list[str],
    dry_run: bool,
) -> dict:
    """
    Patch block group features with EJScreen values.

    Returns a stats dict with counts of matched/updated/unchanged/nulled features.
    When *dry_run* is True the GeoJSON object is not modified.
    """
    stats = {"matched": 0, "unmatched": 0, "updated": 0, "unchanged": 0, "nulled": 0}

    for feat in gj["features"]:
        props = feat["properties"]
        geoid = str(props.get("GEOID", "")).strip()

        if geoid not in lookup:
            stats["unmatched"] += 1
            continue

        stats["matched"] += 1
        record = lookup[geoid]

        for ejfield in fields:
            gj_key, kind = FIELD_MAP[ejfield]
            new_val = _coerce(record.get(ejfield), kind)
            old_val = props.get(gj_key)

            if new_val != old_val:
                if not dry_run:
                    props[gj_key] = new_val
                stats["nulled" if new_val is None else "updated"] += 1
            else:
                stats["unchanged"] += 1

    return stats


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh EJScreen indicators in de_blockgroups.geojson",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would change without writing to disk",
    )
    parser.add_argument(
        "--fields", choices=list(FIELD_GROUPS.keys()), default="all",
        help="Field group to refresh (default: all)",
    )
    args = parser.parse_args()

    fields = FIELD_GROUPS[args.fields]
    label = "DRY RUN — " if args.dry_run else ""
    print(f"{label}Fetching EJScreen 2023 for Delaware")
    print(f"  Field group '{args.fields}': {len(fields)} field(s)")

    lookup = fetch_ejscreen(fields)
    print(f"Total: {len(lookup)} block groups from EJScreen\n")

    with open(GEOJSON) as f:
        gj = json.load(f)

    stats = apply_to_geojson(gj, lookup, fields, dry_run=args.dry_run)

    print("Results:")
    print(f"  Matched BGs:     {stats['matched']:>5}")
    print(f"  Unmatched BGs:   {stats['unmatched']:>5}")
    print(f"  Fields updated:  {stats['updated']:>5}")
    print(f"  Fields nulled:   {stats['nulled']:>5}")
    print(f"  Fields same:     {stats['unchanged']:>5}")

    if args.dry_run:
        print("\nDRY RUN — no file written. Remove --dry-run to apply changes.")
        return

    with open(GEOJSON, "w") as f:
        json.dump(gj, f, separators=(",", ":"))

    print(f"\nWrote {GEOJSON.name}")
    print("Next:")
    print("  git add de_blockgroups.geojson")
    print("  git commit -m 'Refresh EJScreen 2023 data'")
    print("  git push origin main")


if __name__ == "__main__":
    main()
