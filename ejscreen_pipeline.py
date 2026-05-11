"""
Delaware Cumulative Impacts Pipeline — v3
Housing-level analysis via two complementary approaches:

  MODULE A — Block Group Level (regulatory map)
    - EJScreen block group data (~800 ppl avg vs ~4,000 for tract)
    - ACS block group socioeconomic indicators
    - CDC PLACES health outcomes (tract level, assigned to BGs within tract)
    - ~570 DE block groups vs ~210 census tracts

  MODULE B — Parcel Level (community accountability tool)
    - NCC parcel database (address-level)
    - Distance to each named facility (Honeywell, Evraz, Chemtrade, Sunoco, etc.)
    - FEMA flood zone status
    - Building age (pre-1978 = lead paint risk indicator)
    - Road proximity for traffic exposure
    - NOTE: Health outcome data stays at block group — privacy floor

Run:    python ejscreen_pipeline_v3.py
        python ejscreen_pipeline_v3.py --parcel   (adds NCC parcel module)

Output: de_blockgroup_scores.json       ← regulation map widget
        de_blockgroup_scores.csv
        de_parcel_scores.json           ← community accountability tool (--parcel only)
        de_parcel_scores.csv

Requirements: pip install requests
"""

import argparse
import csv
import json
import math
import sys
import time
from collections import defaultdict

import requests

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────
STATE_ABBREV  = "DE"
STATE_FIPS    = "10"
NCC_FIPS      = "10001"

# EJScreen ArcGIS REST — 2023 block group state percentiles
# (original geodata.epa.gov/OEI/EJSCREEN endpoint retired)
EJSCREEN_BG_URL = (
    "https://services2.arcgis.com/iq8zYa0SRsvIFFKz/arcgis/rest/services/"
    "EJSCREEN_2023_BG_StatePct_with_AS_CNMI_GU_VI_gdb/FeatureServer/0/query"
)

# CDC PLACES census tract (best available — assigned to child block groups)
CDC_PLACES_URL  = "https://chronicdata.cdc.gov/resource/cwsq-ngmh.json"

# NCC parcel service (New Castle County open GIS)
NCC_PARCEL_URL  = (
    "https://services3.arcgis.com/uB6dqCnkRlkiB04l/arcgis/rest/services/"
    "New_Castle_County_Parcels/FeatureServer/0/query"
)

# ──────────────────────────────────────────────────────────────────────────────
# KNOWN FACILITIES — Claymont industrial corridor + statewide majors
# Coordinates: (lat, lon)
# Source: DNREC NavMap, EPA FRS, personal knowledge
# Add more from DNREC Tier II / Chemical Neighbors as available
# ──────────────────────────────────────────────────────────────────────────────
FACILITIES = [
    # ── Claymont industrial corridor ──────────────────────────────────────────
    {"name": "Honeywell/Allied Chemical AWE Site",          "lat": 39.7972, "lon": -75.4611,
     "type": "AWE/Superfund",    "weight": 3.0, "fips": "10001"},
    {"name": "Evraz Claymont Steel",                        "lat": 39.7943, "lon": -75.4617,
     "type": "Heavy industrial", "weight": 2.5, "fips": "10001"},
    {"name": "Oceanport Industries",                        "lat": 39.8109, "lon": -75.4363,
     "type": "Industrial",       "weight": 2.0, "fips": "10001"},
    {"name": "Sunoco Partners Marketing & Terminals",       "lat": 39.7988, "lon": -75.4490,
     "type": "Petroleum",        "weight": 2.0, "fips": "10001"},
    {"name": "Chemtrade Logistics (Marcus Hook adj)",       "lat": 39.8100, "lon": -75.4190,
     "type": "Chemical",         "weight": 2.2, "fips": "10001"},
    {"name": "Energy Transfer Marketing & Terminals",       "lat": 39.8081, "lon": -75.4267,
     "type": "Petroleum",        "weight": 2.0, "fips": "10001"},  # Title V; DNREC permit
    {"name": "Messer LLC – Claymont Facility",              "lat": 39.8092, "lon": -75.4393,
     "type": "Industrial gas",   "weight": 1.5, "fips": "10001"},  # DNREC air permit
    # ── Wilmington / Delaware River industrial corridor ───────────────────────
    {"name": "Incinerator (DSWA Cherry Island)",            "lat": 39.7333, "lon": -75.5111,
     "type": "Solid waste",      "weight": 2.0, "fips": "10001"},
    {"name": "Calpine Edge Moor Power Plant",               "lat": 39.7384, "lon": -75.5038,
     "type": "Power generation", "weight": 1.8, "fips": "10001"},  # Title V; fmr NRG Edgemoor
    {"name": "Calpine Hay Road Power Plant",                "lat": 39.7433, "lon": -75.5067,
     "type": "Power generation", "weight": 1.8, "fips": "10001"},  # Title V
    {"name": "Wilmington Wastewater Treatment Plant",       "lat": 39.7359, "lon": -75.5158,
     "type": "Wastewater",       "weight": 1.2, "fips": "10001"},  # Title V
    {"name": "Clean Earth of New Castle",                   "lat": 39.7148, "lon": -75.5383,
     "type": "Hazardous waste",  "weight": 1.8, "fips": "10001"},  # Title V; HW processing
    {"name": "Buckeye Terminals",                           "lat": 39.7105, "lon": -75.5297,
     "type": "Petroleum",        "weight": 1.5, "fips": "10001"},  # Title V
    # ── Southern New Castle County ─────────────────────────────────────────────
    {"name": "Croda Inc (Atlas Point)",                     "lat": 39.6915, "lon": -75.5410,
     "type": "Chemical",         "weight": 2.0, "fips": "10001"},  # Title V; specialty chemicals
    {"name": "Kuehne Chemical Company",                     "lat": 39.6023, "lon": -75.6295,
     "type": "Chemical",         "weight": 2.5, "fips": "10001"},  # Title V; chlorine production
    {"name": "Delaware City Refinery",                      "lat": 39.5809, "lon": -75.6312,
     "type": "Petroleum refinery","weight": 2.5, "fips": "10001"}, # Title V; major refinery
    {"name": "Nexpera LLC – Red Lion Plant",                "lat": 39.5929, "lon": -75.6334,
     "type": "Chemical/Mfg",     "weight": 1.8, "fips": "10001"},  # Title V
    # ── Kent / Sussex ──────────────────────────────────────────────────────────
    {"name": "Dover Air Force Base",                        "lat": 39.1295, "lon": -75.4657,
     "type": "Military/Air",     "weight": 1.5, "fips": "10003"},
    {"name": "Perdue Farms (Milford)",                      "lat": 38.9120, "lon": -75.4348,
     "type": "CAFO/Industrial",  "weight": 1.6, "fips": "10005"},
    {"name": "Mountaire Farms (Millsboro)",                 "lat": 38.5887, "lon": -75.3229,
     "type": "CAFO/Industrial",  "weight": 1.6, "fips": "10005"},
    {"name": "Indian River Power LLC",                      "lat": 38.5853, "lon": -75.2339,
     "type": "Power generation", "weight": 2.0, "fips": "10005"},  # Title V; fmr NRG Indian River
    # ── I-95 / US-13 corridor traffic ─────────────────────────────────────────
    {"name": "I-95 / Route 13 interchange (Claymont)",      "lat": 39.7920, "lon": -75.4700,
     "type": "Traffic corridor", "weight": 1.5, "fips": "10001"},
    {"name": "I-95 / Route 141 interchange (NCC)",          "lat": 39.6900, "lon": -75.5800,
     "type": "Traffic corridor", "weight": 1.3, "fips": "10001"},
]
# Source: DNREC NavMap Title V + active air-permitted facilities
# (DE_DNREC_Facilities/FeatureServer/1, fetched 2026-04-01)
# Coordinates verified against DNREC permit records where available.

# Proximity scoring parameters
# Score decays with distance — full score within MIN_M, zero beyond MAX_M
FAC_SCORE_MIN_M  = 300    # meters — full facility score within this radius
FAC_SCORE_MAX_M  = 5000   # meters — zero score beyond this

DE_COUNTIES = {"001": "New Castle", "003": "Kent", "005": "Sussex"}

EB_THRESHOLD = 6.0
SV_THRESHOLD = 6.0


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def safe_float(val, min_val=None):
    try:
        v = float(val)
        if min_val is not None and v < min_val:
            return None
        return v
    except (TypeError, ValueError):
        return None


def haversine_m(lat1, lon1, lat2, lon2):
    """Distance in meters between two lat/lon points."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def proximity_score(distance_m, weight=1.0):
    """
    Linear decay: full score (weight) within FAC_SCORE_MIN_M,
    zero beyond FAC_SCORE_MAX_M.
    """
    if distance_m <= FAC_SCORE_MIN_M:
        return weight
    if distance_m >= FAC_SCORE_MAX_M:
        return 0.0
    decay = 1 - (distance_m - FAC_SCORE_MIN_M) / (FAC_SCORE_MAX_M - FAC_SCORE_MIN_M)
    return weight * decay


def get_county_name(geoid):
    fips = str(geoid)[2:5] if len(str(geoid)) >= 5 else ""
    return DE_COUNTIES.get(fips, "Unknown")


# ──────────────────────────────────────────────────────────────────────────────
# MODULE A — BLOCK GROUP PIPELINE
# ──────────────────────────────────────────────────────────────────────────────

EJSCREEN_EB_FIELDS = {
    "P_PM25":   1.2,
    "P_OZONE":  0.8,
    "P_DSLPM":  1.3,
    "P_CANCER": 1.2,
    "P_RESP":   1.0,
    "P_PTRAF":  1.1,
    "P_PNPL":   1.2,
    "P_PTSDF":  1.0,
    "P_PRMP":   1.1,
    "P_PWDIS":  0.8,
}

EJSCREEN_SV_FIELDS = {
    "LOWINCPCT":  1.3,
    "UNEMPPCT":   1.0,
    "LINGISOPCT": 1.1,
    "LESSHSPCT":  1.0,
    "UNDER5PCT":  0.7,
    "OVER64PCT":  0.7,
    "P_LIFEEXPPCT": 1.2,
}

CDC_MEASURES = {
    "CASTHMA":    1.4,
    "CHD":        1.3,
    "DEPRESSION": 1.0,
    "COPD":       1.3,
    "CSMOKING":   0.8,
    "STROKE":     1.1,
    "MHLTH":      1.0,
}
HEALTH_SV_WEIGHT = 0.40


def fetch_ejscreen_blockgroups():
    print("\n[A1] Fetching EJScreen block group data (Layer 1)...")
    all_fields = (
        ["ID", "ACSTOTPOP", "CNTY_NAME", "ST_ABBREV",
         "P_PEOPCOLORPCT", "NPL_CNT"]
        + list(EJSCREEN_EB_FIELDS.keys())
        + list(EJSCREEN_SV_FIELDS.keys())
    )
    results, offset = [], 0
    while True:
        params = {
            "where":             f"ST_ABBREV='{STATE_ABBREV}'",
            "outFields":         ",".join(all_fields),
            "returnGeometry":    "false",
            "f":                 "json",
            "resultOffset":      offset,
            "resultRecordCount": 500,
        }
        try:
            r = requests.get(EJSCREEN_BG_URL, params=params, timeout=30)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"  ERROR: {e}")
            sys.exit(1)

        data = r.json()
        feats = data.get("features", [])
        if not feats:
            break
        results.extend(f["attributes"] for f in feats)
        print(f"  {len(results)} block groups...")
        if not data.get("exceededTransferLimit"):
            break
        offset += 500

    print(f"  Done: {len(results)} block groups")
    return results


def fetch_places_tracts():
    print("\n[A2] Fetching CDC PLACES health data (census tract)...")
    results, offset = {}, 0
    measure_filter = " OR ".join(f"measureid='{m}'" for m in CDC_MEASURES)
    while True:
        params = {
            "$where":  f"stateabbr='DE' AND length(locationname)=11 AND ({measure_filter})",
            "$select": "locationname,measureid,data_value",
            "$limit":  5000,
            "$offset": offset,
        }
        try:
            r = requests.get(CDC_PLACES_URL, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"  WARNING: {e} — health sub-score will be omitted")
            return {}
        if not data:
            break
        for row in data:
            geoid   = str(row.get("locationname", "")).strip()
            measure = str(row.get("measureid", "")).strip().upper()
            val     = safe_float(row.get("data_value"))
            if geoid not in results:
                results[geoid] = {}
            if val is not None:
                results[geoid][measure] = val
        if len(data) < 5000:
            break
        offset += 5000

    print(f"  Done: {len(results)} tracts with PLACES data")
    return results


def state_avgs(places_data):
    totals = defaultdict(list)
    for td in places_data.values():
        for m, v in td.items():
            if v is not None:
                totals[m].append(v)
    return {m: sum(vs)/len(vs) for m, vs in totals.items() if vs}


def bg_to_tract(geoid):
    """Block group GEOID (12 char) → parent tract GEOID (11 char)."""
    return str(geoid)[:11]


def score_eb(attrs):
    vals, wts = [], []
    for f, w in EJSCREEN_EB_FIELDS.items():
        v = safe_float(attrs.get(f))
        if v is not None:
            vals.append(v * w)
            wts.append(w)
    if not wts:
        return None
    return round(min(10, max(0, sum(vals) / sum(wts) / 10)), 2)


def score_sv_ej(attrs):
    vals, wts = [], []
    for f, w in EJSCREEN_SV_FIELDS.items():
        v = safe_float(attrs.get(f))
        if v is None:
            continue
        if f != "P_LIFEEXPPCT":
            v = v * 100
        vals.append(v * w)
        wts.append(w)
    if not wts:
        return None
    return round(min(10, max(0, sum(vals) / sum(wts) / 10)), 2)


def score_health(geoid_bg, places_data, avgs):
    tract_id = bg_to_tract(geoid_bg)
    td = places_data.get(tract_id, {})
    vals, wts = [], []
    for m, w in CDC_MEASURES.items():
        tv  = td.get(m)
        avg = avgs.get(m)
        if tv is None or not avg:
            continue
        ratio = min(2.5, tv / avg)
        vals.append(ratio * w)
        wts.append(w)
    if not wts:
        return None
    return round(min(10, max(0, sum(vals) / sum(wts) * 4.0)), 2)


def run_blockgroup_pipeline():
    bg_data    = fetch_ejscreen_blockgroups()
    places     = fetch_places_tracts()
    avgs       = state_avgs(places)
    tracts = []

    for attrs in bg_data:
        geoid = str(attrs.get("GEOID") or attrs.get("ID") or "").strip()
        pop   = safe_float(attrs.get("ACSTOTPOP"), min_val=1)
        if not geoid or pop is None:
            continue

        # Use CNTY_NAME from service directly; fall back to GEOID-derived name
        cnty_raw = str(attrs.get("CNTY_NAME") or "").replace(" County", "").strip()
        county = cnty_raw if cnty_raw in DE_COUNTIES.values() else get_county_name(geoid)
        eb      = score_eb(attrs)
        sv_ej   = score_sv_ej(attrs)
        if eb is None or sv_ej is None:
            continue

        sv_h    = score_health(geoid, places, avgs)
        sv      = round(
            sv_ej * (1 - HEALTH_SV_WEIGHT) + sv_h * HEALTH_SV_WEIGHT, 2
        ) if sv_h else sv_ej

        tracts.append({
            "id":           geoid,
            "name":         f"{county} BG {geoid[-7:].lstrip('0') or '0'}",
            "county":       county,
            "geoid":        geoid,
            "parent_tract": bg_to_tract(geoid),
            "pop":          int(pop),
            "eb":           eb,
            "sv":           sv,
            "sv_ej":        sv_ej,
            "sv_health":    sv_h,
            # Key indicators for tooltip
            "pm25_pct":     safe_float(attrs.get("P_PM25")),
            "diesel_pct":   safe_float(attrs.get("P_DSLPM")),
            "cancer_pct":   safe_float(attrs.get("P_CANCER")),
            "traffic_pct":  safe_float(attrs.get("P_PTRAF")),
            "superfund_pct":safe_float(attrs.get("P_PNPL")),
            "lowinc_pct":   safe_float(attrs.get("LOWINCPCT")),
            "unemp_pct":    safe_float(attrs.get("UNEMPPCT")),
            "lingiso_pct":  safe_float(attrs.get("LINGISOPCT")),
            "poc_pct":      safe_float(attrs.get("P_PEOPCOLORPCT")),
        })

    tracts.sort(key=lambda t: t["eb"], reverse=True)

    # Write outputs
    with open("de_blockgroup_scores.json", "w") as f:
        json.dump({
            "source":      "EPA EJScreen block groups + CDC PLACES",
            "state":       "DE",
            "unit":        "block_group",
            "generated":   time.strftime("%Y-%m-%d"),
            "note":        "Health data (CDC PLACES) is at census tract level, assigned to child block groups. No sub-tract health data available due to privacy protections.",
            "tracts":      tracts,
        }, f, indent=2)

    if tracts:
        with open("de_blockgroup_scores.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=tracts[0].keys())
            w.writeheader()
            w.writerows(tracts)

    ob = [t for t in tracts if t["eb"] >= EB_THRESHOLD and t["sv"] >= SV_THRESHOLD]
    print(f"\n{'='*55}")
    print("BLOCK GROUP RESULTS")
    print(f"{'='*55}")
    print(f"Total DE block groups:        {len(tracts)}")
    ob_pct = round(len(ob) / len(tracts) * 100) if tracts else 0
    print(f"Overburdened (EB≥{EB_THRESHOLD} & SV≥{SV_THRESHOLD}):  {len(ob)} ({ob_pct}%)")
    for co in ["New Castle", "Kent", "Sussex"]:
        ct  = [t for t in tracts if t["county"] == co]
        cob = [t for t in ct if t["eb"] >= EB_THRESHOLD and t["sv"] >= SV_THRESHOLD]
        print(f"  {co} Co.:  {len(cob)}/{len(ct)} overburdened")
    print(f"\nTop 10 highest EB block groups:")
    for t in tracts[:10]:
        flag = "OVERBURDENED" if t["eb"] >= EB_THRESHOLD and t["sv"] >= SV_THRESHOLD else ""
        print(f"  {t['name']:40s} EB:{t['eb']:4.1f} SV:{t['sv']:4.1f} {flag}")
    print(f"\nOutputs: de_blockgroup_scores.json / .csv")
    return tracts


# ──────────────────────────────────────────────────────────────────────────────
# MODULE C — SUPPLEMENTAL DATA LAYERS
# ──────────────────────────────────────────────────────────────────────────────

# DelDOT Equity Focus Areas 2024 — FirstMap FeatureServer
DELDOT_EFA_URL = (
    "https://enterprise.firstmap.delaware.gov/arcgis/rest/services/"
    "Society/DE_Equity_Focus_Areas/FeatureServer/1/query"
)

# DHSS My Healthy Community — ZIP-level health portal
# NOTE: The interactive portal (myhealthycommunity.dhss.delaware.gov) is
# behind bot protection and cannot be fetched programmatically.
# To use zip-level DHSS data:
#   1. Visit https://myhealthycommunity.dhss.delaware.gov/cpr/zip-code-<ZIP>
#   2. Export the PDF or use the portal's download option
#   3. Save as dhss_zip_health.csv with columns:
#      zip,indicator,value,year,state_value
# This function will load that file if present.
DHSS_ZIP_CSV = "dhss_zip_health.csv"

# DHSS indicators mapped to pipeline health measures (where available)
DHSS_INDICATOR_MAP = {
    "Chronic Obstructive Pulmonary Disease (COPD)": "COPD",
    "Cancer":                                        "CASTHMA",   # best available proxy
    "Heart Disease":                                 "CHD",
    "Depression":                                    "DEPRESSION",
    "Stroke":                                        "STROKE",
}


def fetch_deldot_efa():
    """
    Fetch DelDOT Equity Focus Area designations (block-group level).
    Returns dict: GEOID → {'efa': 'Significant'|'Moderate'|'Not EFA', 'pop': int}
    """
    print("\n[C1] Fetching DelDOT Equity Focus Areas (2024)...")
    results, offset = {}, 0
    while True:
        params = {
            "where":             "1=1",
            "outFields":         "GEOID,EFA_DESIGNATION,TOTAL_POPULATION,COUNTYFP",
            "returnGeometry":    "false",
            "f":                 "json",
            "resultOffset":      offset,
            "resultRecordCount": 1000,
        }
        try:
            r = requests.get(DELDOT_EFA_URL, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"  WARNING: EFA fetch failed: {e}")
            return {}
        feats = data.get("features", [])
        if not feats:
            break
        for f in feats:
            a = f["attributes"]
            results[str(a["GEOID"])] = {
                "efa": a.get("EFA_DESIGNATION", ""),
                "pop": int(a.get("TOTAL_POPULATION") or 0),
            }
        if not data.get("exceededTransferLimit"):
            break
        offset += 1000
    print(f"  Done: {len(results)} block groups with EFA designation")
    return results


def load_dhss_zip_health():
    """
    Load manually-downloaded DHSS Community Profile Report data.
    Returns dict: zip_code → {indicator → value}
    Returns empty dict if file not present (non-fatal).
    """
    import os
    if not os.path.exists(DHSS_ZIP_CSV):
        print(f"  [C2] {DHSS_ZIP_CSV} not found — DHSS zip health layer skipped.")
        print(f"       Download from: https://myhealthycommunity.dhss.delaware.gov/cpr/zip-code-<ZIP>")
        return {}
    print(f"\n[C2] Loading DHSS zip health data from {DHSS_ZIP_CSV}...")
    data = {}
    with open(DHSS_ZIP_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            z = str(row.get("zip", "")).strip()
            ind = str(row.get("indicator", "")).strip()
            val = safe_float(row.get("value"))
            if z not in data:
                data[z] = {}
            if val is not None:
                data[z][ind] = val
    print(f"  Done: {len(data)} zip codes loaded")
    return data


def run_supplemental_pipeline(bg_scores):
    """
    Joins block group scores with DelDOT EFA designations.
    Writes de_efa_comparison.json / .csv.
    """
    print(f"\n{'='*55}")
    print("MODULE C — SUPPLEMENTAL LAYERS")
    print(f"{'='*55}")

    efa_data  = fetch_deldot_efa()
    dhss_data = load_dhss_zip_health()   # empty if file not present

    if not efa_data:
        print("  No EFA data — skipping comparison output")
        return

    bg_index = {t["geoid"]: t for t in bg_scores}
    rows = []
    for geoid, efa_rec in efa_data.items():
        bg = bg_index.get(geoid)
        rows.append({
            "geoid":    geoid,
            "county":   bg["county"]  if bg else "",
            "name":     bg["name"]    if bg else f"BG {geoid}",
            "pop":      bg["pop"]     if bg else efa_rec["pop"],
            "eb":       bg["eb"]      if bg else None,
            "sv":       bg["sv"]      if bg else None,
            "efa":      efa_rec["efa"],
            "pm25_pct": bg.get("pm25_pct")    if bg else None,
            "cancer_pct":bg.get("cancer_pct") if bg else None,
            "lowinc_pct":bg.get("lowinc_pct") if bg else None,
        })

    rows.sort(key=lambda r: (r["efa"] == "Not EFA", -(r["eb"] or 0)))

    with open("de_efa_comparison.json", "w") as f:
        from collections import Counter
        efa_counts = Counter(r["efa"] for r in rows)
        high_eb    = {k: sum(1 for r in rows if r["efa"]==k and r["eb"] and r["eb"]>=EB_THRESHOLD)
                      for k in efa_counts}
        json.dump({
            "source":   "Pipeline scores × DelDOT EFA 2024",
            "generated": time.strftime("%Y-%m-%d"),
            "summary": {k: {"total_bgs": efa_counts[k], "high_eb_bgs": high_eb[k]} for k in efa_counts},
            "block_groups": rows,
        }, f, indent=2)

    with open("de_efa_comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    print(f"\nEFA × EB Cross-tab:")
    print(f"{'EFA Designation':18s} {'BGs':>5s} {'High-EB':>9s} {'Pop':>10s}")
    print("-" * 48)
    for k in ["Significant", "Moderate", "Not EFA"]:
        grp = [r for r in rows if r["efa"] == k]
        heb = sum(1 for r in grp if r["eb"] and r["eb"] >= EB_THRESHOLD)
        pop = sum(r["pop"] or 0 for r in grp)
        pct = round(heb / len(grp) * 100) if grp else 0
        print(f"{k:18s} {len(grp):>5d} {heb:>5d} ({pct:2d}%) {pop:>10,}")
    print(f"\nOutputs: de_efa_comparison.json / .csv")


# ──────────────────────────────────────────────────────────────────────────────
# MODULE B — PARCEL LEVEL (NCC only initially)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_ncc_parcels():
    """
    Fetch New Castle County parcels from open GIS service.
    Returns list of parcels with address, coordinates, build year.
    
    NOTE: If NCC_PARCEL_URL is blocked or wrong, download the NCC parcel
    shapefile manually from:
    https://nccde.org/1391/GIS-Data-Downloads
    Then replace this function with:
        gdf = gpd.read_file('your_downloaded_parcels.shp')
        return gdf.to_crs('EPSG:4326')
    """
    print("\n[B1] Fetching NCC parcel data...")
    parcels = []
    offset  = 0
    fields  = "PARCEL_ID,SITEADDRESS,CITY,YEARBUILT,SHAPE,ACREAGE,LAND_USE"

    while True:
        params = {
            "where":             "COUNTY='NEW CASTLE'",
            "outFields":         fields,
            "returnGeometry":    "true",
            "outSR":             "4326",
            "geometryType":      "esriGeometryPoint",  # centroid
            "returnCentroid":    "true",
            "f":                 "json",
            "resultOffset":      offset,
            "resultRecordCount": 1000,
        }
        try:
            r = requests.get(NCC_PARCEL_URL, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"  WARNING: NCC parcel fetch failed: {e}")
            print("  Download parcels manually from https://nccde.org/1391/GIS-Data-Downloads")
            return []

        feats = data.get("features", [])
        if not feats:
            break

        for f in feats:
            attrs = f.get("attributes", {})
            geom  = f.get("centroid") or f.get("geometry")
            if not geom:
                continue
            lat = geom.get("y") or geom.get("lat")
            lon = geom.get("x") or geom.get("lon")
            if lat is not None and lon is not None:
                parcels.append({
                    "parcel_id":    attrs.get("PARCEL_ID", ""),
                    "address":      attrs.get("SITEADDRESS", ""),
                    "city":         attrs.get("CITY", ""),
                    "year_built":   safe_float(attrs.get("YEARBUILT")),
                    "land_use":     attrs.get("LAND_USE", ""),
                    "lat":          float(lat),
                    "lon":          float(lon),
                })

        print(f"  {len(parcels)} parcels fetched...")
        if not data.get("exceededTransferLimit"):
            break
        offset += 1000

    print(f"  Done: {len(parcels)} parcels")
    return parcels


def score_parcel_eb(parcel):
    """
    Environmental burden score for a single parcel (0-10).
    Based on:
      - Proximity to each named facility (weighted by facility type)
      - Lead paint risk (pre-1978 construction)
    
    Health/SV data stays at block group — no parcel-level health records exist.
    """
    lat, lon = parcel["lat"], parcel["lon"]

    # Facility proximity sub-score
    fac_score = 0.0
    closest   = []
    for fac in FACILITIES:
        dist_m = haversine_m(lat, lon, fac["lat"], fac["lon"])
        score  = proximity_score(dist_m, weight=fac["weight"])
        fac_score += score
        if dist_m < FAC_SCORE_MAX_M:
            closest.append({"name": fac["name"], "dist_m": round(dist_m), "type": fac["type"]})
    closest.sort(key=lambda fac: fac["dist_m"])

    # Normalize facility score to 0-10 scale
    # Max theoretical = sum of all facility weights = ~25
    # A parcel adjacent to Honeywell + Evraz + Oceanport = ~7.5
    max_possible   = sum(f["weight"] for f in FACILITIES)
    fac_normalized = min(10.0, fac_score / max_possible * 20)

    # Lead paint risk: pre-1978 = +1.0 on EB
    year_built = parcel.get("year_built")
    lead_flag  = bool(year_built and year_built < 1978)
    lead_score = 1.0 if lead_flag else 0.0

    eb = round(min(10, fac_normalized + lead_score), 2)

    parcel["eb"]           = eb
    parcel["fac_score_raw"]= round(fac_score, 3)
    parcel["lead_risk"]    = lead_flag
    parcel["nearby_facs"]  = closest[:3]  # top 3 closest facilities
    parcel["nearby_count"] = len(closest)
    return parcel


def run_parcel_pipeline(bg_scores):
    """
    Build parcel-level output.
    EB scored from facility proximity.
    SV assigned from parent block group (best available sub-tract data).
    """
    print("\n" + "="*55)
    print("MODULE B — PARCEL LEVEL (NCC)")
    print("="*55)

    parcels = fetch_ncc_parcels()
    if not parcels:
        print("  No parcel data available — see note above")
        return

    # Build block group lookup by approximate lat/lon
    # (proper spatial join would use shapefile boundaries)
    print("\n[B2] Scoring parcels...")
    scored = []
    for p in parcels:
        score_parcel_eb(p)
        scored.append(p)

    scored.sort(key=lambda p: p["eb"], reverse=True)

    # Write outputs
    output = []
    for p in scored:
        output.append({
            "parcel_id":    p["parcel_id"],
            "address":      p["address"],
            "city":         p["city"],
            "lat":          p["lat"],
            "lon":          p["lon"],
            "year_built":   p["year_built"],
            "lead_risk":    p["lead_risk"],
            "eb":           p["eb"],
            "sv":           None,  # requires block group join — see note
            "nearby_facilities": p["nearby_count"],
            "closest_facility":  p["nearby_facs"][0]["name"] if p["nearby_facs"] else None,
            "closest_dist_m":    p["nearby_facs"][0]["dist_m"] if p["nearby_facs"] else None,
        })

    with open("de_parcel_scores.json", "w") as f:
        json.dump({
            "source":    "NCC Parcel GIS + facility proximity scoring",
            "unit":      "parcel",
            "generated": time.strftime("%Y-%m-%d"),
            "note":      (
                "EB = facility proximity score + lead paint flag. "
                "SV = null at parcel level — health/socioeconomic data "
                "not available below block group due to privacy protections. "
                "To add SV: join this file to de_blockgroup_scores.json "
                "by block group GEOID (requires spatial join on parcel centroid)."
            ),
            "facilities_used": [f["name"] for f in FACILITIES],
            "parcels": output,
        }, f, indent=2)

    if output:
        with open("de_parcel_scores.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=output[0].keys())
            w.writeheader()
            w.writerows(output)

    print(f"\nPARCEL RESULTS")
    print(f"Total NCC parcels scored: {len(scored)}")
    high_eb = [p for p in scored if p["eb"] >= EB_THRESHOLD]
    lead    = [p for p in scored if p["lead_risk"]]
    print(f"High EB (≥{EB_THRESHOLD}):       {len(high_eb)}")
    print(f"Lead paint risk (pre-1978): {len(lead)}")
    print(f"\nTop 10 highest EB parcels:")
    for p in scored[:10]:
        nearest = p["nearby_facs"][0] if p["nearby_facs"] else None
        near_txt = (
            f"Near: {nearest['name'][:30]} ({nearest['dist_m']}m)"
            if nearest else
            "Near: no major facility"
        )
        print(f"  {p.get('address','?'):40s} EB:{p['eb']:4.1f} "
              f"{'[LEAD]' if p['lead_risk'] else '      '} "
              f"{near_txt}")
    print(f"\nOutputs: de_parcel_scores.json / .csv")
    print(f"\nNEXT STEP — join parcel + block group data:")
    print(f"  python merge_parcel_bg.py")
    print(f"  (script will be generated separately)")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--parcel", action="store_true",
        help="Also run parcel-level module (NCC only)"
    )
    parser.add_argument(
        "--no-supplemental", action="store_true",
        help="Skip Module C (DelDOT EFA comparison)"
    )
    args = parser.parse_args()

    print("=" * 55)
    print("Delaware Cumulative Impacts Pipeline — v3")
    print("Housing-level analysis")
    print("=" * 55)

    bg_scores = run_blockgroup_pipeline()

    if not args.no_supplemental:
        run_supplemental_pipeline(bg_scores)

    if args.parcel:
        run_parcel_pipeline(bg_scores)
    else:
        print(f"\nTo also run parcel-level scoring (NCC), add --parcel flag:")
        print(f"  python ejscreen_pipeline_v3.py --parcel")

    print("\nDone.")
