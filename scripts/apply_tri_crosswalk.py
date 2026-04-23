#!/usr/bin/env python3
"""
apply_tri_crosswalk.py \u2014 write `trifid` fields into facilities.json.

Reads `tri_crosswalk_suggestions.json` (from suggest_tri_crosswalk.py)
and adds a `trifid` property to each `facilities.json` feature whose
auto-suggestion clears BOTH a final_score and a name_score threshold.

Why two thresholds? final_score is a mix of name + proximity. A
warehouse sitting on a former-steel-mill parcel can score 0.6 purely on
proximity (same lat/lon as the real TRI reporter) while having no
meaningful name overlap \u2014 those are wrong matches and show up with a
low name_score. Requiring both filters them out.

Defaults are conservative. You can always run with --dry-run first,
scan the output, then re-run with --apply.

Usage
-----
    python3 scripts/apply_tri_crosswalk.py                  # dry-run preview
    python3 scripts/apply_tri_crosswalk.py --apply          # write facilities.json
    python3 scripts/apply_tri_crosswalk.py --apply \\
        --final 0.65 --name 0.40                            # loosen thresholds
    python3 scripts/apply_tri_crosswalk.py --apply \\
        --force-trifid "Pepsi Distribution Center=null"     # override specific ones

Pass `=null` to explicitly null out a match the auto-suggest got wrong.
Pass `="TRIFID"` to force a specific TRIFID onto a named feature.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
FAC  = ROOT / "facilities.json"
SUG  = ROOT / "tri_crosswalk_suggestions.json"

# Curated-facility `type` substrings that signal the site is NOT itself
# a TRI reporter, even if it sits on top of one. Lower-case comparison.
SKIP_TYPE_SUBSTRINGS = [
    "warehouse",
    "distribution",
    "refrigeration",
    "cold storage",
    "vacant",
    "mall",
    "retail",
    "commercial/industrial development",
    "commercial development",
    "residential",
    "neighborhood",
    "hospital",
    "airport",
    "rail station",
    "rail bridge",
    "rail yard",
    "bridge",
    "substation",
    "contaminated site",
    "contamination site",
    "cleanup",
    "redevelopment",
    "port of ",
    "highway",
]


def parse_overrides(pairs: list[str]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for p in pairs or []:
        if "=" not in p:
            sys.exit(f"bad --force-trifid value {p!r}; expected NAME=TRIFID or NAME=null")
        name, val = p.split("=", 1)
        val = val.strip()
        out[name.strip()] = None if val.lower() == "null" else val
    return out


def should_skip_type(ftype: str | None) -> str | None:
    if not ftype:
        return None
    t = ftype.lower()
    for sub in SKIP_TYPE_SUBSTRINGS:
        if sub in t:
            return sub
    return None


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Apply TRI crosswalk suggestions to facilities.json")
    ap.add_argument("--apply", action="store_true",
                    help="Write changes to facilities.json "
                         "(default: dry-run preview)")
    ap.add_argument("--final", type=float, default=0.65,
                    help="Minimum final_score to auto-apply (default 0.65)")
    ap.add_argument("--name", type=float, default=0.40,
                    help="Minimum name_score to auto-apply (default 0.40)")
    ap.add_argument("--force-trifid", action="append", metavar='NAME=TRIFID',
                    help="Override auto-suggestion for a named feature; "
                         "use NAME=null to clear. Repeatable.")
    args = ap.parse_args()

    if not FAC.exists():
        sys.exit(f"missing {FAC.name}")
    if not SUG.exists():
        sys.exit(f"missing {SUG.name} \u2014 run suggest_tri_crosswalk.py first")

    fac_data = json.loads(FAC.read_text())
    sug_data = json.loads(SUG.read_text())
    overrides = parse_overrides(args.force_trifid)

    # Name \u2192 suggestion (exact name match; facilities.json names are unique).
    sug_by_name = {s["facility_name"]: s for s in sug_data["suggestions"]}

    applied:    list[dict] = []
    skipped:    list[dict] = []
    overridden: list[dict] = []
    unchanged:  list[dict] = []

    for feat in fac_data.get("features", []):
        props = feat.get("properties", {}) or {}
        name  = props.get("name") or ""
        ftype = props.get("type") or ""
        cur   = props.get("trifid")
        s     = sug_by_name.get(name)

        if name in overrides:
            want = overrides[name]
            overridden.append({
                "name": name, "old": cur, "new": want,
                "reason": "manual override",
            })
            if want is None:
                props.pop("trifid", None)
            else:
                props["trifid"] = want
            continue

        if not s:
            unchanged.append({
                "name": name, "reason": "no suggestion record",
            })
            continue

        suggested = s.get("suggested_trifid")
        top = (s["candidates"][0] if s.get("candidates") else None)
        final_score = (top or {}).get("final_score") or 0.0
        name_score  = (top or {}).get("name_score")  or 0.0

        skip_hit = should_skip_type(ftype)
        passes_thresholds = (
            suggested is not None
            and final_score >= args.final
            and name_score  >= args.name
            and skip_hit is None
        )

        if passes_thresholds:
            if cur == suggested:
                unchanged.append({
                    "name": name, "trifid": cur,
                    "reason": "already present",
                })
                continue
            applied.append({
                "name": name, "trifid": suggested,
                "final": final_score, "name_score": name_score,
                "tri_name": (top or {}).get("name"),
            })
            props["trifid"] = suggested
            continue

        reason_parts: list[str] = []
        if suggested is None:
            reason_parts.append("no confident suggestion")
        if final_score < args.final:
            reason_parts.append(f"final={final_score:.2f}<{args.final}")
        if name_score < args.name:
            reason_parts.append(f"name={name_score:.2f}<{args.name}")
        if skip_hit is not None:
            reason_parts.append(f"type contains '{skip_hit}'")
        skipped.append({
            "name": name,
            "type": ftype,
            "suggested": suggested,
            "final": final_score,
            "name_score": name_score,
            "top_tri": (top or {}).get("name"),
            "reason": "; ".join(reason_parts) or "below thresholds",
        })

    # Reporting.
    print(f"\nAuto-apply thresholds: final\u2265{args.final}, name\u2265{args.name}, "
          f"type-skip if any of {len(SKIP_TYPE_SUBSTRINGS)} substrings match")
    print(f"  applied:    {len(applied)}")
    print(f"  overridden: {len(overridden)}")
    print(f"  skipped:    {len(skipped)} (review & hand-edit these)")
    print(f"  unchanged:  {len(unchanged)}")

    def _print_block(title: str, items: list[dict], fmt):
        if not items:
            return
        print(f"\n{title}")
        print("-" * len(title))
        for it in items:
            print(fmt(it))

    _print_block(
        "APPLIED (auto):",
        applied,
        lambda a: (f"  {a['name'][:60]:60s}  \u2192 {a['trifid']:16s}  "
                   f"(final={a['final']:.2f}, name={a['name_score']:.2f})  "
                   f"[{a['tri_name']}]"),
    )
    _print_block(
        "OVERRIDDEN (manual):",
        overridden,
        lambda o: f"  {o['name'][:60]:60s}  {o['old']} \u2192 {o['new']}",
    )
    _print_block(
        "SKIPPED \u2014 hand-edit facilities.json if you want to wire any of these:",
        skipped,
        lambda s: (f"  {s['name'][:60]:60s}  {s['reason']}"
                   + (f"\n     top candidate: {s['top_tri']} ({s['suggested']})"
                      if s.get('suggested') or s.get('top_tri') else "")),
    )

    if not args.apply:
        print("\n(dry-run \u2014 re-run with --apply to write facilities.json)")
        return

    if not (applied or overridden):
        print("\nnothing to write")
        return

    FAC.write_text(json.dumps(fac_data, indent=1))
    print(f"\nwrote {FAC.name} ({FAC.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
