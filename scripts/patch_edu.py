#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026 <YOUR NAME>. See LICENSE.md.
"""
patch_edu.py — adds edu_nohsdip_pct to de_blockgroups.geojson
Run from the repo root:  python3 scripts/patch_edu.py
Requires: requests  (pip install requests)
"""
import json, sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip install requests first")

EJSCREEN = (
    "https://services2.arcgis.com/iq8zYa0SRsvIFFKz/arcgis/rest/services/"
    "EJSCREEN_2023_BG_StatePct_with_AS_CNMI_GU_VI_gdb/FeatureServer/0/query"
)
GEOJSON = Path(__file__).parent.parent / "de_blockgroups.geojson"

lookup, offset = {}, 0
while True:
    r = requests.get(EJSCREEN, params={
        "where": "ST_ABBREV='DE'",
        "outFields": "ID,LESSHSPCT",
        "returnGeometry": "false",
        "f": "json",
        "resultOffset": offset,
        "resultRecordCount": 500,
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
    for feat in data.get("features", []):
        a = feat["attributes"]
        geoid = str(a.get("ID", "")).strip()
        val   = a.get("LESSHSPCT")
        if geoid:
            lookup[geoid] = round(float(val), 1) if val is not None else None
    print(f"  fetched {len(lookup)} block groups...")
    if not data.get("exceededTransferLimit"):
        break
    offset += 500

print(f"Total fetched: {len(lookup)}")

with open(GEOJSON) as f:
    gj = json.load(f)

matched = 0
for feat in gj["features"]:
    geoid = feat["properties"].get("GEOID", "")
    if geoid in lookup:
        feat["properties"]["edu_nohsdip_pct"] = lookup[geoid]
        matched += 1

print(f"Matched {matched}/{len(gj['features'])} block groups")

with open(GEOJSON, "w") as f:
    json.dump(gj, f, separators=(",", ":"))

print("Done — commit de_blockgroups.geojson and push")
