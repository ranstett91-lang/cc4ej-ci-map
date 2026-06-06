#!/usr/bin/env python3
"""One-off: append all NJ Delaware-River-corridor TRI facilities (Salem +
Gloucester counties) to facilities.json, deriving each feature's fields from
the repo's own EPA TRI roster (tri_facilities.json). Idempotent: skips any TRI
facility already present on the map (matched by TRIFID)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAC = ROOT / "facilities.json"
TRI = ROOT / "tri_facilities.json"

COUNTY_FIPS = {"SALEM": "34033", "GLOUCESTER": "34015"}

# NAICS prefix/code -> (human-readable type label, impact category).
# impact must be one of: air, chemical, refinery, contamination, traffic, ag
NAICS = {
    "221112": ("Fossil-fuel / cogeneration power plant", "air"),
    "221113": ("Nuclear power generating station", "air"),
    "311351": ("Cocoa & chocolate manufacturing", "air"),
    "311812": ("Commercial bakery", "air"),
    "321999": ("Wood product manufacturing", "chemical"),
    "322211": ("Corrugated & paperboard box manufacturing", "chemical"),
    "323111": ("Commercial printing", "chemical"),
    "324110": ("Petroleum refinery", "refinery"),
    "324191": ("Petroleum lubricating oil & grease manufacturing", "refinery"),
    "325110": ("Petrochemical manufacturing", "chemical"),
    "325120": ("Industrial gas manufacturing", "chemical"),
    "325188": ("Inorganic chemical manufacturing", "chemical"),
    "325199": ("Organic chemical manufacturing", "chemical"),
    "325211": ("Plastics & resin manufacturing", "chemical"),
    "325411": ("Pharmaceutical / medicinal chemical manufacturing", "chemical"),
    "325412": ("Pharmaceutical preparation manufacturing", "chemical"),
    "325413": ("Biological / diagnostic products manufacturing", "chemical"),
    "325510": ("Paint & coating manufacturing", "chemical"),
    "325520": ("Adhesive manufacturing", "chemical"),
    "325910": ("Printing ink manufacturing", "chemical"),
    "325991": ("Custom compounding of purchased resins", "chemical"),
    "325998": ("Specialty chemical manufacturing", "chemical"),
    "326113": ("Plastics film & sheet manufacturing", "chemical"),
    "326122": ("Plastics pipe & fittings manufacturing", "chemical"),
    "326199": ("Plastics product manufacturing", "chemical"),
    "327213": ("Glass container manufacturing", "air"),
    "327320": ("Ready-mix concrete manufacturing", "air"),
    "327331": ("Concrete block & brick manufacturing", "air"),
    "327390": ("Concrete product manufacturing", "air"),
    "327910": ("Abrasive product manufacturing", "chemical"),
    "327992": ("Ground & treated mineral manufacturing", "chemical"),
    "327999": ("Nonmetallic mineral product manufacturing", "air"),
    "331112": ("Ferroalloy & electrometallurgical manufacturing", "chemical"),
    "331315": ("Aluminum sheet & plate manufacturing", "chemical"),
    "331492": ("Secondary smelting / refining of nonferrous metals", "chemical"),
    "332111": ("Iron & steel forging", "chemical"),
    "332115": ("Metal stamping & closures manufacturing", "chemical"),
    "332313": ("Plate work / fabricated metal manufacturing", "chemical"),
    "332431": ("Metal can manufacturing", "chemical"),
    "332813": ("Electroplating, plating & metal coating", "chemical"),
    "333613": ("Mechanical power transmission equipment manufacturing", "chemical"),
    "334220": ("Communications equipment manufacturing", "chemical"),
    "334418": ("Printed circuit assembly manufacturing", "chemical"),
    "334612": ("Prerecorded media manufacturing", "chemical"),
    "335314": ("Relay & industrial control manufacturing", "chemical"),
    "335931": ("Wiring device manufacturing", "chemical"),
    "336999": ("Transportation equipment manufacturing", "chemical"),
    "424710": ("Petroleum bulk storage & terminal", "refinery"),
    "493190": ("Bulk storage / tank farm", "refinery"),
    "511120": ("Periodical publishing", "chemical"),
    "561720": ("Industrial cleaning services", "contamination"),
    "562211": ("Hazardous waste treatment & disposal", "contamination"),
}

# Name-based impact overrides for sites whose hazard isn't captured by NAICS.
NAME_IMPACT = [
    ("SHIELDALLOY", "contamination"),  # radioactive ferroalloy Superfund site
]

# Casing fixups applied after Title Case (Title Case mangles these).
FIXUPS = {
    "Exxonmobil": "ExxonMobil", "Exxon": "Exxon", "Dupont": "DuPont",
    "Saint-Gobain": "Saint-Gobain", "Ppl": "PPL", "Coim": "COIM",
    "Ggb": "GGB", "Cpi": "CPI", "Spmt": "SPMT", "Adm": "ADM",
    "Itw": "ITW", "Ge": "GE", "3M": "3M", "Lanxess": "LANXESS",
    "Alr": "ALR", "Psi": "PSI", "Dba": "DBA", "Dadc": "DADC",
    "Basf": "BASF", "Geo": "GEO", "Cc": "CC", "K-Tron": "K-Tron",
    "Mapei": "MAPEI", "Apg": "APG", "Llc": "LLC", "L.p.": "L.P.",
    "Lp": "LP", "Inc": "Inc", "Co": "Co", "Corp": "Corp", "Usa": "USA",
    "Ltl": "LTL",
}

ACRONYM_KEEP = {"LLC", "LP", "INC", "CO", "CORP", "USA", "GE", "3M",
                "ITW", "ADM", "GGB", "CPI", "SPMT", "PPL", "ALR", "PSI",
                "DBA", "US", "L.P.", "LTL", "MFG", "DIV", "CTR"}


def clean_name(raw):
    s = re.sub(r"\s+", " ", raw).strip()
    s = s.replace("GENERATIN G", "GENERATING")
    s = s.replace("MANUFACTURNG", "MANUFACTURING")
    out = []
    for tok in s.split(" "):
        if tok in ACRONYM_KEEP:
            out.append(tok)
        elif re.match(r"^#?\d", tok):       # plant numbers, 3M, etc.
            out.append(tok)
        else:
            out.append(tok.title())
    s = " ".join(out)
    for a, b in FIXUPS.items():
        s = re.sub(r"\b" + re.escape(a) + r"\b", b, s)
    return s


def weight_for(lbs):
    lbs = lbs or 0
    if lbs >= 10_000_000:
        return 3.0
    if lbs >= 1_000_000:
        return 2.5
    if lbs >= 100_000:
        return 2.0
    if lbs >= 1_000:
        return 1.5
    return 1.0


def impact_for(naics, name):
    up = name.upper()
    for key, imp in NAME_IMPACT:
        if key in up:
            return imp
    return NAICS.get(naics, ("Industrial / TRI-reporting facility", "chemical"))[1]


def type_for(naics):
    return NAICS.get(naics, ("Industrial / TRI-reporting facility", "chemical"))[0]


def build_note(v, naics_label):
    city = v["city"].title()
    total = v.get("total_lbs") or 0
    fy, ly = v.get("first_year"), v.get("last_year")
    parts = []
    parts.append(
        f"EPA Toxics Release Inventory (TRI) reporting facility in {city}, NJ "
        f"(NAICS {v['naics']} — {naics_label.lower()})."
    )
    yr = ""
    if fy and ly:
        yr = f" between {fy} and {ly}" if fy != ly else f" in {fy}"
    parts.append(
        f"Reported approximately {total:,.0f} lbs of total toxic chemical "
        f"releases to EPA TRI{yr}."
    )
    tops = v.get("top_chemicals") or []
    if tops:
        chem = ", ".join(
            f"{c['name']} ({c['lbs']:,.0f} lbs)" for c in tops[:3]
        )
        parts.append(f"Largest reported releases: {chem}.")
    parts.append(
        "Sits on the New Jersey bank of the Delaware River; its releases enter "
        "the shared Delaware River airshed and watershed that New Castle "
        "County, DE communities depend on, adding to the cumulative pollution "
        "burden borne across the river."
    )
    parent = (v.get("parent") or "").strip()
    if parent and parent.upper() not in v["name"].upper():
        parts.append(f"Parent company on record: {clean_name(parent)}.")
    if ly and ly >= 2022:
        parts.append(f"Active TRI reporter (most recent submission {ly}).")
    elif ly:
        parts.append(
            f"Most recent TRI submission on record: {ly} — no later "
            f"filings, indicating reduced operations or below-threshold releases."
        )
    return " ".join(parts)


def main():
    fac = json.loads(FAC.read_text())
    tri = json.loads(TRI.read_text())["facilities"]

    existing_trifids = {
        f["properties"].get("trifid")
        for f in fac["features"]
        if f["properties"].get("trifid")
    }
    # Existing map entries already covering these TRI sites but lacking a trifid:
    existing_trifids |= {"08067XYVNYRTE13", "08014PGCRPRTE13"}  # OxyVinyls, Logan Generating

    candidates = [
        (k, v) for k, v in tri.items()
        if v["state"] == "NJ" and v["county"] in COUNTY_FIPS
        and k not in existing_trifids
    ]
    # Stable, meaningful order: heaviest reporters first.
    candidates.sort(key=lambda kv: -(kv[1].get("total_lbs") or 0))

    added = 0
    for trifid, v in candidates:
        naics_label = type_for(v["naics"])
        feat = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(v["lon"], 4), round(v["lat"], 4)],
            },
            "properties": {
                "name": f"{clean_name(v['name'])} — {v['city'].title()}, NJ",
                "type": f"{naics_label} (NJ)",
                "weight": weight_for(v.get("total_lbs")),
                "fips": COUNTY_FIPS[v["county"]],
                "state": "NJ",
                "source": "EPA TRI (Toxics Release Inventory)",
                "impact": impact_for(v["naics"], v["name"]),
                "category": "facility",
                "trifid": trifid,
                "de_implication": build_note(v, naics_label),
            },
        }
        fac["features"].append(feat)
        added += 1

    FAC.write_text(json.dumps(fac, indent=1, ensure_ascii=True) + "\n")
    print(f"Added {added} NJ river-corridor facilities. "
          f"Total features now {len(fac['features'])}.")


if __name__ == "__main__":
    main()
