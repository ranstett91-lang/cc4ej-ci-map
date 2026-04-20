#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026 <YOUR NAME>. See LICENSE.md.
"""Patch `founded` (year of first industrial/polluting use at the site) onto
every feature in facilities.json. Keys by the `name` property so the script is
re-runnable and idempotent.

Year sourcing:
  High confidence — corroborated by corporate history or widely cited:
    Sun Oil Marcus Hook 1902; DuPont Chambers Works 1891; DuPont Edge Moor
    TiO2 1935; DuPont Seaford Nylon 1939; Delaware City Refinery 1957;
    I-95 through DE 1963; Worth/Phoenix Steel 1917; Paulsboro Refinery 1917;
    Dover AFB 1941; Chester Incinerator 1991; Hay Road 1989.
  Medium confidence — founded date of corporate lineage / site:
    Honeywell/Allied AWE 1917; Trainer Refinery 1926; Edge Moor Power 1954;
    Indian River Power 1957; Atlas Point (Atlas Powder) 1938.
  Estimate (~decade):
    Kuehne, Metachem, Oxy, Nexpera, Clean Earth, Oceanport, Messer,
    Mountaire, Perdue plants, Corrosion Control — mid-to-late 20th century.

For warehouses + redevelopments built on legacy industrial land, `founded`
uses the year of the underlying polluting activity (so scrubbing back
through the 20th century retires the *burden*, not just the current tenant).
Example: Pepsi / Agile / First State Crossing all sit on the Worth Steel
(1917) footprint.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FACILITIES_PATH = ROOT / "facilities.json"

# name (exact match) -> founded year
FOUNDED = {
    # --- Claymont / Marcus Hook / NCC industrial corridor ---
    "Solstice Advanced Materials (formerly Honeywell / Allied Chemical) — AWE Superfund Site": 1917,
    "Honeywell Delaware Plant": 1917,
    "Evraz Claymont Steel — Former Steel Mill (closed 2015)": 1917,
    "Pepsi Distribution Center — Former Steel Mill Site": 1917,
    "Agile Cold Storage — Former Steel Mill Site": 1917,
    "Former Tri-State Mall — Vacant": 1965,
    "First State Crossing — Commercial/Industrial Development (NCC Monitoring)": 1917,
    "Citisteel / Phoenix Steel Contamination Site (DE-0046)": 1917,
    "INEOS (formerly General Chemical) — Delaware Valley Works": 1917,
    "Messer LLC — Claymont Facility": 1945,
    "Oceanport Industries": 1975,
    "I-95 / I-495 / Route 13 — Claymont Diesel Corridor": 1963,

    # --- Marcus Hook / Trainer refineries + chemicals ---
    "Monroe Energy LLC — Trainer Refinery": 1926,
    "Energy Transfer Marcus Hook Complex": 1902,
    "Braskem America — Marcus Hook": 1929,
    "Valtris Specialty Chemicals — Delaware River Plant": 1940,
    "ReWorld (formerly Covanta) Chester Incinerator": 1991,
    "Evonik Corp — Marcus Hook": 1955,
    "Mexichem Specialty Resins (Vestolit) — Marcus Hook": 1957,

    # --- NJ side of Delaware River ---
    "Lubrizol Corp — Pedricktown Plant": 1967,
    "Chemours Chambers Works — Deepwater, NJ": 1891,
    "Paulsboro Refining Company — Paulsboro, NJ": 1917,
    "LANXESS Corp — Logan Township, NJ": 1960,
    "Infineum USA — Paulsboro, NJ": 1917,
    "OxyVinyls LP — Pedricktown Plant": 1965,
    "Mexichem Specialty Resins / Vestolit (Orbia) — Pedricktown Plant": 1965,
    "Depot Connect International (Quala) — Pedricktown Tank Wash": 1985,
    "Corrosion Control Corporation — Pedricktown": 1975,
    "Logan Generating Plant — Former Coal Power Plant / Brownfield": 1994,

    # --- Edge Moor / Wilmington waterfront ---
    "Chemours Edge Moor (formerly DuPont) — TiO2 / PFAS": 1935,
    "DSWA Cherry Island Landfill": 1984,
    "Calpine Edge Moor Power Plant": 1954,
    "Calpine Hay Road Power Plant": 1989,
    "Wilmington Wastewater Treatment Plant": 1954,

    # --- New Castle / Delaware City ---
    "Clean Earth of New Castle": 1975,
    "Buckeye Terminals — New Castle": 1955,
    "Croda Inc. (Atlas Point)": 1938,
    "Metachem Products — New Castle (chlorinated solvents site)": 1966,
    "Kuehne Chemical Company — New Castle (chlorine)": 1968,
    "Occidental Chemical Corp. — New Castle": 1966,
    "Delaware City Refinery": 1957,
    "Air Liquide Industrial — Delaware City": 1957,
    "Nexpera LLC — Red Lion Plant": 1966,
    "I-95 / Route 141 Interchange — NCC Industrial Corridor": 1963,

    # --- Downstate DE ---
    "Dover Air Force Base": 1941,
    "Perdue Farms — Milford Processing Plant": 1976,
    "Allen Harim Foods — Millsboro": 1968,
    "Indian River Power — Millsboro": 1957,
    "Perdue Foods — Georgetown Processing Plant": 1985,
    "Mountaire Farms — Millsboro Processing Plant": 1972,
    "Mountaire Farms — Selbyville Processing Plant": 1958,
    "Allen Harim — Harbeson Processing Plant": 2011,

    # --- Historical / legacy contamination ---
    "DuPont / Chemours Seaford Works — Former Nylon Plant": 1939,
    "Dover Gas Light — Manufactured Gas Plant (MGP) Contamination Site": 1859,
}


def main() -> int:
    data = json.loads(FACILITIES_PATH.read_text())
    feats = data["features"]

    missing = []
    patched = 0
    for feat in feats:
        name = feat["properties"].get("name", "")
        yr = FOUNDED.get(name)
        if yr is None:
            missing.append(name)
            continue
        feat["properties"]["founded"] = yr
        patched += 1

    if missing:
        print("ERROR — these facilities have no founded year assigned:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        print(f"\nAdd them to FOUNDED in {__file__} and rerun.", file=sys.stderr)
        return 1

    stray = set(FOUNDED) - {f["properties"].get("name", "") for f in feats}
    if stray:
        print("WARNING — FOUNDED has entries with no matching feature:", file=sys.stderr)
        for s in sorted(stray):
            print(f"  - {s}", file=sys.stderr)

    FACILITIES_PATH.write_text(json.dumps(data, separators=(",", ":")))
    print(f"Patched {patched}/{len(feats)} features with `founded`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
