#!/usr/bin/env python3
"""
suggest_tri_crosswalk.py \u2014 propose TRIFID matches for facilities.json.

Reads:
    facilities.json       \u2014 curated 54-feature roster (GeoJSON, name + coords)
    tri_facilities.json   \u2014 166 DE TRI reporters (from fetch_tri_history.py)

Writes:
    tri_crosswalk_suggestions.json
        For each curated facility, up to 3 TRIFID candidates ranked by a
        weighted score of (name similarity, geographic proximity), plus a
        `suggested_trifid` which is the top pick when the score clears a
        confidence threshold.
    tri_crosswalk_review.txt
        Human-readable side-by-side that is faster to scan than JSON.

You (the human) review `tri_crosswalk_review.txt`, accept/override the
suggestions, and edit `facilities.json` to add a `trifid` field on the
features you want wired into the TRI history. Any feature without a
`trifid` simply won't get the release-history splash.

Usage:
    python3 scripts/suggest_tri_crosswalk.py
    python3 scripts/suggest_tri_crosswalk.py --max-distance-mi 3

Scoring
-------
  final_score  = 0.65 * name_score + 0.35 * proximity_score
  name_score   = best match across tokenised facility name vs TRI name,
                 ignoring common corporate suffixes and "formerly X" aliases
  proximity_score = 1 - min(distance_mi, max_dist) / max_dist
  suggested    = top candidate when final_score >= 0.55 AND distance <= max_dist

Historical facilities (pre-1987) and non-industrial sites (residential
areas, hospitals, airports) typically have no match \u2014 that is correct
output, not a bug.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).parent.parent
FAC_IN      = ROOT / "facilities.json"
TRI_IN      = ROOT / "tri_facilities.json"
OUT_JSON    = ROOT / "tri_crosswalk_suggestions.json"
OUT_TEXT    = ROOT / "tri_crosswalk_review.txt"

# Token-level stop terms / noise that shouldn't count toward name similarity.
STOP_TOKENS = {
    "inc", "llc", "corp", "corporation", "company", "co", "ltd", "lp", "lllp",
    "the", "and", "of", "at", "a", "an",
    "facility", "plant", "works", "mill", "site", "station", "refinery",
    "terminal", "complex", "center", "centre", "industries", "industrial",
}

CORP_SUFFIX_RE = re.compile(
    r"\b(inc|llc|corp(?:oration)?|company|co|ltd|lp|lllp|gp|plc|ag|sa|nv|bv)\b\.?",
    flags=re.I,
)


def clean_name(s: str) -> str:
    """Lowercase, strip punctuation/corp-suffixes, collapse whitespace."""
    s = (s or "").lower()
    # Drop content in parentheses (common home for "formerly X" etc.);
    # we'll use that text separately as an alias.
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\bformerly\b.*$", " ", s)
    s = CORP_SUFFIX_RE.sub(" ", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_aliases(s: str) -> list[str]:
    """Pull out parenthetical 'formerly X' / 'formerly Honeywell' aliases."""
    out: list[str] = []
    for m in re.finditer(r"\(([^)]*)\)", s or ""):
        inner = m.group(1)
        # Split 'formerly Honeywell / Allied Chemical' into both halves.
        inner = re.sub(r"\bformerly\b", " ", inner, flags=re.I)
        for piece in re.split(r"[/,;|]+", inner):
            cleaned = clean_name(piece)
            if cleaned:
                out.append(cleaned)
    for m in re.finditer(r"\bformerly\s+([^\u2014\-\(]+)", s or "", flags=re.I):
        cleaned = clean_name(m.group(1))
        if cleaned:
            out.append(cleaned)
    return out


def token_set(s: str) -> set[str]:
    return {t for t in clean_name(s).split() if t and t not in STOP_TOKENS}


def name_score(cur_name: str, tri_name: str) -> float:
    """Return 0..1. Max of sequence-ratio (smoothed) and Jaccard on tokens
    across the curated primary name AND any parenthetical aliases. This
    handles cases like "Solstice Advanced Materials (formerly Honeywell /
    Allied Chemical)" \u2192 TRI "HONEYWELL INTERNATIONAL INC - CLAYMONT".
    """
    names_to_try = [cur_name] + extract_aliases(cur_name)
    best = 0.0
    tri_clean = clean_name(tri_name)
    tri_tokens = token_set(tri_name)
    for n in names_to_try:
        nc = clean_name(n)
        if not nc or not tri_clean:
            continue
        seq = SequenceMatcher(None, nc, tri_clean).ratio()
        cur_tokens = token_set(n)
        jacc = 0.0
        if cur_tokens and tri_tokens:
            inter = cur_tokens & tri_tokens
            union = cur_tokens | tri_tokens
            jacc = len(inter) / len(union)
        # Bias a bit toward Jaccard so a single shared rare token
        # ("amtrak", "dupont") anchors the match more than raw edit distance.
        score = max(seq, 0.15 + 0.85 * jacc)
        if score > best:
            best = score
    return best


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.7613  # earth radius, miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Suggest TRIFID crosswalk for curated facilities.json")
    ap.add_argument("--max-distance-mi", type=float, default=5.0,
                    help="Ignore TRI facilities farther than this from "
                         "the curated coord (default 5 mi)")
    ap.add_argument("--top-k", type=int, default=3,
                    help="Candidates per facility to list (default 3)")
    ap.add_argument("--threshold", type=float, default=0.55,
                    help="Minimum final_score for `suggested_trifid` "
                         "(default 0.55)")
    args = ap.parse_args()

    if not FAC_IN.exists():
        sys.exit(f"missing {FAC_IN.name}")
    if not TRI_IN.exists():
        sys.exit(f"missing {TRI_IN.name} \u2014 run fetch_tri_history.py first")

    fac = json.loads(FAC_IN.read_text())
    tri = json.loads(TRI_IN.read_text())
    tri_facs = tri.get("facilities", tri)  # tolerate both shapes

    # Flatten TRI side into a list of dicts with numeric coords.
    tri_list: list[dict] = []
    for trifid, meta in tri_facs.items():
        lat = meta.get("lat")
        lon = meta.get("lon")
        if lat is None or lon is None:
            continue
        tri_list.append({
            "trifid":     trifid,
            "name":       meta.get("name") or "",
            "city":       meta.get("city") or "",
            "parent":     meta.get("parent") or "",
            "lat":        float(lat),
            "lon":        float(lon),
            "total_lbs":  meta.get("total_lbs") or 0,
            "first_year": meta.get("first_year"),
            "last_year":  meta.get("last_year"),
            "closed":     bool(meta.get("closed")),
        })

    max_dist = float(args.max_distance_mi)
    suggestions: list[dict] = []

    for feat in fac.get("features", []):
        props = feat.get("properties", {}) or {}
        geom  = feat.get("geometry", {}) or {}
        coords = geom.get("coordinates") or [None, None]
        lon, lat = coords[0], coords[1]
        cur_name = props.get("name") or ""
        # Skip non-industrial / clearly non-TRI categories entirely \u2014
        # their "match" would just be noise.
        if lat is None or lon is None:
            suggestions.append({
                "facility_name": cur_name,
                "facility_coords": None,
                "category": props.get("category"),
                "type": props.get("type"),
                "candidates": [],
                "suggested_trifid": None,
                "skip_reason": "no coordinates",
            })
            continue

        scored: list[dict] = []
        for tri_f in tri_list:
            dist = haversine_mi(lat, lon, tri_f["lat"], tri_f["lon"])
            if dist > max_dist:
                continue
            ns = name_score(cur_name, tri_f["name"])
            prox = max(0.0, 1.0 - (dist / max_dist))
            final = 0.65 * ns + 0.35 * prox
            scored.append({
                "trifid":      tri_f["trifid"],
                "name":        tri_f["name"],
                "city":        tri_f["city"],
                "distance_mi": round(dist, 2),
                "name_score":  round(ns, 3),
                "final_score": round(final, 3),
                "total_lbs":   tri_f["total_lbs"],
                "years":       f'{tri_f["first_year"]}\u2013{tri_f["last_year"]}'
                               if tri_f["first_year"] else None,
                "closed":      tri_f["closed"],
            })
        scored.sort(key=lambda d: d["final_score"], reverse=True)
        top = scored[: args.top_k]
        suggested = (top[0]["trifid"]
                     if top and top[0]["final_score"] >= args.threshold
                     else None)
        suggestions.append({
            "facility_name":    cur_name,
            "facility_coords":  [lon, lat],
            "category":         props.get("category"),
            "type":             props.get("type"),
            "founded":          props.get("founded"),
            "candidates":       top,
            "suggested_trifid": suggested,
        })

    out = {
        "_meta": {
            "source_facilities":      str(FAC_IN.name),
            "source_tri_facilities":  str(TRI_IN.name),
            "max_distance_mi":        max_dist,
            "score_threshold":        args.threshold,
            "note":                   "Review and paste suggested_trifid into "
                                      "each feature's properties in facilities.json.",
        },
        "suggestions": suggestions,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))

    # Human review text \u2014 one block per curated facility.
    lines: list[str] = []
    auto = 0
    for s in suggestions:
        header = f"{s['facility_name']}"
        if s.get("founded"):
            header += f"  (founded {s['founded']})"
        if s.get("type"):
            header += f"  \u2014 {s['type']}"
        lines.append(header)
        lines.append("-" * min(len(header), 100))
        if s.get("suggested_trifid"):
            auto += 1
            lines.append(f"  SUGGESTED: {s['suggested_trifid']}")
        elif s.get("skip_reason"):
            lines.append(f"  (skipped: {s['skip_reason']})")
        else:
            lines.append(f"  SUGGESTED: (no confident match)")
        if not s["candidates"]:
            lines.append("  (no TRI facility within the search radius)")
        for i, c in enumerate(s["candidates"], 1):
            closed_tag = "  [closed]" if c.get("closed") else ""
            lines.append(
                f"  {i}. {c['trifid']:16s}  score={c['final_score']:.2f}  "
                f"dist={c['distance_mi']:5.2f}mi  "
                f"lbs_lifetime={c['total_lbs']:>12,.0f}  "
                f"{c['years'] or '':9s}  {c['name']}{closed_tag}"
            )
        lines.append("")

    lines.insert(0, f"# TRI crosswalk review \u2014 {len(suggestions)} curated "
                    f"facilities, {auto} with automatic suggestions "
                    f"(score >= {args.threshold}).")
    lines.insert(1, "# Edit facilities.json: add a \"trifid\" property to each "
                    "feature you want wired to annual TRI release history.")
    lines.insert(2, "")
    OUT_TEXT.write_text("\n".join(lines))

    print(f"Wrote {OUT_JSON.name} ({OUT_JSON.stat().st_size / 1024:.1f} KB)")
    print(f"Wrote {OUT_TEXT.name} ({OUT_TEXT.stat().st_size / 1024:.1f} KB)")
    print(f"  {auto} / {len(suggestions)} curated facilities have an "
          f"automatic suggested_trifid at threshold {args.threshold}.")


if __name__ == "__main__":
    main()
