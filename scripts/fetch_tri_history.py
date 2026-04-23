#!/usr/bin/env python3
"""
fetch_tri_history.py \u2014 build tri_history.json and tri_facilities.json
from the EPA Toxics Release Inventory (TRI) via Envirofacts.

Pulls annual chemical-level release quantities for every Delaware
facility that ever reported to TRI, then aggregates per facility per
year. Emits:

    tri_history.json
        { "TRIFID": { "1987": <lbs_on_off_site>, "1988": ..., ... }, ... }

    tri_facilities.json
        { "TRIFID": {
            "name":           "...",
            "city":           "...",
            "county":         "...",
            "lat":            39.803,
            "lon":            -75.438,
            "parent":         "...",
            "naics":          "325",
            "first_year":     1987,
            "last_year":      2023,
            "total_lbs":      1234567.89,   # sum across all years
            "top_chemicals":  [ {"name": "...", "lbs": ...}, ...top 5 ]
          }, ... }

Source
------
EPA Envirofacts `tri_form_r_ez` table:
    https://data.epa.gov/efservice/tri_form_r_ez/state_abbr/DE/reporting_year/<YYYY>/json
One row per (facility, chemical, year). We sum TOTAL_ON_OFF_SITE_RELEASE
across chemicals to produce the yearly headline number.

Usage
-----
    python3 scripts/fetch_tri_history.py
    python3 scripts/fetch_tri_history.py --years 2010-2023
    python3 scripts/fetch_tri_history.py --years 2022,2023 --dry-run
    python3 scripts/fetch_tri_history.py --start-year 2015

The Envirofacts API paginates with a `rows/start:end` path segment
(inclusive). We request up to 10 000 rows per year, which comfortably
covers any single-state single-year slice (DE tops out around ~500
chemical-level rows per year).

Requires: requests  (pip3 install requests)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests first")


OUT_HISTORY    = Path(__file__).parent.parent / "tri_history.json"
OUT_FACILITIES = Path(__file__).parent.parent / "tri_facilities.json"

BASE_ROOT = "https://data.epa.gov/efservice/tri_form_r_ez"
# Envirofacts v2: the format token ("JSON" / "CSV" / "XML") must come
# LAST in the path, after any rows/START:END range. Putting `/json/`
# earlier silently yields XML on this endpoint.


def build_base(state: str, county_fips: str | None) -> str:
    """Build the per-state (optionally county-scoped) base URL.

    With county scoping, the fetch is massively smaller \u2014 useful for
    PA/NJ where we only want the Delaware-River airshed counties, not
    the whole state. The Envirofacts column is `state_county_fips_code`
    (a 5-digit string like "42045"); `county_fips` alone does NOT exist
    on tri_form_r_ez and will 500 every request.
    """
    u = f"{BASE_ROOT}/state_abbr/{state.upper()}"
    if county_fips:
        u += f"/state_county_fips_code/{county_fips}"
    return u + "/reporting_year"

# TRI started in 1987. We stop at whatever the user's current system
# thinks is "last complete reporting year" by default (release N covers
# reporting year N-1, roughly); `--years` or `--start-year` can widen it.
DEFAULT_FIRST_YEAR = 1987
DEFAULT_LAST_YEAR  = datetime.now(timezone.utc).year - 1

# Fields we persist on the facility roster from the most recent row we
# see for that TRIFID. Envirofacts case drifts across endpoints (upper
# vs lower snake), so we lowercase every key on read.
FAC_FIELDS = [
    "tri_facility_id",
    "facility_name",
    "city_name",
    "county_name",
    "state_abbr",
    "zip_code",
    "latitude",
    "longitude",
    "standardized_parent_company",
    "parent_co_name",
    "primary_naics_code",
    "fac_closed_ind",
]


def parse_years(spec: str) -> list[int]:
    """Parse a --years value: '' | '2020,2022' | '2010-2023' \u2192 [int, ...]."""
    spec = (spec or "").strip()
    if not spec:
        return list(range(DEFAULT_FIRST_YEAR, DEFAULT_LAST_YEAR + 1))
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return sorted(out)


def fetch_year(year: int, base: str, page_size: int = 1_000,
               max_retries: int = 3, verbose: bool = False) -> list[dict]:
    """Fetch every TRI Form R row for *year* at the given base URL.

    Envirofacts paginates by path segment `rows/START:END` (inclusive
    0-based). Max page is 10 000 rows per call, but larger pages
    sometimes 500 or return HTML error pages, so default page is 1 000.
    If we somehow hit the ceiling we keep fetching subsequent pages
    until a short page ends the walk.
    """
    rows: list[dict] = []
    start = 0
    while True:
        end = start + page_size - 1
        url = f"{base}/{year}/rows/{start}:{end}/JSON"
        if verbose:
            print(f"    GET {url}")
        for attempt in range(max_retries):
            try:
                r = requests.get(url, timeout=180,
                                 headers={"Accept": "application/json",
                                          "User-Agent": "cc4ej-ci-map/1.0"})
                break
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"    {year}: request failed after {max_retries} tries: {e}")
                    return rows
                time.sleep(2 ** attempt)
        ct = (r.headers.get("content-type") or "").lower()
        if r.status_code == 404:
            # EPA returns 404 for years with zero records (e.g. future
            # years, or very early years for some states). Treat as empty.
            return rows
        if not r.ok:
            print(f"    {year}: HTTP {r.status_code} ({ct}) \u2014 {r.text[:240]!r}")
            return rows
        try:
            page = r.json()
        except ValueError:
            snippet = r.text[:400].replace("\n", " ")
            print(f"    {year}: non-JSON response; content-type={ct}; "
                  f"body[0:400]={snippet!r}")
            return rows
        # EPA sometimes returns a fault object like
        #   {"Error": {"Message": "..."}}
        # at top level. Detect and surface.
        if isinstance(page, dict):
            err = page.get("Error") or page.get("error") or page.get("fault")
            if err:
                print(f"    {year}: API error \u2014 {err}")
                return rows
            # Envirofacts sometimes wraps the list under a key like
            # "tri_form_r_ez" or "Results"; pull the first list value.
            for v in page.values():
                if isinstance(v, list):
                    page = v
                    break
            else:
                print(f"    {year}: unexpected dict response; keys={list(page)[:6]}")
                return rows
        if not page:
            break
        # Lowercase all keys once so downstream accessors don't care which
        # casing variant Envirofacts happens to return.
        rows.extend({k.lower(): v for k, v in row.items()} for row in page)
        if len(page) < page_size:
            break
        start += page_size
    return rows


def _num(v) -> float:
    """Envirofacts gives scientific strings like '0E-7' / '10.00000'; parse to float."""
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _load_existing(path: Path) -> dict:
    """Load a previously-written tri_history/tri_facilities JSON, or {}."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"  warning: existing {path.name} unreadable ({e}); starting fresh")
        return {}


def _rebuild_facility_summary(trifid: str, year_map: dict[str, float],
                              meta: dict,
                              chem_totals: dict[str, float]) -> dict:
    """Roll one TRIFID's year-map + chem-totals into the roster shape."""
    years_present = sorted(int(y) for y in year_map.keys())
    top_chems = sorted(chem_totals.items(), key=lambda kv: kv[1],
                       reverse=True)[:5]
    return {
        "name":          meta.get("facility_name"),
        "city":          meta.get("city_name"),
        "county":        meta.get("county_name"),
        "state":         meta.get("state_abbr"),
        "zip":           meta.get("zip_code"),
        "lat":           _num(meta.get("latitude")) or None,
        "lon":           _num(meta.get("longitude")) or None,
        "parent":        (meta.get("standardized_parent_company")
                          or meta.get("parent_co_name")),
        "naics":         meta.get("primary_naics_code"),
        "closed":        meta.get("fac_closed_ind") == "Y",
        "first_year":    years_present[0] if years_present else None,
        "last_year":     years_present[-1] if years_present else None,
        "total_lbs":     round(sum(year_map.values()), 2),
        "top_chemicals": [
            {"name": name, "lbs": round(lbs, 2)}
            for name, lbs in top_chems
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fetch EPA TRI annual release history; merges into existing JSON.")
    ap.add_argument("--state", default="DE",
                    help="Two-letter state (default DE). Repeat runs with "
                         "--state PA/NJ/etc to append cross-state data.")
    ap.add_argument("--counties", default="",
                    help="Comma-separated 5-digit county FIPS to scope within "
                         "the state (e.g. '42045,42101' for PA Delaware+Phila "
                         "counties). Default: entire state.")
    ap.add_argument("--years", default="",
                    help="Years to fetch; '2020,2023' or '2010-2023' "
                         "(default: 1987 through last completed calendar year)")
    ap.add_argument("--start-year", type=int, default=None,
                    help="Shortcut: fetch from this year through present")
    ap.add_argument("--dry-run", action="store_true",
                    help="Preview; do not write output JSON files")
    ap.add_argument("--sleep", type=float, default=0.25,
                    help="Seconds to sleep between per-year requests "
                         "(default 0.25, EPA rate limits are gentle)")
    ap.add_argument("--verbose", action="store_true",
                    help="Print every URL as it's fetched (debug)")
    ap.add_argument("--no-merge", action="store_true",
                    help="Overwrite the output JSON instead of merging into it")
    args = ap.parse_args()

    if args.start_year is not None and not args.years:
        years = list(range(args.start_year, DEFAULT_LAST_YEAR + 1))
    else:
        years = parse_years(args.years)

    counties = [c.strip() for c in args.counties.split(",") if c.strip()]
    scopes = [(args.state, c) for c in counties] or [(args.state, None)]
    scope_label = (f"{args.state} counties {counties}" if counties
                   else args.state)

    print(f"Fetching EPA TRI for {scope_label}: "
          f"{years[0]}\u2013{years[-1]} ({len(years)} years)")

    # Fresh accumulator for THIS run only \u2014 we'll merge with existing JSON at
    # write time so prior states/years don't get clobbered.
    releases: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    chem_by_fac: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    fac_meta: dict[str, dict] = {}
    fac_meta_year: dict[str, int] = {}

    total_rows = 0
    for state, county in scopes:
        base = build_base(state, county)
        scope_hdr = f"{state}" + (f" / county {county}" if county else "")
        print(f"\n==> {scope_hdr}")
        for year in years:
            t0 = time.time()
            rows = fetch_year(year, base, verbose=args.verbose)
            dt = time.time() - t0
            if not rows:
                print(f"  {year}: 0 rows ({dt:.1f}s)")
                continue
            total_rows += len(rows)
            trifids_this_year: set[str] = set()
            for row in rows:
                trifid = (row.get("tri_facility_id") or "").strip()
                if not trifid:
                    continue
                lbs = _num(row.get("total_on_off_site_release"))
                releases[trifid][year] += lbs
                chem = (row.get("cas_chem_name") or row.get("chem_name")
                        or row.get("generic_chem_name") or "Unknown")
                chem_by_fac[trifid][chem] += lbs
                if trifid not in fac_meta or year >= fac_meta_year.get(trifid, 0):
                    fac_meta[trifid] = {k: row.get(k) for k in FAC_FIELDS}
                    fac_meta_year[trifid] = year
                trifids_this_year.add(trifid)
            print(f"  {year}: {len(rows)} rows, {len(trifids_this_year)} facilities "
                  f"({dt:.1f}s)")
            if args.sleep:
                time.sleep(args.sleep)

    if not releases:
        sys.exit("no TRI data fetched \u2014 check --state/--counties/--years "
                 "and network reachability")

    # --- Merge phase -------------------------------------------------------
    merged_history: dict[str, dict[str, float]] = {}
    merged_fac:     dict[str, dict]              = {}
    merged_years:   set[int]                     = set()
    merged_states:  set[str]                     = set()

    if not args.no_merge:
        existing_hist = _load_existing(OUT_HISTORY)
        merged_history.update(existing_hist.get("facilities", {}) or {})
        merged_years.update(existing_hist.get("_meta", {}).get("years", []) or [])
        ex_states = existing_hist.get("_meta", {}).get("states")
        if ex_states:
            merged_states.update(ex_states)
        elif existing_hist.get("_meta", {}).get("state"):
            merged_states.add(existing_hist["_meta"]["state"])
        existing_fac = _load_existing(OUT_FACILITIES)
        merged_fac.update(existing_fac.get("facilities", {}) or {})

    merged_years.update(years)
    merged_states.add(args.state.upper())

    # For each TRIFID in THIS run, overlay new year totals onto whatever the
    # prior JSON held (new wins on same-year conflicts, which is safe since
    # a TRIFID is uniquely state-scoped).
    for trifid, year_map in releases.items():
        dst = merged_history.setdefault(trifid, {})
        for y, v in year_map.items():
            dst[str(y)] = round(v, 2)
        # Sort year keys after the merge for readability.
        merged_history[trifid] = {
            str(y): dst[str(y)] for y in sorted(int(k) for k in dst.keys())
        }

    # Rebuild the facility-roster row for every TRIFID we touched this run.
    # Two things we must not regress when the user re-runs for just an older
    # year (e.g. 1995-only retry for DE):
    #   (1) facility metadata \u2014 keep the most-recent row, not this run's
    #       row if this run fetched an older year;
    #   (2) top_chemicals \u2014 preserve prior lifetime top-5 and augment with
    #       this run's chemical totals (max-wins per chemical, since a prior
    #       top-5 entry is already a lifetime figure).
    for trifid in releases.keys():
        year_totals = merged_history.get(trifid, {})
        existing_row = merged_fac.get(trifid, {})
        meta = fac_meta.get(trifid, {})
        this_run_year = fac_meta_year.get(trifid, 0)
        existing_last = existing_row.get("last_year") or 0

        if meta and this_run_year >= existing_last:
            # This run has data at least as recent as the prior roster row;
            # use its Envirofacts-keyed metadata directly.
            combined_meta = dict(meta)
        else:
            # Prior roster row is more recent \u2014 promote it back to
            # Envirofacts field names so the rebuild helper sees a consistent
            # schema.
            combined_meta = {
                "facility_name":               existing_row.get("name"),
                "city_name":                   existing_row.get("city"),
                "county_name":                 existing_row.get("county"),
                "state_abbr":                  existing_row.get("state"),
                "zip_code":                    existing_row.get("zip"),
                "latitude":                    existing_row.get("lat"),
                "longitude":                   existing_row.get("lon"),
                "standardized_parent_company": existing_row.get("parent"),
                "parent_co_name":              None,
                "primary_naics_code":          existing_row.get("naics"),
                "fac_closed_ind":
                    "Y" if existing_row.get("closed") else None,
            }

        # Merge chemical totals: this-run's chem_by_fac + existing top-5.
        # Existing top-5 is a lifetime figure, so take max to avoid
        # regressing on partial refetch.
        combined_chems: dict[str, float] = dict(chem_by_fac[trifid])
        for item in existing_row.get("top_chemicals", []) or []:
            name = item.get("name")
            lbs = item.get("lbs") or 0
            if not name:
                continue
            try:
                combined_chems[name] = max(combined_chems.get(name, 0.0),
                                           float(lbs))
            except (TypeError, ValueError):
                pass

        merged_fac[trifid] = _rebuild_facility_summary(
            trifid, year_totals, combined_meta, combined_chems)

    payload_history = {
        "_meta": {
            "source":   "EPA Envirofacts tri_form_r_ez",
            "states":   sorted(merged_states),
            "field":    "TOTAL_ON_OFF_SITE_RELEASE (lbs/year, summed across chemicals)",
            "years":    sorted(merged_years),
            "retrieved_utc":
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "facilities": merged_history,
    }
    payload_facilities = {
        "_meta": {
            "source":   "EPA Envirofacts tri_form_r_ez + tri_facility",
            "states":   sorted(merged_states),
            "retrieved_utc":
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note":     "Facility metadata reflects the most recent TRI submission on file.",
        },
        "facilities": merged_fac,
    }

    fetched_years = sorted({y for t in releases for y in releases[t].keys()})
    print(f"\n  total rows fetched this run: {total_rows}")
    print(f"  facilities touched this run: {len(releases)}")
    print(f"  years with new data:         {len(fetched_years)}")
    print(f"  merged history size:         {len(merged_history)} facilities, "
          f"{len(merged_years)} years, states={sorted(merged_states)}")

    if args.dry_run:
        print("\nDRY RUN \u2014 top 5 (this run) by lifetime total:")
        top = sorted(((tid, merged_fac[tid]) for tid in releases),
                     key=lambda kv: kv[1]["total_lbs"] or 0,
                     reverse=True)[:5]
        for trifid, info in top:
            print(f"  {trifid:18s}  {info['total_lbs']:>14,.0f} lbs  "
                  f"{info['name']} ({info['city']}, {info['state']})")
        return

    with open(OUT_HISTORY, "w") as f:
        json.dump(payload_history, f, separators=(",", ":"))
    with open(OUT_FACILITIES, "w") as f:
        json.dump(payload_facilities, f, separators=(",", ":"))
    print(f"\nWrote {OUT_HISTORY.name} "
          f"({OUT_HISTORY.stat().st_size / 1024:.1f} KB)")
    print(f"Wrote {OUT_FACILITIES.name} "
          f"({OUT_FACILITIES.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
