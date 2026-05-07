#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026. See LICENSE.md.
"""fetch_noaa_wind_rose.py — build a 16-direction wind-rose histogram from
NOAA Integrated Surface Database (ISD) hourly observations at KILG
(Wilmington/New Castle Airport, DE).

Output
------
    noaa_wind_rose.json — {
        _meta: {
            station, station_id, lat, lon, years, retrieved_utc,
            n_observations, n_calm, n_missing,
            mean_speed_ms, calm_frequency
        },
        directions: [
            {bin: "N",     deg_center: 0,    deg_range: [-11.25, 11.25],
             frequency: 0.057, mean_speed_ms: 4.2, ...},
            ...16 entries...
        ]
    }

Methodology
-----------
ISD WND column has format "ddd,q,T,sssss,q" where:
  - ddd = wind direction, degrees from north (000-360, 999=missing)
  - q   = direction quality flag
  - T   = wind type code (C=calm, N=normal, V=variable, B=...)
  - sss = wind speed × 10, m/s (00000-09999, 9999=missing)
  - q   = speed quality flag

Calm observations (T=C, speed=0) are counted separately and reported as
calm_frequency. They do NOT contribute to direction bins (no direction
exists for calm wind).

Sixteen-direction binning matches conventional wind rose presentation:
N, NNE, NE, ENE, E, ESE, SE, SSE, S, SSW, SW, WSW, W, WNW, NW, NNW
each spanning 22.5° centered on its compass heading.

Why a wind rose vs the snapshot wind factor: chronic exposure depends on
how often wind blows FROM each direction over years, not on what's
happening right now. The CIS overlay can use this to weight facilities
that are upwind of a given location more heavily — and the multiplier
becomes a stable per-facility-per-point scalar instead of changing with
the live weather.

Usage
-----
    python3 scripts/fetch_noaa_wind_rose.py            # 2015-2024 (10y default)
    python3 scripts/fetch_noaa_wind_rose.py --years 2010-2024
    python3 scripts/fetch_noaa_wind_rose.py --dry-run  # parse, don't write
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "noaa_wind_rose.json"

STATION_ID = "72418013781"
STATION_NAME = "WILMINGTON NEW CASTLE CO AIRPORT, DE US"
STATION_CALL_SIGN = "KILG"
STATION_LAT = 39.67444
STATION_LON = -75.60566

# 16 compass directions, 22.5° per bin, centered on each heading.
COMPASS_LABELS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]
N_BINS = len(COMPASS_LABELS)
BIN_WIDTH_DEG = 360.0 / N_BINS  # 22.5


def isd_url(year: int) -> str:
    return (f"https://www.ncei.noaa.gov/data/global-hourly/access/"
            f"{year}/{STATION_ID}.csv")


def parse_wnd(field: str) -> tuple[float | None, float | None, str | None]:
    """Parse an ISD WND field. Returns (direction_deg, speed_ms, type_code).

    Returns (None, None, type) for missing direction or speed.
    """
    parts = field.split(",")
    if len(parts) < 5:
        return None, None, None
    try:
        ddd = int(parts[0])
        sss = int(parts[3])
    except (ValueError, IndexError):
        return None, None, None
    type_code = parts[2] if len(parts) > 2 else None
    direction = None if ddd == 999 else float(ddd)
    speed = None if sss == 9999 else sss / 10.0
    return direction, speed, type_code


def direction_bin(deg: float) -> int:
    """Map a 0-360° heading into one of N_BINS sectors. Bins are centered
    on each compass heading: bin 0 = N (337.5°-22.5°), bin 1 = NNE
    (11.25°-33.75°), wrapping around. Returns the bin index 0..N_BINS-1."""
    # Shift so that bin 0 (N) is centered on 0°.
    shifted = (deg + BIN_WIDTH_DEG / 2.0) % 360.0
    return int(shifted // BIN_WIDTH_DEG)


def fetch_year(year: int) -> bytes:
    req = Request(isd_url(year), headers={"User-Agent": "CC4EJ-WindRose/1.0"})
    with urlopen(req, timeout=120) as resp:
        return resp.read()


def parse_csv_streaming(data: bytes):
    """Yield (wnd_field,) for each row in an ISD CSV blob, skipping the
    header. We avoid the csv module because the file uses heavy quoting
    and we only need one column."""
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if not lines:
        return
    header = lines[0]
    cols = [c.strip().strip('"') for c in header.split(",")]
    try:
        wnd_idx = cols.index("WND")
    except ValueError:
        raise RuntimeError("ISD CSV missing WND column")

    import csv as _csv
    reader = _csv.reader(lines[1:])
    for row in reader:
        if len(row) > wnd_idx:
            yield row[wnd_idx]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2015-2024",
                    help="year range (inclusive), default 2015-2024")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if "-" in args.years:
        y_lo, y_hi = (int(x) for x in args.years.split("-", 1))
    else:
        y_lo = y_hi = int(args.years)
    years = list(range(y_lo, y_hi + 1))

    print(f"Fetching NOAA ISD for {STATION_CALL_SIGN} ({STATION_ID}), years {y_lo}-{y_hi}",
          file=sys.stderr)

    bin_counts = [0] * N_BINS
    bin_speed_sum = [0.0] * N_BINS
    n_obs = 0
    n_calm = 0
    n_missing = 0
    total_speed = 0.0

    for year in years:
        try:
            blob = fetch_year(year)
        except HTTPError as ex:
            print(f"  {year}: HTTP {ex.code} (skipping)", file=sys.stderr)
            continue
        rows_this_year = 0
        for wnd in parse_csv_streaming(blob):
            direction, speed, tc = parse_wnd(wnd)
            if direction is None and speed == 0.0:
                n_calm += 1
                rows_this_year += 1
                continue
            if direction is None or speed is None:
                n_missing += 1
                continue
            n_obs += 1
            total_speed += speed
            b = direction_bin(direction)
            bin_counts[b] += 1
            bin_speed_sum[b] += speed
            rows_this_year += 1
        print(f"  {year}: {rows_this_year:,} rows parsed", file=sys.stderr)

    if n_obs == 0:
        print("ERROR: no valid wind observations parsed", file=sys.stderr)
        return 1

    total_for_freq = n_obs + n_calm
    calm_frequency = n_calm / total_for_freq if total_for_freq > 0 else 0.0
    mean_speed = total_speed / n_obs if n_obs > 0 else 0.0

    directions = []
    for i, label in enumerate(COMPASS_LABELS):
        cnt = bin_counts[i]
        # Frequency normalized over directional observations only (excludes calm).
        # When applying the rose to CIS the calm fraction is handled via the
        # baseline (no-wind) weight; only directional observations modulate the
        # facility-specific multiplier.
        freq = cnt / n_obs if n_obs > 0 else 0.0
        mean_b_speed = (bin_speed_sum[i] / cnt) if cnt > 0 else 0.0
        center = (i * BIN_WIDTH_DEG) % 360.0
        lo = (center - BIN_WIDTH_DEG / 2.0) % 360.0
        hi = (center + BIN_WIDTH_DEG / 2.0) % 360.0
        directions.append({
            "bin": label,
            "deg_center": round(center, 2),
            "deg_range": [round(lo, 2), round(hi, 2)],
            "count": cnt,
            "frequency": round(freq, 5),
            "mean_speed_ms": round(mean_b_speed, 2),
        })

    # Sanity check: directional frequencies should sum to 1.0 (calm excluded).
    s = sum(d["frequency"] for d in directions)
    if abs(s - 1.0) > 0.005:
        print(f"WARNING: directional frequencies sum to {s:.5f} (expected ~1.0)",
              file=sys.stderr)

    payload = {
        "_meta": {
            "source": "NOAA Integrated Surface Database (ISD), hourly observations",
            "endpoint": "https://www.ncei.noaa.gov/data/global-hourly/access/{year}/" + STATION_ID + ".csv",
            "station": STATION_NAME,
            "station_id": STATION_ID,
            "call_sign": STATION_CALL_SIGN,
            "lat": STATION_LAT,
            "lon": STATION_LON,
            "years": years,
            "n_observations": n_obs,
            "n_calm": n_calm,
            "n_missing": n_missing,
            "calm_frequency": round(calm_frequency, 5),
            "mean_speed_ms": round(mean_speed, 2),
            "n_bins": N_BINS,
            "bin_width_deg": BIN_WIDTH_DEG,
            "convention": "Direction is FROM (meteorological convention). "
                          "Wind FROM 270° = westerly = blowing east.",
            "frequency_normalization": "Sum over directional bins = 1.0; "
                                       "calm fraction reported separately.",
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "directions": directions,
    }

    print()
    print(f"Total directional observations: {n_obs:,}")
    print(f"Calm observations: {n_calm:,} ({calm_frequency:.1%} of total)")
    print(f"Missing observations skipped: {n_missing:,}")
    print(f"Mean wind speed: {mean_speed:.2f} m/s")
    print()
    print("Wind rose (frequency from each direction):")
    for d in directions:
        bar = "█" * int(d["frequency"] * 200)
        print(f"  {d['bin']:>3s}  {d['frequency']*100:5.2f}%  "
              f"speed {d['mean_speed_ms']:.1f} m/s  {bar}")

    if args.dry_run:
        print("\nDry-run only. Re-run without --dry-run to write noaa_wind_rose.json.")
        return 0

    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"\nWrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
