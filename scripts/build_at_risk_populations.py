#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026 <YOUR NAME>. See LICENSE.md.
"""
build_at_risk_populations.py — compose at_risk_populations.json

County-level at-risk population indicators for Delaware's three counties
(Kent 10001, New Castle 10003, Sussex 10005). Mirrors the American Lung
Association "State of the Air" methodology:
    - State BRFSS Child ACBS current-asthma rate (or NHIS national fallback)
      × county under-18 ACS population = pediatric asthma est_count.
    - County age structure (total pop, U-18, 65+) from ACS 5-year B01001.
    - Adult asthma / COPD / CVD / lung cancer / poverty / people-of-color
      counts and air-quality grades transcribed from the published SOTA
      county tables (scripts/sota_de_<year>.csv).
    - Optional tract-level pediatric asthma availability probe for PLACES
      Children's Data (records availability only; never per-tract numbers).

Usage:
    python3 scripts/build_at_risk_populations.py               # fetch + write
    python3 scripts/build_at_risk_populations.py --dry-run     # preview
    python3 scripts/build_at_risk_populations.py --sota-year 2026
    python3 scripts/build_at_risk_populations.py --acs-year 2023

Requires: requests
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import fetch_acs_age_structure
    import fetch_brfss_child_asthma
    import fetch_sota_at_risk
    import probe_places_children
except ImportError:
    # Allow running as `python3 scripts/build_at_risk_populations.py`
    sys.path.insert(0, str(Path(__file__).parent))
    import fetch_acs_age_structure          # noqa: E402
    import fetch_brfss_child_asthma         # noqa: E402
    import fetch_sota_at_risk               # noqa: E402
    import probe_places_children            # noqa: E402


OUT = Path(__file__).parent.parent / "at_risk_populations.json"


def _field(value, source: str, vintage, extra: dict | None = None) -> dict:
    """Wrap a numeric value with source+vintage metadata.

    Blank/None values are preserved as-is with source='pending' so the UI
    can show an honest gap rather than a fabricated number.
    """
    if value is None:
        return {"value": None, "source": "pending", "vintage": None}
    rec: dict = {"source": source, "vintage": vintage}
    rec.update(extra or {})
    # Separate count vs rate presentation for numeric fields at the call-site.
    return rec


def compose_county(fips: str, acs: dict, brfss: dict, sota: dict) -> dict:
    """Compose one county's block in the output JSON."""
    # Pediatric asthma est_count = rate × U-18 population.
    u18 = acs.get("u18_count")
    rate = brfss.get("rate_pct")
    if u18 is not None and rate is not None:
        est = int(round(u18 * rate / 100))
    else:
        est = None

    return {
        "name":             acs.get("name") or sota.get("name") or fips,
        "population_total": {
            "value":  acs.get("pop"),
            "source": "acs",
            "vintage": acs.get("vintage"),
        },
        "children_under_18": {
            "count":  acs.get("u18_count"),
            "pct":    acs.get("u18_pct"),
            "source": "acs",
            "vintage": acs.get("vintage"),
        },
        "adults_65_plus": {
            "count":  acs.get("o65_count"),
            "pct":    acs.get("o65_pct"),
            "source": "acs",
            "vintage": acs.get("vintage"),
        },
        "pediatric_asthma": {
            "rate_pct":  rate,
            "est_count": est,
            "source":    brfss.get("source"),
            "scope":     brfss.get("scope"),
            "vintage":   brfss.get("vintage"),
            "fallback":  brfss.get("fallback", False),
        },
        "adult_asthma": {
            "rate_pct":  sota.get("adult_asthma_pct"),
            "source":    "sota" if sota.get("adult_asthma_pct") is not None else "pending",
            "vintage":   sota.get("vintage"),
        },
        "copd": {
            "rate_pct":  sota.get("copd_pct"),
            "source":    "sota" if sota.get("copd_pct") is not None else "pending",
            "vintage":   sota.get("vintage"),
        },
        "cardiovascular_disease": {
            "rate_pct":  sota.get("cvd_pct"),
            "source":    "sota" if sota.get("cvd_pct") is not None else "pending",
            "vintage":   sota.get("vintage"),
        },
        "lung_cancer": {
            "count":     sota.get("lung_cancer"),
            "source":    "sota" if sota.get("lung_cancer") is not None else "pending",
            "vintage":   sota.get("vintage"),
        },
        "sota_grades": {
            "ozone":        {"grade": sota.get("ozone_grade"),        "days":  sota.get("ozone_days"),
                             "vintage": sota.get("vintage")},
            "pm25_daily":   {"grade": sota.get("pm25_daily_grade"),   "days":  sota.get("pm25_daily_days"),
                             "vintage": sota.get("vintage")},
            "pm25_annual":  {"status": sota.get("pm25_annual_status"), "value": sota.get("pm25_annual_value"),
                             "vintage": sota.get("vintage")},
        },
        "sota_additional": {
            "poverty":         {"count": sota.get("poverty"),
                                "source": "sota" if sota.get("poverty") is not None else "pending",
                                "vintage": sota.get("vintage")},
            "people_of_color": {"count": sota.get("people_of_color"),
                                "source": "sota" if sota.get("people_of_color") is not None else "pending",
                                "vintage": sota.get("vintage")},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary; do not write at_risk_populations.json")
    parser.add_argument("--sota-year", type=int, default=2025,
                        help="SOTA report year to read from scripts/sota_de_<year>.csv")
    parser.add_argument("--acs-year", type=int, default=2023,
                        help="Latest year of the ACS 5-year window")
    parser.add_argument("--skip-places-probe", action="store_true",
                        help="Don't hit the PLACES catalog API")
    args = parser.parse_args()

    print(f"Fetching ACS {args.acs_year - 4}-{args.acs_year} age structure for DE...")
    census_key = os.environ.get("CENSUS_API_KEY")
    acs = fetch_acs_age_structure.fetch_acs(
        year=args.acs_year,
        api_key=census_key,
    )
    print(f"  {len(acs)} counties")

    print("Fetching ACS age structure for DE places (Wilmington)...")
    acs_places = fetch_acs_age_structure.fetch_acs_places(
        year=args.acs_year,
        api_key=census_key,
    )
    print(f"  {len(acs_places)} places")

    print("Fetching BRFSS child asthma (DE state, NHIS fallback)...")
    brfss = fetch_brfss_child_asthma.fetch(state="DE")
    tag = "state" if not brfss.get("fallback") else "NHIS national fallback"
    print(f"  rate={brfss.get('rate_pct')}% ({tag}, vintage {brfss.get('vintage')})")

    print(f"Reading SOTA {args.sota_year} DE county tables...")
    sota = fetch_sota_at_risk.read(year=args.sota_year)
    print(f"  {len(sota)} counties")

    if args.skip_places_probe:
        places_child = {"name": "CDC PLACES Children's Data",
                        "available": False, "scope": "tract",
                        "note": "Probe skipped by --skip-places-probe."}
    else:
        print("Probing CDC PLACES for children's current-asthma measure...")
        places_child = probe_places_children.probe(state="DE")
        print(f"  available={places_child.get('available')}")

    counties_out: dict[str, dict] = {}
    for fips, sota_row in sota.items():
        acs_row = acs.get(fips, {})
        counties_out[fips] = compose_county(fips, acs_row, brfss, sota_row)

    # Compose sub-county "cities" records for DE places. Same BRFSS/NHIS
    # pediatric-asthma rate as the parent county (BRFSS doesn't release
    # below state level), applied to the city's own U-18 ACS denominator
    # so the Wilmington pediatric asthma est_count is Wilmington-scale.
    cities_out: dict[str, dict] = {}
    for place_fips, place_acs in acs_places.items():
        parent = place_acs.get("parent_county")
        u18 = place_acs.get("u18_count")
        rate = brfss.get("rate_pct")
        est = int(round(u18 * rate / 100)) if (u18 is not None and rate is not None) else None
        cities_out[place_fips] = {
            "name":          place_acs.get("name"),
            "parent_county": parent,
            "population_total": {
                "value":  place_acs.get("pop"),
                "source": "acs",
                "vintage": place_acs.get("vintage"),
            },
            "children_under_18": {
                "count":  place_acs.get("u18_count"),
                "pct":    place_acs.get("u18_pct"),
                "source": "acs",
                "vintage": place_acs.get("vintage"),
            },
            "adults_65_plus": {
                "count":  place_acs.get("o65_count"),
                "pct":    place_acs.get("o65_pct"),
                "source": "acs",
                "vintage": place_acs.get("vintage"),
            },
            "pediatric_asthma": {
                "rate_pct":  rate,
                "est_count": est,
                "source":    brfss.get("source"),
                "scope":     brfss.get("scope"),
                "vintage":   brfss.get("vintage"),
                "fallback":  brfss.get("fallback", False),
                "note":      "Same state rate as the parent county, applied to city U-18 ACS population.",
            },
        }

    payload = {
        "_meta": {
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "state":    "DE",
            "counties": {fips: rec["name"] for fips, rec in counties_out.items()},
            "sources": {
                "sota": {
                    "name":        "American Lung Association State of the Air",
                    "url":         "https://www.lung.org/research/sota",
                    "report_year": args.sota_year,
                },
                "acs": {
                    "name":    "US Census ACS 5-year",
                    "table":   "B01001",
                    "url":     f"https://api.census.gov/data/{args.acs_year}/acs/acs5",
                    "vintage": f"{args.acs_year - 4}-{args.acs_year}",
                },
                "brfss_child": {
                    "name":    "CDC BRFSS Child Asthma Call-Back Survey",
                    "url":     brfss.get("source_url", "https://www.cdc.gov/brfss/acbs/"),
                    "vintage": brfss.get("vintage"),
                    "scope":   brfss.get("scope"),
                },
                "nhis": {
                    "name": "CDC NHIS (national pediatric asthma)",
                    "url":  "https://www.cdc.gov/asthma/nhis/default.htm",
                    "scope": "national",
                },
                "places_child": places_child,
            },
            "note": "County-level at-risk population indicators following the ALA "
                    "State of the Air methodology. Displayed in the 'At-Risk "
                    "Populations' info-panel section. Fields with source='pending' "
                    "need transcription from the SOTA county tables.",
            "wilmington_tracts": [],
        },
        "counties": counties_out,
        "cities":   cities_out,
    }

    if args.dry_run:
        print("\nDRY RUN — summary:")
        for fips, rec in counties_out.items():
            pa = rec["pediatric_asthma"]
            print(f"  {fips} {rec['name']}: pop={rec['population_total']['value']} "
                  f"u18={rec['children_under_18']['count']} "
                  f"peds_asthma={pa['rate_pct']}% est={pa['est_count']} "
                  f"(fallback={pa['fallback']})")
        return

    with OUT.open("w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"\nWrote {OUT.name}")


if __name__ == "__main__":
    main()
