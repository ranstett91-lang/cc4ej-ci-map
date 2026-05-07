"""
_cis_stats.py — shared math/stats helpers for the Facility Burden Index (CIS)
and its analysis scripts.

Factored out of audit_cis_sensitivity.py, analyze_cis_places.py,
patch_facility_weight_tier.py, and build_facility_weights.py to ensure all
CIS-related scripts use IDENTICAL implementations of:

  - haversine distance (mi)
  - polygon / multipolygon centroid (matching index.html geomCentroid)
  - rawProximityCIS (matching index.html implementation)
  - Spearman rank correlation (with documented degenerate-case behavior)

Why factor: a previous audit caught that the four scripts had three slightly
different copies of spearman_rho — two returned 1.0 and one returned 0.0 when
one axis was constant (degenerate case). A single helper module forces parity.

Degenerate-case convention:
  When all xs are equal OR all ys are equal, Spearman ρ is mathematically
  undefined (zero variance in one axis means rank-pair scatter has no
  meaningful direction). This module returns 0.0 — the conservative reading
  ("no association detectable in this sample"). Callers that want a different
  default should test the inputs themselves before calling.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence


# ── Geometry ─────────────────────────────────────────────────────────────

def haversine_mi(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance between two lat/lng points in miles. Earth radius = 3958.8 mi.

    Mirrors the 'haversineKm' function in index.html — that function is
    misnamed (it returns miles, see comment at index.html:9001) but the math
    is identical. Unit consistency is what matters: both production and
    audit code use the same convention so units cancel in any normalization.
    """
    r = 3958.8
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def polygon_centroid(coords: Sequence) -> tuple[float, float]:
    """Geometric mean of an outer-ring's vertices (lat, lng).

    NOT the area-weighted polygon centroid — this matches index.html's
    geomCentroid which also takes the simple vertex mean. For Delaware BG
    polygons this is a fine approximation; for highly irregular shapes the
    area-weighted centroid would shift somewhat.

    Skips the closing vertex (geojson rings repeat the first coord at the end).
    """
    ring = coords[0]
    n = len(ring) - 1
    sx = sum(p[0] for p in ring[:-1]) / n
    sy = sum(p[1] for p in ring[:-1]) / n
    return sy, sx  # lat, lng


def feature_centroid(geom: dict) -> tuple[float, float]:
    """Centroid of a Polygon or MultiPolygon geometry. For MultiPolygon picks
    the largest piece's centroid (rare in DE BGs; documented limitation)."""
    if geom["type"] == "Polygon":
        return polygon_centroid(geom["coordinates"])
    biggest = max(geom["coordinates"], key=lambda poly: len(poly[0]))
    return polygon_centroid(biggest)


# ── CIS math (replicates index.html rawProximityCIS) ─────────────────────

def raw_proximity_cis(
    lat: float,
    lng: float,
    facilities: Sequence[dict],
    decay: float = 1.5,
    min_mi: float = 0.15,
) -> float:
    """No-wind, no-year-filter CIS at a query point.

    Mirrors index.html's rawProximityCIS with windFromDeg=null and year=None.
    All facilities contribute regardless of `founded` year — caller filters
    upstream if a year-aware variant is needed.
    """
    score = 0.0
    for f in facilities:
        flat = f["geometry"]["coordinates"][1]
        flng = f["geometry"]["coordinates"][0]
        d = max(haversine_mi(lat, lng, flat, flng), min_mi)
        w = f["properties"].get("weight") or 1.0
        score += w / (d ** decay)
    return score


# ── Statistics ───────────────────────────────────────────────────────────

def _ranks(vals: Sequence[float]) -> list[float]:
    """Return ranks for vals using average-tied-ranks convention.

    Tied values share the average of the ranks they would have occupied.
    Ranks are 1-indexed (smallest value gets rank 1.0).
    """
    n = len(vals)
    order = sorted(range(n), key=lambda i: vals[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman_rho(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman rank correlation with average-tied ranks.

    Returns 0.0 when either axis has zero variance (degenerate case where the
    correlation is mathematically undefined). See module docstring for why
    0.0 is the chosen convention.

    Returns 1.0 only when xs and ys have identical rank-orders (or when n<2,
    which is also a trivial case).
    """
    n = len(xs)
    if n < 2:
        return 1.0
    if len(ys) != n:
        raise ValueError(f"spearman_rho: length mismatch ({n} vs {len(ys)})")
    rx = _ranks(xs)
    ry = _ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    denx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    deny = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    if denx == 0 or deny == 0:
        return 0.0
    return num / (denx * deny)


def bootstrap_percentile(values: Sequence[float], q: float) -> float:
    """Order-statistic percentile lookup matching numpy.percentile's
    `lower` interpolation method.

    For q ∈ [0, 1]: returns sorted_values[floor((n-1) * q)].

    Used by bootstrap CI computation. The previous inline implementation used
    `int(q * n)` which is off-by-one (selects the (n*q+1)-th sample for
    nontrivial n); this version is correct.
    """
    if not values:
        return float("nan")
    s = sorted(values)
    return s[max(0, min(len(s) - 1, int((len(s) - 1) * q)))]
