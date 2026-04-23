#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026 <YOUR NAME>. See LICENSE.md.
"""
probe_places_children.py — detect whether CDC PLACES publishes a youth
(ages 3-17) current-asthma measure at census-tract level for Delaware.

Writes a small metadata blob into `_meta.sources.places_child` of
at_risk_populations.json. This probe never emits per-tract numbers —
it only reports availability, so the UI can optionally render a
tract-level pediatric asthma row if the measure becomes available
(or show a "not currently published by CDC for DE" note otherwise).

Usage (standalone):
    python3 scripts/probe_places_children.py

Requires: requests
"""

from __future__ import annotations

import argparse
import json
import sys

try:
    import requests
except ImportError:
    sys.exit("pip install requests first")


CATALOG = "https://chronicdata.cdc.gov/api/catalog/v1"
RESOURCE_BASE = "https://chronicdata.cdc.gov/resource"

# Candidate measure IDs CDC uses or has used for youth asthma in PLACES.
YOUTH_ASTHMA_MEASURES = ["CASTHMA_C", "CURASTHMA_C", "CHILDASTHMA"]


def discover_candidates() -> list[str]:
    """Return a list of Socrata dataset IDs that look like PLACES children."""
    try:
        resp = requests.get(CATALOG, params={
            "q": "PLACES children",
            "only": "datasets",
            "limit": 20,
        }, timeout=30)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return [r.get("resource", {}).get("id")
                for r in results
                if r.get("resource", {}).get("id")]
    except (requests.RequestException, ValueError):
        return []


def probe_dataset(dataset_id: str, state: str = "DE") -> dict | None:
    """Check whether *dataset_id* exposes youth current-asthma for *state* tracts."""
    url = f"{RESOURCE_BASE}/{dataset_id}.json"
    for measure in YOUTH_ASTHMA_MEASURES:
        try:
            resp = requests.get(url, params={
                "stateabbr": state,
                "measureid": measure,
                "$limit": 1,
            }, timeout=20)
            if resp.status_code != 200:
                continue
            rows = resp.json()
            if rows:
                return {
                    "socrata_id": dataset_id,
                    "measure":    measure,
                    "sample":     rows[0],
                }
        except (requests.RequestException, ValueError):
            continue
    return None


def probe(state: str = "DE") -> dict:
    """Return a _meta.sources.places_child blob."""
    candidates = discover_candidates()
    tried: list[str] = []
    for dataset_id in candidates:
        tried.append(dataset_id)
        hit = probe_dataset(dataset_id, state=state)
        if hit:
            sample = hit["sample"]
            return {
                "name":       "CDC PLACES Children's Data",
                "available":  True,
                "socrata_id": hit["socrata_id"],
                "measure":    hit["measure"],
                "scope":      "tract",
                "vintage":    sample.get("year") or sample.get("data_year"),
                "tried_ids":  tried,
            }
    return {
        "name":      "CDC PLACES Children's Data",
        "available": False,
        "scope":     "tract",
        "tried_ids": tried,
        "note":      "No public PLACES dataset exposes youth current-asthma at tract level for Delaware at probe time.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--state", default="DE")
    args = parser.parse_args()
    print(json.dumps(probe(state=args.state), indent=2))


if __name__ == "__main__":
    main()
