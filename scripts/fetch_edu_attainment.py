#!/usr/bin/env python3
"""
fetch_edu_attainment.py
-----------------------
Fetches ACS 5-year educational attainment data (Table B15003) from the
Census API for all Delaware block groups and adds two fields to
de_blockgroups.geojson:

  edu_nohsdip_pct  – % of adults 25+ without a high school diploma
                     (matches EPA EJScreen's LESSHSPCT indicator)
  edu_total_25p    – total population 25+ (denominator, for reference)

Usage:
    python3 scripts/fetch_edu_attainment.py [--key YOUR_CENSUS_API_KEY]

A Census API key is free and recommended (avoids rate limits):
    https://api.census.gov/data/key_signup.html

Without a key the script still works but may be throttled on large requests.

ACS vintage: 2022 5-year (table B15003).
Delaware FIPS: state=10, counties 001 (Kent), 003 (New Castle), 005 (Sussex).

B15003 variable map (relevant subset):
  _001E = Total 25+
  _002E = No schooling completed
  _003E = Nursery school
  _004E = Kindergarten
  _005E–_016E = 1st grade through 12th grade, no diploma
  _017E = Regular high school diploma  ← first "has diploma" bucket
  ... (we don't need 017 onward)
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────

ACS_YEAR   = "2022"
ACS_DATASET = "acs/acs5"
STATE_FIPS  = "10"          # Delaware
DE_COUNTIES = ["001", "003", "005"]  # Kent, New Castle, Sussex

# B15003_001E = total 25+; _002E–_016E = less than HS diploma
TOTAL_VAR   = "B15003_001E"
NO_HS_VARS  = [f"B15003_{str(i).zfill(3)}E" for i in range(2, 17)]  # 002–016
FETCH_VARS  = [TOTAL_VAR] + NO_HS_VARS

GEOJSON_PATH = Path(__file__).parent.parent / "de_blockgroups.geojson"

# ── Census API fetch ─────────────────────────────────────────────────────────

def fetch_county(county_fips: str, api_key: str | None) -> list[dict]:
    """Return list of {geoid, total_25p, no_hs_count} for one county."""
    base = f"https://api.census.gov/data/{ACS_YEAR}/{ACS_DATASET}"
    params = {
        "get": ",".join(FETCH_VARS),
        "for": "block group:*",
        "in":  f"state:{STATE_FIPS} county:{county_fips}",
    }
    if api_key:
        params["key"] = api_key

    url = f"{base}?{urllib.parse.urlencode(params)}"
    print(f"  Fetching county {county_fips} … {url[:80]}…")

    with urllib.request.urlopen(url, timeout=30) as resp:
        rows = json.loads(resp.read())

    # First row is header
    header = rows[0]
    records = []
    for row in rows[1:]:
        r = dict(zip(header, row))
        # Build 12-digit GEOID: state(2) + county(3) + tract(6) + bg(1)
        geoid = r["state"] + r["county"] + r["tract"] + r["block group"]

        total = int(r[TOTAL_VAR]) if r[TOTAL_VAR] not in (None, "-1", "") else None
        no_hs = sum(
            int(r[v]) for v in NO_HS_VARS
            if r.get(v) not in (None, "-1", "")
        ) if total is not None else None

        records.append({
            "geoid":       geoid,
            "total_25p":   total,
            "no_hs_count": no_hs,
        })

    return records


def fetch_all(api_key: str | None) -> dict[str, dict]:
    """Return {geoid: {edu_nohsdip_pct, edu_total_25p}} for all DE block groups."""
    lookup = {}
    for county in DE_COUNTIES:
        for rec in fetch_county(county, api_key):
            total = rec["total_25p"]
            no_hs = rec["no_hs_count"]
            if total and total > 0 and no_hs is not None:
                pct = round(no_hs / total * 100, 1)
            else:
                pct = None
            lookup[rec["geoid"]] = {
                "edu_nohsdip_pct": pct,
                "edu_total_25p":   total,
            }
    return lookup


# ── GeoJSON update ────────────────────────────────────────────────────────────

def update_geojson(lookup: dict[str, dict]) -> None:
    print(f"\nReading {GEOJSON_PATH} …")
    with open(GEOJSON_PATH) as f:
        data = json.load(f)

    matched = 0
    missing = []

    for feat in data["features"]:
        geoid = feat["properties"].get("GEOID")
        if geoid and geoid in lookup:
            feat["properties"].update(lookup[geoid])
            matched += 1
        else:
            missing.append(geoid)

    if missing:
        print(f"  WARNING: {len(missing)} GEOIDs not found in Census response:")
        for g in missing[:10]:
            print(f"    {g}")
        if len(missing) > 10:
            print(f"    … and {len(missing) - 10} more")

    print(f"  Matched and updated {matched} / {len(data['features'])} features.")

    print(f"Writing updated GeoJSON …")
    with open(GEOJSON_PATH, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    print("Done.")


# ── Spot-check ────────────────────────────────────────────────────────────────

def spot_check(lookup: dict[str, dict]) -> None:
    """Print a few known-interesting block groups for sanity checking."""
    checks = {
        "100030101051": "Aniline Village / Hickman Row / Knollwood",
        "100030101041": "Addicks Estates area",
        "100030101042": "NCC BG 101042",
    }
    print("\nSpot-check:")
    for geoid, label in checks.items():
        entry = lookup.get(geoid)
        if entry:
            print(f"  {geoid} ({label}): {entry['edu_nohsdip_pct']}% no-HS  (n={entry['edu_total_25p']})")
        else:
            print(f"  {geoid} ({label}): NOT IN RESPONSE")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", metavar="API_KEY",
                        help="Census API key (optional but recommended)")
    args = parser.parse_args()

    print(f"Fetching ACS {ACS_YEAR} 5-year B15003 for Delaware ({len(DE_COUNTIES)} counties)…")
    try:
        lookup = fetch_all(args.key)
    except Exception as exc:
        print(f"ERROR fetching Census data: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Retrieved data for {len(lookup)} block groups.")
    spot_check(lookup)
    update_geojson(lookup)


if __name__ == "__main__":
    main()
