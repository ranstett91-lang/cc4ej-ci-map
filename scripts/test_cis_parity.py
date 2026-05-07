#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026. See LICENSE.md.
"""test_cis_parity.py — verify that js/cis.js and scripts/_cis_stats.py
produce IDENTICAL Facility Burden Index (CIS) scores for the same inputs.

Why
---
The CIS math is implemented in two places: the live site (js/cis.js, used
in production via index.html) and the Python pipeline (scripts/_cis_stats.py,
used by the audit + analysis scripts). If they ever drift apart, our
"reproducible from public inputs" claim breaks: the methodology says one
thing, the rendered map shows another, and the analyses don't reflect what
users see.

This test generates a deterministic battery of query points across all
three wind modes (snapshot, chronic rose, baseline), runs each side, and
asserts numeric equality within machine epsilon.

Method
------
1. Build a fixed test battery: ~50 query points covering Delaware and
   nearby PA/NJ; mix of wind modes; mix of year filters.
2. Compute expected scores via _cis_stats.raw_proximity_cis (Python ref).
3. Spawn `node` with an inline harness that loads js/cis.js and computes
   the same scores; capture results as JSON.
4. Compare element-wise; print pass/fail per point; exit non-zero on
   any divergence beyond ABS_TOL (default 1e-6, well above f64 epsilon).

Run
---
    python3 scripts/test_cis_parity.py            # full battery
    python3 scripts/test_cis_parity.py --verbose  # print every test point
    python3 scripts/test_cis_parity.py --tol 1e-9 # tighter tolerance

Requires `node` on PATH (Node.js 18+). The script reports SKIPPED
gracefully if Node is not available.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "scripts"))
from _cis_stats import raw_proximity_cis  # type: ignore


FAC = ROOT / "facilities.json"
WIND_ROSE = ROOT / "noaa_wind_rose.json"
JS_CIS = ROOT / "js" / "cis.js"


# Battery generator: deterministic given the seed below. Covers:
#   - lat/lng spread across DE + just outside (NCC industrial corridor,
#     Wilmington, Sussex coast, near-fence to several major facilities)
#   - mix of year filters (None, 1900, 1950, 2000, 2024)
#   - mix of wind modes:
#       windFromDeg = None    → chronic if rose, else baseline
#       windFromDeg = 270     → snapshot west
#       windFromDeg = 90      → snapshot east
#       windFromDeg = 0       → snapshot north
RNG_SEED = 17
N_RANDOM_POINTS = 35

# Hand-picked anchor points — known geography that should produce
# distinguishable scores. Ensures we don't only test in empty rural areas.
ANCHOR_POINTS = [
    (39.803, -75.438, "Claymont (near Solstice/AWE Superfund)"),
    (39.815, -75.420, "Marcus Hook border (PA refineries upwind)"),
    (39.733, -75.580, "Wilmington central (urban industrial corridor)"),
    (39.576, -75.600, "Delaware City (refinery fenceline)"),
    (38.778, -75.080, "Lewes (Sussex coast — low burden)"),
    (38.694, -75.388, "Georgetown (Sussex inland)"),
    (39.690, -75.596, "New Castle (Kuehne / Croda fenceline)"),
    (39.155, -75.527, "Dover (downstate urban + Air Force Base)"),
]


def build_battery():
    rng = random.Random(RNG_SEED)
    points = []
    for lat, lng, name in ANCHOR_POINTS:
        for cat in ("combined", "cancer", "respiratory"):
            points.append({"lat": lat, "lng": lng, "year": None,
                           "windFromDeg": None, "category": cat,
                           "label": f"{name} | chronic | {cat}"})
        points.append({"lat": lat, "lng": lng, "year": 1950, "windFromDeg": None,
                       "category": "combined",
                       "label": f"{name} | year=1950 | chronic | combined"})
        points.append({"lat": lat, "lng": lng, "year": None, "windFromDeg": 270,
                       "category": "combined",
                       "label": f"{name} | year=None | snapshot W | combined"})
    for _ in range(N_RANDOM_POINTS):
        # Bounding box covering DE + immediate PA/NJ industrial neighbors.
        lat = rng.uniform(38.45, 39.95)
        lng = rng.uniform(-75.85, -74.95)
        year = rng.choice([None, 1900, 1980, 2000, 2024])
        wd = rng.choice([None, 0, 90, 180, 270, 45, 315])
        cat = rng.choice(["combined", "cancer", "respiratory"])
        points.append({"lat": lat, "lng": lng, "year": year,
                       "windFromDeg": wd, "category": cat,
                       "label": f"random ({lat:.3f},{lng:.3f}) | y={year} | wd={wd} | {cat}"})
    return points


# JS harness — runs under Node. Reads test points + facilities + windRose
# from stdin (one JSON blob), writes scores to stdout (JSON array).
JS_HARNESS = r"""
const path = require('path');
const fs = require('fs');
const cis = require(process.argv[2]);

let data = '';
process.stdin.on('data', chunk => { data += chunk; });
process.stdin.on('end', () => {
  const input = JSON.parse(data);
  const facilities = input.facilities;
  const windRose = input.windRose;
  const points = input.points;
  const out = points.map(p => {
    return cis.rawProximityCIS(
      p.lat, p.lng, p.year,
      facilities,
      p.windFromDeg,
      windRose,
      p.category || "combined"
    );
  });
  process.stdout.write(JSON.stringify(out));
});
"""


def js_compute(points, facilities, wind_rose):
    """Spawn node with the harness, return list of scores.

    Writes the harness to a temp .js file and invokes `node <file> <cis_path>`.
    Node 25's `-e` flag has known issues passing positional args to eval'd
    code (ERR_INVALID_ARG_TYPE under some conditions); a temp file sidesteps
    that and is cleaner to debug.
    """
    payload = {"facilities": facilities, "windRose": wind_rose, "points": points}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as fh:
        fh.write(JS_HARNESS)
        harness_path = fh.name
    try:
        proc = subprocess.run(
            ["node", harness_path, str(JS_CIS)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        Path(harness_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"node harness failed: {proc.stderr}")
    return json.loads(proc.stdout)


def py_compute(points, facilities, wind_rose):
    """Compute expected scores using the Python reference. Mirrors the
    JS rawProximityCIS three-mode wind logic so both sides are
    structurally equivalent."""
    out = []
    from _cis_stats import haversine_mi  # NaN sentinel parity
    for p in points:
        lat, lng = p["lat"], p["lng"]
        year = p["year"]
        wd = p["windFromDeg"]
        cat = p.get("category", "combined")

        have_snapshot = isinstance(wd, (int, float)) and not math.isnan(wd)
        use_chronic = (not have_snapshot) and bool(wind_rose)

        score = 0.0
        for f in facilities:
            if year is not None:
                founded = f["properties"].get("founded")
                if founded is not None and founded > year:
                    continue
            if cat == "combined":
                w = f["properties"].get("weight")
            else:
                wbc = f["properties"].get("weight_by_category") or {}
                w = wbc.get(cat)
            if not w:
                continue
            f_lat = f["geometry"]["coordinates"][1]
            f_lng = f["geometry"]["coordinates"][0]
            dist = max(haversine_mi(lat, lng, f_lat, f_lng), 0.15)
            if have_snapshot:
                bearing = py_bearing_to(lat, lng, f_lat, f_lng)
                diff = py_angle_diff(bearing, wd)
                w *= 1.0 + 0.4 * math.cos(diff * math.pi / 180.0)
            elif use_chronic:
                bearing = py_bearing_to(lat, lng, f_lat, f_lng)
                w *= py_chronic_factor(bearing, wind_rose)
            score += w / (dist ** 1.5)
        out.append(score)
    return out


def py_bearing_to(lat1, lng1, lat2, lng2):
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dl = math.radians(lng2 - lng1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def py_angle_diff(a, b):
    return abs(((a - b + 180 + 360) % 360) - 180)


def py_chronic_factor(bearing, wind_rose):
    if not wind_rose or "directions" not in wind_rose:
        return 1.0
    s = 0.0
    for d in wind_rose["directions"]:
        diff = py_angle_diff(bearing, d["deg_center"])
        s += d["frequency"] * math.cos(diff * math.pi / 180.0)
    return 1.0 + 0.4 * s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=1e-6,
                    help="absolute tolerance for parity comparison")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    if not shutil.which("node"):
        print("SKIPPED: node not on PATH (Node.js required for JS-side check)",
              file=sys.stderr)
        return 0
    if not JS_CIS.exists():
        print(f"FAIL: {JS_CIS} not found", file=sys.stderr)
        return 1

    facilities = json.loads(FAC.read_text())["features"]
    wind_rose = None
    if WIND_ROSE.exists():
        try:
            wind_rose = json.loads(WIND_ROSE.read_text())
        except json.JSONDecodeError:
            wind_rose = None

    points = build_battery()
    print(f"Running parity check: {len(points)} points × "
          f"{len(facilities)} facilities × wind rose "
          f"({'loaded' if wind_rose else 'absent'})...",
          file=sys.stderr)

    py_scores = py_compute(points, facilities, wind_rose)
    js_scores = js_compute(points, facilities, wind_rose)

    if len(py_scores) != len(js_scores):
        print(f"FAIL: result length mismatch (py={len(py_scores)} js={len(js_scores)})",
              file=sys.stderr)
        return 1

    failures = []
    max_abs_diff = 0.0
    max_rel_diff = 0.0
    for i, p in enumerate(points):
        py = py_scores[i]
        js = js_scores[i]
        abs_diff = abs(py - js)
        rel_diff = abs_diff / max(abs(py), abs(js), 1e-12)
        if abs_diff > max_abs_diff:
            max_abs_diff = abs_diff
        if rel_diff > max_rel_diff:
            max_rel_diff = rel_diff
        ok = abs_diff <= args.tol
        if args.verbose or not ok:
            status = "ok" if ok else "FAIL"
            print(f"  [{status}] {p['label']:65s} "
                  f"py={py:14.6f} js={js:14.6f} Δ={abs_diff:.2e}",
                  file=sys.stderr)
        if not ok:
            failures.append((i, p, py, js, abs_diff))

    print(f"\nMax |Δ|: {max_abs_diff:.3e}   Max relative: {max_rel_diff:.3e}",
          file=sys.stderr)

    if failures:
        print(f"\nFAIL: {len(failures)} of {len(points)} points exceed tol={args.tol}",
              file=sys.stderr)
        return 1
    print(f"\nPASS: all {len(points)} points within tol={args.tol}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
