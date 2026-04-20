#!/usr/bin/env python3
"""
fetch_wonder_mortality.py — build wonder_mortality_history.json.

Pulls cause-of-death mortality rates for Delaware's three counties
(New Castle, Kent, Sussex) from CDC WONDER, 1999-present, for EJ-relevant
causes: asthma, cancers, heart disease, stroke, all-cause.

WONDER's "Multiple Cause of Death" REST endpoint takes an XML POST with
a dense parameter block (grouping, measures, filters). This script
builds that block for each cause × group and parses the returned table
into a flat per-county, per-year, per-cause rate.

Output shape:
    {
      "_meta": {
        "source": "CDC WONDER Multiple Cause of Death 1999-2024",
        "endpoint": "https://wonder.cdc.gov/controller/datarequest/D77",
        "geography": "county (DE FIPS 10001/10003/10005)",
        "causes": {...},
        "years": [1999, ..., 2024],
        "retrieved_utc": "...",
        "note": "Age-adjusted rate per 100,000. <10 deaths suppressed by CDC."
      },
      "counties": {
        "10001": {
          "name": "Kent County, DE",
          "years": {
            "2015": {
              "asthma": 1.2,
              "cancer": 168.4,
              "heart":  178.0,
              "stroke": 38.2,
              "all":    820.0
            }, ...
          }
        }, ...
      }
    }

Usage:
    python3 scripts/fetch_wonder_mortality.py           # full pull
    python3 scripts/fetch_wonder_mortality.py --dry-run
    python3 scripts/fetch_wonder_mortality.py --years 2015-2024

NOTE: CDC WONDER requires accepting terms on the web form before the
REST endpoint will respond — our POST includes the accept_datause_restrictions
flag. If requests start returning an HTML error page, open
https://wonder.cdc.gov/ucd-icd10-expanded.html, click through the Data
Use Restrictions, then re-run this script.

Requires: requests  (pip3 install requests)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests first")

OUT = Path(__file__).parent.parent / "wonder_mortality_history.json"

# CDC WONDER "Underlying Cause of Death, 1999-20xx (Expanded)" = dataset D77.
# Older years (1999-2020) are in D76; 2018-present rolls into D158 (provisional).
# For EJ storytelling we want the long time series, so we hit D76 up through
# its last year and D77/D158 for newer vintages. Dataset IDs:
DATASETS = {
    "D76":  (1999, 2020),   # Underlying Cause of Death, 1999-2020
    "D158": (2018, None),   # Provisional MCD, 2018-present (None = current year)
}
ENDPOINT = "https://wonder.cdc.gov/controller/datarequest"

DE_COUNTIES = {
    "10001": "Kent County, DE",
    "10003": "New Castle County, DE",
    "10005": "Sussex County, DE",
}

# Cause → ICD-10 code prefix list. WONDER accepts any mix of specific
# codes, 3-char groups (with asterisk), or "grouped cause" IDs. We use
# 3-char groups — matches how CDC aggregates its public tables.
CAUSES = {
    "asthma": ["J45", "J46"],
    "cancer": [f"C{n:02d}" for n in range(0, 98)],  # all malignancies
    "heart":  ["I20", "I21", "I22", "I23", "I24", "I25"],  # ischemic heart
    "stroke": ["I60", "I61", "I62", "I63", "I64", "I65", "I66", "I67", "I68", "I69"],
    "resp":   [f"J{n:02d}" for n in range(40, 48)],  # chronic lower resp
    "all":    None,  # no ICD filter
}


def _build_xml(dataset: str, county_fips: str, years: list[int],
               icd_codes: list[str] | None) -> str:
    """Assemble the WONDER XML request body.

    The WONDER API mirrors the web form: every control state is a
    <parameter><name>X</name><value>Y</value></parameter> pair. Omitted
    parameters take the web-form default.
    """
    params: list[tuple[str, str]] = [
        ("accept_datause_restrictions", "true"),
        ("B_1",  "D76.V1-level1"),   # group by Year
        ("B_2",  "D76.V2-level2"),   # group by County
        ("M_1",  "D76.M1"),          # measure: Deaths
        ("M_2",  "D76.M2"),          # measure: Population
        ("M_31", "D76.M31"),         # measure: Crude rate
        ("M_41", "D76.M41"),         # measure: Age-adjusted rate
        ("F_D76.V2", county_fips),   # filter: county
        ("F_D76.V1", "*All*"),       # filter: year = all
        ("I_D76.V1", "*All* (All Dates)"),
        ("I_D76.V2", DE_COUNTIES.get(county_fips, county_fips)),
        ("V_D76.V1", ""),
        ("V_D76.V2", county_fips),
        ("V_D76.V9", "*All*"),       # Gender
        ("V_D76.V10", "*All*"),      # Hispanic
        ("V_D76.V7", "*All*"),       # Age Group
        ("V_D76.V8", "*All*"),       # Race
        ("O_V1_fmode", "freg"),
        ("O_V2_fmode", "freg"),
        ("O_age", "D76.V52"),
        ("O_javascript", "on"),
        ("O_precision", "1"),
        ("O_rate_per", "100000"),
        ("O_show_totals", "false"),
        ("O_timeout", "300"),
        ("O_title", "DE county mortality"),
        ("O_ucd", "D76.V2"),
        ("VM_D76.M6_D76.V10", ""),
        ("VM_D76.M6_D76.V17", "*All*"),
        ("VM_D76.M6_D76.V1_S", "*All*"),
        ("VM_D76.M6_D76.V7", "*All*"),
        ("VM_D76.M6_D76.V8", "*All*"),
    ]
    if icd_codes:
        params.append(("F_D76.V22", "*All*"))
        for code in icd_codes:
            params.append(("V_D76.V22", code))
    else:
        params.append(("F_D76.V22", "*All*"))
        params.append(("V_D76.V22", "*All*"))

    root = ET.Element("request-parameters")
    for name, value in params:
        p = ET.SubElement(root, "parameter")
        ET.SubElement(p, "name").text = name
        ET.SubElement(p, "value").text = value
    return ET.tostring(root, encoding="unicode")


def _post(dataset: str, xml_body: str) -> str | None:
    url = f"{ENDPOINT}/{dataset}"
    try:
        r = requests.post(url, data={"request_xml": xml_body, "accept_datause_restrictions": "true"},
                          timeout=300)
    except requests.RequestException as e:
        print(f"    request error: {e}")
        return None
    if r.status_code != 200:
        print(f"    HTTP {r.status_code}: {r.text[:200]!r}")
        return None
    return r.text


def _parse(xml_text: str) -> list[dict]:
    """Extract {year, county_fips, deaths, pop, crude, aa_rate} rows.

    WONDER returns either an XML <response>...<data-table>...</data-table>
    tree or, on error, an HTML-ish error page. We detect the latter and
    return an empty list so the caller can decide whether to retry.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    rows: list[dict] = []
    # <r><c l="2015"/><c l="10001"/><c l="Kent County, DE"/>...<c v="1234"/>...</r>
    for r in root.iter("r"):
        cells = list(r)
        label_cells = [c.get("l", "") for c in cells if c.get("l") is not None]
        value_cells = [c.get("v", "") for c in cells if c.get("v") is not None]
        if len(label_cells) < 2:
            continue
        yr_txt = label_cells[0]
        fips = label_cells[1] if label_cells[1].isdigit() else (
            label_cells[2] if len(label_cells) > 2 and label_cells[2].isdigit() else "")
        try:
            yr = int(yr_txt)
        except ValueError:
            continue
        def _n(idx):
            try:
                return float(value_cells[idx])
            except (IndexError, ValueError):
                return None
        rows.append({
            "year": yr,
            "fips": fips,
            "deaths": _n(0),
            "pop":    _n(1),
            "crude":  _n(2),
            "aa":     _n(3),
        })
    return rows


def fetch(cause: str, county_fips: str, years: list[int]) -> list[dict]:
    """Fetch one cause × county across all requested years.

    We hit D76 for 1999-2020 and fall through to D158 for 2021+ (CDC
    publishes newer data as provisional until the final vintage is
    rolled into D76).
    """
    out: list[dict] = []
    for dataset, (first, last) in DATASETS.items():
        last_eff = last or datetime.now().year
        ds_years = [y for y in years if first <= y <= last_eff]
        if not ds_years:
            continue
        xml_body = _build_xml(dataset, county_fips, ds_years, CAUSES[cause])
        print(f"    {cause}/{county_fips}/{dataset} ({ds_years[0]}-{ds_years[-1]})")
        txt = _post(dataset, xml_body)
        if not txt:
            continue
        rows = _parse(txt)
        out.extend(rows)
        time.sleep(1.0)  # WONDER explicitly asks for <60 req/min
    return out


def build(years: list[int]) -> dict:
    counties: dict[str, dict] = {
        fips: {"name": name, "years": defaultdict(dict)}
        for fips, name in DE_COUNTIES.items()
    }
    year_set: set[int] = set()

    for cause in CAUSES:
        print(f"\ncause={cause}:")
        for fips in DE_COUNTIES:
            rows = fetch(cause, fips, years)
            for r in rows:
                yr = r["year"]
                if yr < 1999 or yr > 2100:
                    continue
                rate = r.get("aa") if r.get("aa") is not None else r.get("crude")
                if rate is None:
                    continue
                counties[fips]["years"][str(yr)][cause] = round(rate, 2)
                year_set.add(yr)

    # Convert defaultdicts back to plain dicts for JSON.
    for c in counties.values():
        c["years"] = dict(c["years"])

    return {
        "_meta": {
            "source":   "CDC WONDER (Underlying Cause of Death)",
            "endpoint": ENDPOINT + "/{D76,D158}",
            "geography": "county (DE FIPS 10001 Kent / 10003 New Castle / 10005 Sussex)",
            "causes": {k: (v or "all causes") for k, v in CAUSES.items()},
            "years":    sorted(year_set),
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note":     ("Age-adjusted rate per 100,000 (falls back to crude if "
                         "AA unavailable). Counts <10 are suppressed by CDC and "
                         "appear as missing here. County-level only — WONDER "
                         "does not release sub-county mortality without special "
                         "access due to re-identification risk."),
        },
        "counties": counties,
    }


def _parse_years(arg: str) -> list[int]:
    if not arg:
        return list(range(1999, datetime.now().year + 1))
    if "-" in arg:
        a, b = arg.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(y) for y in arg.split(",") if y.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--years", default="", help="Year range (default: 1999-present)")
    args = ap.parse_args()

    years = _parse_years(args.years)
    print(f"Fetching CDC WONDER mortality for DE counties, {years[0]}–{years[-1]}")

    payload = build(years)
    n_cty = len(payload["counties"])
    n_rows = sum(len(v["years"]) for v in payload["counties"].values())
    print(f"\n{n_cty} DE counties, {n_rows} county-year rows")

    if args.dry_run:
        print("DRY RUN — not writing.")
        return

    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"Wrote {OUT.name}  ({OUT.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
