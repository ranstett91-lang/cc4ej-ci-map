"""
_chem_categories.py — chemical → health-endpoint category classifier
for the multi-pollutant CIS variants (Tier 2.2 of the methodology
roadmap; introduced in v1.3).

Categories
----------
"cancer":
    EPA-classified carcinogens. Authoritative source: TRI carc_ind flag
    (set when EPA classifies a chemical as a known/probable carcinogen).
    Supplemented by an explicit CAS list of well-known carcinogens that
    sometimes carc_ind misses (older TRI submissions without the flag).

"respiratory":
    Inhalation-route respiratory irritants and criteria pollutants —
    chemicals that drive asthma exacerbation, COPD flare-ups, lower-
    respiratory-tract irritation. Curated CAS list; no single TRI flag
    captures this category.

A chemical can belong to MULTIPLE categories (formaldehyde is both
cancer and respiratory). The "combined" CIS surface uses ALL chemicals
unconditionally; cancer and respiratory variants use only chemicals
in the matching category.

Provenance
----------
Cancer additions (when carc_ind=0): WHO IARC Group 1 / 2A list, EPA
IRIS "known" or "likely" carcinogen designations, or California
Proposition 65 "known to cause cancer" listings.

Respiratory: EPA IRIS RfC (chronic inhalation reference concentrations)
or California OEHHA Reference Exposure Levels (RELs); criteria
pollutants under NAAQS where reported in TRI.

Source citations live alongside each CAS entry below so a reviewer
can audit any inclusion.
"""

from __future__ import annotations


# CAS numbers MUST be normalized: TRI sometimes returns "75-44-5",
# sometimes "0000075-44-5"; we strip leading zeros and any whitespace.

# ---- Cancer category ----
# These are added to whatever carc_ind=1 catches in the TRI data.
# Carcinogens that should always count, even if a particular row's
# carc_ind is empty (older TRI submissions can be inconsistent).
CANCER_CAS_ADDITIONS = {
    # CAS:  reason
    "71-43-2":   "Benzene — IARC Group 1, EPA IRIS known carcinogen",
    "75-21-8":   "Ethylene oxide — IARC Group 1, IRIS Class B1",
    "106-99-0":  "1,3-Butadiene — IARC Group 1",
    "75-01-4":   "Vinyl chloride — IARC Group 1",
    "75-07-0":   "Acetaldehyde — IARC Group 2B, IRIS Class B2",
    "50-00-0":   "Formaldehyde — IARC Group 1, IRIS Class B1 (also respiratory)",
    "1332-21-4": "Asbestos — IARC Group 1",
    "75-09-2":   "Methylene chloride / dichloromethane — IARC Group 2A",
    "127-18-4":  "Tetrachloroethylene — IARC Group 2A",
    "79-01-6":   "Trichloroethylene — IARC Group 1",
    "108-88-3":  "Toluene — IARC Group 3 (but EPA IRIS lists subchronic effects; included for safety)",
    "100-41-4":  "Ethylbenzene — IARC Group 2B",
    "1330-20-7": "Xylene — IARC Group 3 (mixed); included as conservative",
    "108-95-2":  "Phenol — IARC Group 3 (excluded as cancer; kept respiratory only)",  # NOT cancer
    "7440-43-9": "Cadmium — IARC Group 1",
    "7440-47-3": "Chromium — Cr(VI) is IARC Group 1",
    "7440-02-0": "Nickel — Cr nickel compounds IARC Group 1",
    "7440-41-7": "Beryllium — IARC Group 1",
    "7439-92-1": "Lead — IARC Group 2B (probable carcinogen)",
    "91-20-3":   "Naphthalene — IARC Group 2B, IRIS Class C",
    "100-42-5":  "Styrene — IARC Group 2A",
    "108-90-7":  "Chlorobenzene — IARC Group 2B",
    "67-66-3":   "Chloroform — IARC Group 2B",
    "75-25-2":   "Bromoform — IARC Group 3 (kept conservative)",
    "74-83-9":   "Methyl bromide — IARC Group 3 (kept conservative)",
    "302-01-2":  "Hydrazine — IARC Group 2B, IRIS Class B2",
    "106-89-8":  "Epichlorohydrin — IARC Group 2A",
    "107-13-1":  "Acrylonitrile — IARC Group 2B",
    "56-23-5":   "Carbon tetrachloride — IARC Group 2B",
    "107-06-2":  "1,2-Dichloroethane — IARC Group 2B",
    "123-91-1":  "1,4-Dioxane — IARC Group 2B",
    "68-12-2":   "Dimethylformamide — IARC Group 2A",
    "107-02-8":  "Acrolein — IARC Group 3 (kept respiratory only; not cancer)",  # NOT cancer
    "7782-49-2": "Selenium — IARC Group 3; not cancer",  # NOT cancer
    "7440-50-8": "Copper — not classified as carcinogen",  # NOT cancer
}
# Filter to actual carcinogens only (entries marked NOT cancer above are
# placeholders for documentation; remove them from the inclusion set).
_CANCER_NEGATIVE = {"108-95-2", "107-02-8", "7782-49-2", "7440-50-8"}
CANCER_CAS_ADDITIONS = {k: v for k, v in CANCER_CAS_ADDITIONS.items()
                        if k not in _CANCER_NEGATIVE}


# ---- Respiratory category ----
# Curated CAS list of respiratory tract irritants and criteria pollutant
# precursors that appear in TRI submissions. Sources: EPA IRIS RfC,
# OEHHA RELs, US criteria pollutant list.
RESPIRATORY_CAS = {
    "7664-93-9":  "Sulfuric acid (acid mists) — RfC; criteria PM precursor",
    "7647-01-0":  "Hydrochloric acid — IRIS RfC",
    "7664-39-3":  "Hydrogen fluoride — IRIS RfC",
    "7446-09-5":  "Sulfur dioxide — NAAQS criteria pollutant",
    "10102-43-9": "Nitric oxide — NOx, NAAQS precursor",
    "10102-44-0": "Nitrogen dioxide — NAAQS criteria pollutant",
    "7664-41-7":  "Ammonia — IRIS RfC; PM precursor",
    "7782-50-5":  "Chlorine — IRIS RfC",
    "75-44-5":    "Phosgene — OEHHA REL",
    "7783-06-4":  "Hydrogen sulfide — IRIS RfC",
    "74-90-8":    "Hydrogen cyanide — IRIS RfC",
    "108-95-2":   "Phenol — IRIS RfC",
    "107-02-8":   "Acrolein — IRIS RfC (potent respiratory irritant)",
    "75-07-0":    "Acetaldehyde — IRIS RfC; also cancer (multi-category)",
    "50-00-0":    "Formaldehyde — IRIS RfC; also cancer (multi-category)",
    "108-88-3":   "Toluene — IRIS RfC",
    "1330-20-7":  "Xylene (mixed) — IRIS RfC",
    "100-41-4":   "Ethylbenzene — IRIS RfC; also cancer",
    "100-42-5":   "Styrene — IRIS RfC; also cancer",
    "26471-62-5": "Toluene diisocyanate — RfC",
    "584-84-9":   "2,4-TDI — RfC",
    "91-20-3":    "Naphthalene — IRIS RfC; also cancer",
    "67-56-1":    "Methanol — IRIS RfC",
    "127-18-4":   "Tetrachloroethylene — IRIS RfC; also cancer",
    "75-09-2":    "Methylene chloride — IRIS RfC; also cancer",
    "79-01-6":    "Trichloroethylene — IRIS RfC; also cancer",
    "75-15-0":    "Carbon disulfide — IRIS RfC",
    "67-64-1":    "Acetone — IRIS RfC",
    "78-93-3":    "Methyl ethyl ketone (MEK) — IRIS RfC",
    "7440-50-8":  "Copper — copper fume causes metal-fume fever (respiratory)",
    "7439-96-5":  "Manganese — IRIS RfC",
    "7440-02-0":  "Nickel — IRIS RfC; also cancer",
    "7440-43-9":  "Cadmium — IRIS RfC; also cancer",
    "7440-47-3":  "Chromium — IRIS RfC; Cr(VI) also cancer",
    "7439-92-1":  "Lead — IRIS RfC; also cancer",
    "7440-41-7":  "Beryllium — IRIS RfC; also cancer",
    "7440-36-0":  "Antimony — IRIS RfC",
    "7782-49-2":  "Selenium — IRIS RfC",
}


def normalize_cas(cas: str | None) -> str:
    """Strip whitespace and leading zeros so CAS lookups are stable across
    TRI's inconsistent zero-padding ('0000075-44-5' → '75-44-5')."""
    if not cas:
        return ""
    cas = cas.strip()
    if "-" not in cas:
        return cas
    parts = cas.split("-")
    parts[0] = parts[0].lstrip("0") or "0"
    return "-".join(parts)


def categories_for_chem(chem: dict) -> list[str]:
    """Return the list of categories (zero or more) a chemical belongs to,
    given its TRI metadata block from tri_chemical_history.json.

    `chem` is expected to have keys: cas, name, hap_flag, carc_flag, metal_flag.
    """
    cas = normalize_cas(chem.get("cas") or "")
    cats: list[str] = []
    if chem.get("carc_flag"):
        cats.append("cancer")
    elif cas in CANCER_CAS_ADDITIONS:
        cats.append("cancer")
    if cas in RESPIRATORY_CAS:
        cats.append("respiratory")
    return cats


def classify_all(chemicals: dict) -> dict[str, list[str]]:
    """Apply categories_for_chem across a {chem_id: {...}} mapping.

    Returns: {chem_id: ["cancer", "respiratory", ...] | []}
    """
    return {chem_id: categories_for_chem(meta)
            for chem_id, meta in chemicals.items()}


def filter_chemicals(chemicals: dict, category: str) -> set[str]:
    """Return the set of chem_ids that belong to `category`. The special
    category "combined" returns ALL chem_ids unconditionally (matches the
    pre-v1.3 behavior of summing every chemical)."""
    if category == "combined":
        return set(chemicals.keys())
    return {chem_id for chem_id, meta in chemicals.items()
            if category in categories_for_chem(meta)}


__all__ = [
    "CANCER_CAS_ADDITIONS",
    "RESPIRATORY_CAS",
    "normalize_cas",
    "categories_for_chem",
    "classify_all",
    "filter_chemicals",
]
