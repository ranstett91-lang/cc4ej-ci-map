// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2024-2026 Claymont Coalition for Environmental Justice. See LICENSE.md.
//
// js/cis.js — pure-math implementation of the Facility Burden Index (CIS).
//
// Extracted from index.html in methodology v1.3 (Tier 4.2 of the roadmap)
// so that:
//   1. The math is in a single auditable file rather than buried inside
//      a 9000-line single-page app.
//   2. A Python parity test (scripts/test_cis_parity.py) can verify the
//      JS implementation produces identical scores to the Python reference
//      (scripts/_cis_stats.py) by spawning Node.js and comparing.
//   3. Future methodology bumps that change the math touch ONE file
//      that's covered by parity tests, not an inline definition that
//      could silently drift from the documented formula.
//
// Loading conventions:
//   - Browser:  <script src="js/cis.js?v=1"></script>  (loads BEFORE the
//               inline app code that calls these functions)
//   - Node:     const CIS = require('./js/cis.js')
//   - Both:     functions are exposed both on window/globalThis (browser)
//               AND via module.exports (Node).
//
// Parity contract:
//   Every function defined here MUST produce identical numeric output to
//   its Python counterpart in scripts/_cis_stats.py for the same inputs.
//   See scripts/test_cis_parity.py for the property-based verification.
//   When changing math here, update _cis_stats.py in the same commit.

(function (root) {
  'use strict';

  // ── Constants (mirror scripts/_cis_stats.py defaults) ────────────────────

  var CIS_DECAY = 1.5;     // distance decay exponent
  var CIS_MIN_MI = 0.15;   // ~240 m floor to prevent singularity near facilities

  // ── Geometry ─────────────────────────────────────────────────────────────

  // Great-circle distance in miles. Earth radius = 3958.8 mi. Returns 999
  // (a "very far" sentinel) when any coordinate is null/undefined/NaN —
  // mirrors the defensive guard from the previous inline haversineMi.
  // Without the sentinel, NaN inputs would produce NaN scores that silently
  // poison downstream sums. The Python counterpart is haversine_mi() in
  // _cis_stats.py.
  function haversineKm(lat1, lon1, lat2, lon2) {
    if (lat1 == null || lat2 == null || lon1 == null || lon2 == null
        || isNaN(lat1) || isNaN(lat2) || isNaN(lon1) || isNaN(lon2)) {
      return 999;
    }
    var r = 3958.8;
    var p1 = lat1 * Math.PI / 180;
    var p2 = lat2 * Math.PI / 180;
    var dp = (lat2 - lat1) * Math.PI / 180;
    var dl = (lon2 - lon1) * Math.PI / 180;
    var a = Math.sin(dp / 2) * Math.sin(dp / 2)
          + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
    return r * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  // Initial great-circle bearing from point 1 to point 2 (degrees clockwise from north).
  function bearingTo(lat1, lon1, lat2, lon2) {
    var phi1 = lat1 * Math.PI / 180;
    var phi2 = lat2 * Math.PI / 180;
    var dl = (lon2 - lon1) * Math.PI / 180;
    var y = Math.sin(dl) * Math.cos(phi2);
    var x = Math.cos(phi1) * Math.sin(phi2)
          - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dl);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  }

  // Smallest angular difference between two bearings (0–180°).
  function angleDiff(a, b) {
    return Math.abs(((a - b + 180 + 360) % 360) - 180);
  }

  // ── Wind factor ──────────────────────────────────────────────────────────

  // Frequency-weighted directional multiplier: 1 + 0.4 × Σ freq[d] × cos(Δ).
  // windRose is the parsed noaa_wind_rose.json or a similarly-shaped object
  // with a .directions array of {deg_center, frequency} entries. Returns 1.0
  // (no adjustment) if windRose is missing or malformed.
  function chronicWindFactor(bearingDeg, windRose) {
    if (!windRose || !windRose.directions) return 1.0;
    var s = 0;
    for (var i = 0; i < windRose.directions.length; i++) {
      var d = windRose.directions[i];
      var diff = angleDiff(bearingDeg, d.deg_center);
      s += d.frequency * Math.cos(diff * Math.PI / 180);
    }
    return 1.0 + 0.4 * s;
  }

  // ── Core CIS ─────────────────────────────────────────────────────────────

  // Compute the raw (un-normalized) Facility Burden Index at a query point.
  //
  // Wind factor (three modes, priority order):
  //   1. Snapshot (windFromDeg is a finite number)   — 1 ± 0.4 cos(Δ to live wind)
  //   2. Chronic  (windRose loaded, no snapshot)     — chronicWindFactor()
  //   3. Baseline (neither)                          — no directional adjustment
  //
  // `year` is optional. When provided, facilities with founded > year are
  // excluded; facilities missing `founded` are always included (null-safe).
  //
  // `category` (v1.3+) selects which weight to use:
  //   "combined"    — facility.properties.weight  (default; v1.0–v1.2 behavior)
  //   "cancer"      — facility.properties.weight_by_category.cancer
  //   "respiratory" — facility.properties.weight_by_category.respiratory
  //
  // For non-combined categories, facilities with null or zero weight in that
  // category are skipped entirely (they don't contribute to that surface).
  // Required for the multi-pollutant CIS variants where Superfund-only sites
  // and traffic corridors don't have per-chemical TRI data and so cannot be
  // attributed to cancer or respiratory drivers specifically.
  //
  // Args:
  //   lat, lng        — query lat/lon (degrees)
  //   year            — optional integer; null/undefined disables time filter
  //   facilities      — array of GeoJSON Feature objects (with
  //                     geometry.coordinates [lon, lat] and properties.weight)
  //   windFromDeg     — meteorological FROM direction in degrees (number) or
  //                     null/undefined for non-snapshot modes
  //   windRose        — parsed noaa_wind_rose.json object or null
  //   category        — "combined" (default), "cancer", or "respiratory"
  //
  // Returns: raw score (caller normalizes via normalizeCIS).
  function rawProximityCIS(lat, lng, year, facilities, windFromDeg, windRose, category) {
    if (!facilities || !facilities.length) return 0;
    var cat = category || "combined";
    var score = 0;
    var haveSnapshot = (typeof windFromDeg === 'number') && isFinite(windFromDeg);
    var useChronic = !haveSnapshot && !!windRose;
    for (var i = 0; i < facilities.length; i++) {
      var f = facilities[i];
      if (year != null && f.properties.founded != null && f.properties.founded > year) continue;
      var w;
      if (cat === "combined") {
        w = f.properties.weight;
      } else {
        var wbc = f.properties.weight_by_category;
        w = wbc && wbc[cat];
      }
      // Skip facilities that don't contribute to this category surface.
      if (w == null || w === 0) continue;
      var fLat = f.geometry.coordinates[1];
      var fLng = f.geometry.coordinates[0];
      var dist = Math.max(haversineKm(lat, lng, fLat, fLng), CIS_MIN_MI);
      if (haveSnapshot) {
        var diff = angleDiff(bearingTo(lat, lng, fLat, fLng), windFromDeg);
        w *= 1.0 + 0.4 * Math.cos(diff * Math.PI / 180);
      } else if (useChronic) {
        w *= chronicWindFactor(bearingTo(lat, lng, fLat, fLng), windRose);
      }
      score += w / Math.pow(dist, CIS_DECAY);
    }
    return score;
  }

  // Normalize a raw CIS to a 0–10 scale, capped at 10. cisP95 is the 95th
  // percentile of raw scores at BG centroids (precomputed once per page load).
  function normalizeCIS(raw, cisP95) {
    if (!cisP95) return 0;
    return Math.min(10, (raw / cisP95) * 10);
  }

  // Plain-language label for a normalized 0–10 score. Used in popups and
  // info-panel narrative.
  function cisInterpretation(score) {
    if (score < 1)   return 'Minimal — little or no detectable facility burden here.';
    if (score < 3)   return 'Low — limited industrial or traffic sources nearby.';
    if (score < 5)   return 'Moderate — several significant sources within a few miles.';
    if (score < 6.5) return 'Elevated — multiple major industrial sources within 1–2 miles.';
    if (score < 8)   return 'High — heavy industrial concentration in this area.';
    return             'Very High — extreme clustering of industrial sources at close range.';
  }

  // ── Public API ──────────────────────────────────────────────────────────

  var api = {
    CIS_DECAY: CIS_DECAY,
    CIS_MIN_MI: CIS_MIN_MI,
    haversineKm: haversineKm,
    bearingTo: bearingTo,
    angleDiff: angleDiff,
    chronicWindFactor: chronicWindFactor,
    rawProximityCIS: rawProximityCIS,
    normalizeCIS: normalizeCIS,
    cisInterpretation: cisInterpretation,
  };

  if (typeof module !== 'undefined' && module.exports) {
    // Node.js (used by scripts/test_cis_parity.py).
    module.exports = api;
  } else {
    // Browser: expose on the host so existing inline code keeps using bare
    // names like `haversineKm(...)` without a namespace change. Also expose
    // a CIS namespace for new code that prefers explicit qualification.
    root.CIS = api;
    root.haversineKm = haversineKm;
    root.bearingTo = bearingTo;
    root.angleDiff = angleDiff;
    root.chronicWindFactor = chronicWindFactor;
    root.rawProximityCIS = rawProximityCIS;
    root.normalizeCIS = normalizeCIS;
    root.cisInterpretation = cisInterpretation;
    root.CIS_DECAY = CIS_DECAY;
    root.CIS_MIN_MI = CIS_MIN_MI;
  }
})(typeof globalThis !== 'undefined'
    ? globalThis
    : (typeof self !== 'undefined' ? self : this));
