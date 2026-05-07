#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026. See LICENSE.md.
"""build_facility_weights.py — derive TRI-data-driven facility weights.

Replaces the hand-curated `weight` values in facilities.json with values
derived from public-record EPA TRI data. The composite formula:

    weight = clamp(1.2, 3.0,
        base_tier × (1 + α · log10(1 + recent_5yr_avg_lbs / 1000))
                  × (1 + β · HAP_flag)
                  × (1 + γ · NAICS_high_risk_flag))

Where:
    base_tier        — rubric tier from facilities.json `weight_tier`
                       (set by patch_facility_weight_tier.py from
                       weighting_rubric.md)
    recent_5yr_avg   — mean annual TRI release (lbs/yr) over the most
                       recent 5 reporting years available in tri_history.json
    HAP_flag         — 1 if any of facility's top_chemicals matches the EPA
                       Hazardous Air Pollutants list, 0 otherwise
    NAICS_high_risk  — 1 if facility NAICS prefix is in
                       {324 petroleum/coal, 325 chemicals, 331 primary
                       metals, 562 waste mgmt}, 0 otherwise

    α = 0.03, β = 0.05, γ = 0.05  — calibrated so the modifier maximum is
                                     ~1.27, keeping output range close to
                                     the original 1.2–3.0 rubric span.

Facilities without `trifid` (Superfund-only, legacy contamination, traffic
corridors, etc.) keep their existing rubric tier weight unchanged.

Output
------
    facility_weights.json   — keyed by trifid: {weight, base_tier, recent_5yr_avg,
                                                hap_flag, naics_high_risk_flag,
                                                multiplier, ...}
    weight_provenance.csv   — full audit trail (one row per facility)

Usage
-----
    python3 scripts/build_facility_weights.py            # dry-run preview
    python3 scripts/build_facility_weights.py --patch    # write weights to
                                                          # facilities.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

# Shared CIS math/stats helpers — single source of truth.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cis_stats import spearman_rho

ROOT = Path(__file__).resolve().parent.parent
FAC = ROOT / "facilities.json"
TRI_FAC = ROOT / "tri_facilities.json"
TRI_HIST = ROOT / "tri_history.json"
WEIGHTS_OUT = ROOT / "facility_weights.json"
PROV_OUT = ROOT / "weight_provenance.csv"

# Calibration coefficients. See module docstring.
ALPHA = 0.03   # recent-emissions multiplier
BETA = 0.05    # HAP flag bonus
GAMMA = 0.05   # NAICS high-risk bonus

WEIGHT_MIN = 1.2
WEIGHT_MAX = 3.0
RECENT_YEARS = 5

# EPA Hazardous Air Pollutants — keyword markers matched case-insensitively
# against TRI top_chemicals.name. Sourced from EPA Clean Air Act §112 list
# (188 chemicals as of the 2026 list at
# https://www.epa.gov/haps/initial-list-hazardous-air-pollutants-modifications).
# These markers cover the substantial majority that appear in
# Delaware/PA/NJ region TRI submissions. Each keyword is a substring matched
# in lowercased chemical names; care required to avoid false positives
# (e.g. plain "bromine" is intentionally excluded — it's not on the §112
# list, only specific brominated compounds are).
HAP_KEYWORDS = [
    "benzene",
    "formaldehyde",
    "toluene",
    "xylene",
    "methanol",
    "methylene chloride",     # synonym: dichloromethane (next entry)
    "dichloromethane",
    "lead",                   # Pb and Pb compounds
    "mercury",                # Hg and Hg compounds
    "hydrochloric acid",
    "hydrogen fluoride",
    "sulfuric acid",          # acid mists added in 1990 CAA amendments
    "chlorine",
    "ethylene oxide",
    "1,3-butadiene",
    "vinyl chloride",
    "asbestos",
    "acrylonitrile",
    "cadmium",
    "chromium",               # any chromium match; Cr(VI) is the §112 form
    "nickel",
    "polycyclic aromatic",
    "naphthalene",
    "styrene",
    "ethylbenzene",
    "phosgene",
    "phosphine",
    "bromoform",              # CHBr3 — replaces bare "bromine" (audit fix 3.2)
    "methyl bromide",         # CH3Br — replaces bare "bromine" (audit fix 3.2)
    "vinylidene chloride",
    "trichloroethylene",
    "tetrachloroethylene",    # IUPAC; some TRI rows use the synonym below
    "perchloroethylene",      # PCE — common TRI name for tetrachloroethylene
    "n-hexane",
    "diethanolamine",
    "1,4-dioxane",
    "1,2-dichloroethane",
    "carbon tetrachloride",
    "dimethylformamide",
    "epichlorohydrin",
    "hydrazine",
    "vinyl acetate",
    "antimony",
    "beryllium",
    "cobalt",
    "manganese",
    "selenium",
]

# NAICS prefixes flagged as high-risk per EPA EJScreen / RSEI proximity
# indicator emphasis. Petroleum, chemicals, primary metals, waste management.
NAICS_HIGH_RISK_PREFIXES = ["324", "325", "331", "562"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def is_hap(top_chemicals: list[dict]) -> tuple[bool, list[str]]:
    """Return (flag, list_of_matched_keywords) given a TRI top_chemicals list.

    Used both to set hap_flag and to populate the audit CSV with the matched
    keyword(s) so reviewers can see WHY a facility was HAP-flagged.
    """
    matches = []
    for chem in top_chemicals or []:
        name = (chem.get("name") or "").lower()
        for kw in HAP_KEYWORDS:
            if kw in name and kw not in matches:
                matches.append(kw)
    return (bool(matches), matches)


def is_high_risk_naics(naics: str | None) -> bool:
    if not naics:
        return False
    return any(str(naics).startswith(p) for p in NAICS_HIGH_RISK_PREFIXES)


def recent_5yr_avg(history_for_facility: dict, recent_n: int = RECENT_YEARS) -> tuple[float, list[int]]:
    """Mean annual release (lbs/yr) over the most-recent N years with data.

    Returns (mean, list_of_years_used). If <N years exist, uses what's there.
    Returns (0.0, []) if no years have positive values.
    """
    if not history_for_facility:
        return 0.0, []
    items = sorted(((int(y), float(v)) for y, v in history_for_facility.items()
                   if v is not None and float(v) >= 0),
                  key=lambda t: t[0],
                  reverse=True)
    used = items[:recent_n]
    if not used:
        return 0.0, []
    avg = sum(v for _, v in used) / len(used)
    return avg, [y for y, _ in used]


def derive_weight(base_tier: float, recent_avg: float, hap: bool, hr_naics: bool) -> tuple[float, float]:
    """Apply composite formula. Returns (weight, multiplier)."""
    log_term = math.log10(1.0 + max(recent_avg, 0) / 1000.0)
    multiplier = (1.0 + ALPHA * log_term) * (1.0 + BETA * (1 if hap else 0)) * (1.0 + GAMMA * (1 if hr_naics else 0))
    raw = base_tier * multiplier
    clamped = max(WEIGHT_MIN, min(WEIGHT_MAX, raw))
    return round(clamped, 2), round(multiplier, 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", action="store_true",
                    help="overwrite `weight` in facilities.json with derived values")
    ap.add_argument("--no-csv", action="store_true",
                    help="skip writing weight_provenance.csv")
    args = ap.parse_args()

    fac_data = load_json(FAC)
    tri_fac_blob = load_json(TRI_FAC).get("facilities", {})
    tri_hist_blob = load_json(TRI_HIST).get("facilities", {})

    feats = fac_data["features"]
    rows = []
    weights_payload = {}
    matched_count = 0
    unmatched_count = 0
    no_recent_emissions = 0
    rank_pairs = []  # (old_weight, new_weight) for sanity check

    for feat in feats:
        p = feat["properties"]
        name = p.get("name", "")
        old_weight = p.get("weight")
        base_tier = p.get("weight_tier")
        trifid = p.get("trifid")

        if base_tier is None:
            print(f"ERROR: {name!r} missing weight_tier — run "
                  f"patch_facility_weight_tier.py first", file=sys.stderr)
            return 1

        if not trifid:
            # No TRI match — keep existing weight unchanged.
            unmatched_count += 1
            rows.append({
                "name": name,
                "trifid": "",
                "old_weight": old_weight,
                "weight_tier": base_tier,
                "recent_5yr_avg_lbs": "",
                "years_used": "",
                "hap_flag": "",
                "hap_keywords": "",
                "naics": "",
                "naics_high_risk_flag": "",
                "multiplier": 1.0,
                "new_weight": old_weight,
                "method": "rubric tier (no TRI match)",
            })
            rank_pairs.append((float(old_weight), float(old_weight)))
            continue

        tri_meta = tri_fac_blob.get(trifid, {})
        history = tri_hist_blob.get(trifid, {})
        recent_avg, years_used = recent_5yr_avg(history)
        if recent_avg <= 0:
            no_recent_emissions += 1

        top_chems = tri_meta.get("top_chemicals", [])
        hap, hap_kws = is_hap(top_chems)
        naics = tri_meta.get("naics", "")
        hr_naics = is_high_risk_naics(naics)

        new_weight, multiplier = derive_weight(float(base_tier), recent_avg, hap, hr_naics)
        rank_pairs.append((float(old_weight), new_weight))
        matched_count += 1

        weights_payload[trifid] = {
            "name": name,
            "weight": new_weight,
            "base_tier": float(base_tier),
            "recent_5yr_avg_lbs": round(recent_avg, 1),
            "years_used": years_used,
            "hap_flag": hap,
            "hap_keywords": hap_kws,
            "naics": naics,
            "naics_high_risk_flag": hr_naics,
            "multiplier": multiplier,
        }

        rows.append({
            "name": name,
            "trifid": trifid,
            "old_weight": old_weight,
            "weight_tier": base_tier,
            "recent_5yr_avg_lbs": round(recent_avg, 1),
            "years_used": ",".join(str(y) for y in years_used),
            "hap_flag": hap,
            "hap_keywords": "; ".join(hap_kws),
            "naics": naics,
            "naics_high_risk_flag": hr_naics,
            "multiplier": multiplier,
            "new_weight": new_weight,
            "method": "TRI-derived composite",
        })

    # Spearman rank correlation between old & new weights — sanity check that
    # we haven't randomly shuffled severity ordering.
    rho = spearman_rho([p[0] for p in rank_pairs], [p[1] for p in rank_pairs])

    # Print headline + biggest-shift table.
    shifts = sorted(rows, key=lambda r: -abs(float(r["new_weight"]) - float(r["old_weight"]))
                    if r["old_weight"] is not None else 0)
    print(f"Facilities: {len(feats)}  matched-to-TRI: {matched_count}  unmatched: {unmatched_count}")
    print(f"Old vs new weight rank correlation (Spearman ρ): {rho:.3f}")
    print(f"Facilities with zero recent (last-5yr) emissions: {no_recent_emissions}")
    print(f"Coefficients: α={ALPHA}, β={BETA}, γ={GAMMA}; cap=[{WEIGHT_MIN}, {WEIGHT_MAX}]")
    print(f"\nTop 12 facilities by |Δ weight|:")
    print(f"  {'name':50s}  {'old':>4s}  {'new':>4s}  {'mult':>5s}  notes")
    for r in shifts[:12]:
        old = r["old_weight"]
        new = r["new_weight"]
        mult = r["multiplier"]
        notes = []
        if r.get("hap_flag"):
            notes.append("HAP")
        if r.get("naics_high_risk_flag"):
            notes.append(f"NAICS {r['naics']}")
        if r.get("recent_5yr_avg_lbs"):
            notes.append(f"{float(r['recent_5yr_avg_lbs']):,.0f} lb/yr avg")
        if not r.get("trifid"):
            notes.append("no TRI")
        print(f"  {r['name'][:50]:50s}  {old:4.1f}  {new:4.1f}  {mult:5.3f}  {' / '.join(notes)[:60]}")

    if not args.no_csv:
        with PROV_OUT.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nWrote {PROV_OUT.relative_to(ROOT)}")

    weights_meta = {
        "_meta": {
            "method": "TRI-derived composite weight",
            "formula": ("clamp(1.2, 3.0, base_tier × "
                        "(1 + α · log10(1 + recent_5yr_avg/1000)) × "
                        "(1 + β · HAP) × (1 + γ · NAICS_high_risk))"),
            "alpha": ALPHA,
            "beta": BETA,
            "gamma": GAMMA,
            "weight_min": WEIGHT_MIN,
            "weight_max": WEIGHT_MAX,
            "recent_years_window": RECENT_YEARS,
            "hap_keywords": HAP_KEYWORDS,
            "naics_high_risk_prefixes": NAICS_HIGH_RISK_PREFIXES,
            "facilities_matched": matched_count,
            "facilities_unmatched_kept_rubric": unmatched_count,
            "rank_correlation_old_vs_new": round(rho, 3),
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "weights": weights_payload,
    }
    WEIGHTS_OUT.write_text(json.dumps(weights_meta, separators=(",", ":")))
    print(f"Wrote {WEIGHTS_OUT.relative_to(ROOT)}")

    if not args.patch:
        print("\nDry-run only. Re-run with --patch to write derived weights "
              "into facilities.json.")
        return 0

    # Patch facilities.json — write the new weight values AND update
    # weight_basis to reflect the TRI-derived provenance. weight_tier
    # (regulatory rubric class) stays unchanged so basis still cites the
    # underlying classification; the new sentence appended to basis explains
    # the operational weight derivation.
    for feat, row in zip(feats, rows):
        feat["properties"]["weight"] = float(row["new_weight"])
        existing = feat["properties"].get("weight_basis", "")
        if row["trifid"]:
            recent = float(row["recent_5yr_avg_lbs"]) if row["recent_5yr_avg_lbs"] else 0.0
            mult = float(row["multiplier"])
            base = float(row["weight_tier"])
            extras = []
            if row["hap_flag"]:
                extras.append(f"HAP+ ({row['hap_keywords']})" if row["hap_keywords"] else "HAP+")
            if row["naics_high_risk_flag"]:
                extras.append(f"NAICS {row['naics']} (high-risk)")
            extras_str = "; ".join(extras) if extras else "no HAP / non-high-risk NAICS"
            tri_line = (f"TRI-derived weight v1.1: {row['new_weight']:.2f} = "
                        f"base {base:.1f} × {mult:.3f} "
                        f"(recent 5yr avg {recent:,.0f} lb/yr; {extras_str})")
            # Strip any prior derivation line so re-runs are idempotent.
            base_basis = existing.split(" || TRI-derived")[0]
            feat["properties"]["weight_basis"] = base_basis + " || " + tri_line
        else:
            # No TRI match — note the rubric-only provenance idempotently.
            base_basis = existing.split(" || ")[0]
            if "rubric tier (no TRI match)" not in base_basis:
                feat["properties"]["weight_basis"] = base_basis + " || rubric tier (no TRI match)"

    FAC.write_text(json.dumps(fac_data, separators=(",", ":")))
    print(f"\nApplied: patched {len(feats)} facility weights + bases into facilities.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
