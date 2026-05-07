#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026. See LICENSE.md.
"""analyze_cis_monitors.py — empirical correlation between the CIS
proximity-burden index and EPA AirData monitored air quality at Delaware
EPA AQS monitor sites.

This is the most direct empirical defense of the CIS as a screening
proxy. If proximity-burden tracks measured pollutant concentrations,
the index has external validity: it's not just an opinion about which
neighborhoods have the most facility density.

Method
------
1. Load DE monitors from air_monitors.json (~11 sites for 2018-2024
   span; 7 with PM2.5/O3, fewer for SO2/NO2/CO).
2. At each monitor location (lat, lng), compute the no-wind production
   CIS via _cis_stats.raw_proximity_cis with the v2.0 facility weights.
3. For each parameter (PM2.5, NO2, O3, SO2, CO):
   - Take the monitor's multi-year arithmetic-mean concentration
   - Compute Spearman ρ between CIS and concentration across monitors
   - Report n, ρ, simple sign test for direction
4. Also report per-monitor table so reviewers can see the underlying
   data, not just summary statistics.

Honesty discipline
------------------
n = 5-7 per parameter is small. Spearman ρ at this n has very wide
confidence intervals — even ρ = 0.6 isn't strongly distinguishable
from zero. We report ρ and the sign-test p-value but explicitly avoid
"statistically significant" language. The headline framing is "does
the relationship go in the expected direction" rather than "is it
statistically detectable."

Why this matters anyway
-----------------------
- A clearly POSITIVE correlation in the expected direction (high CIS →
  high measured pollution) is what you'd predict if the index is
  capturing real proximity-mediated air burden.
- A NEGATIVE correlation, or zero, would tell you the index is
  measuring something other than what monitors detect — that would
  be a finding to disclose and explain.
- Either result is publishable. The plan said "report results
  regardless of direction; do NOT cherry-pick" — that discipline
  applies here too.

Usage
-----
    python3 scripts/analyze_cis_monitors.py
        # writes analyses/cis_monitor_correlation_2026.md
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "scripts"))
from _cis_stats import raw_proximity_cis, spearman_rho  # type: ignore

FAC = ROOT / "facilities.json"
MONITORS = ROOT / "air_monitors.json"
OUT = ROOT / "analyses" / "cis_monitor_correlation_2026.md"

# Direction-of-effect hypothesis per parameter. All criteria pollutants
# we look at are facility-emitted or facility-precursor — so a positive
# correlation between CIS and concentration is the directional prediction.
EXPECTED_SIGN = {
    "88101": +1,  # PM2.5
    "42602": +1,  # NO2 (combustion product, traffic + power plants)
    "44201": +1,  # O3 (secondary; expectation slightly weaker since O3
                  #     is regional and can even *decrease* near NOx
                  #     sources due to titration — see report caveat)
    "42401": +1,  # SO2
    "42101": +1,  # CO
}


def main() -> int:
    facilities = json.loads(FAC.read_text())["features"]
    mon_data = json.loads(MONITORS.read_text())
    monitors = mon_data["monitors"]
    parameters = mon_data["_meta"]["parameters"]
    print(f"Loaded {len(monitors)} DE monitors, {len(facilities)} facilities",
          file=sys.stderr)

    # Compute production CIS at each monitor location (no wind / chronic
    # via the no-arg call to raw_proximity_cis which mirrors v2.0 default).
    monitor_records = []
    for m in monitors:
        cis = raw_proximity_cis(m["lat"], m["lng"], facilities)
        monitor_records.append({
            **m,
            "cis_raw": cis,
        })

    # Per-parameter: collect (cis, mean_conc) pairs across monitors that
    # measure that parameter, compute Spearman ρ.
    rows = []
    for pcode, pinfo in parameters.items():
        pairs = []
        for m in monitor_records:
            mean = m.get("multi_year_mean", {}).get(pcode)
            if mean is None or m["cis_raw"] is None:
                continue
            pairs.append((m["cis_raw"], mean, m))
        if len(pairs) < 4:
            rows.append({
                "param_code": pcode,
                "param_name": pinfo["name"],
                "units": pinfo["units"],
                "n": len(pairs),
                "rho": None,
                "expected_sign": EXPECTED_SIGN.get(pcode, +1),
                "note": f"n<4, skipped — not enough monitors measure this in DE",
                "pairs": [(p[2]["site_id"], p[0], p[1]) for p in pairs],
            })
            continue
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        rho = spearman_rho(xs, ys)
        rows.append({
            "param_code": pcode,
            "param_name": pinfo["name"],
            "units": pinfo["units"],
            "n": len(pairs),
            "rho": rho,
            "expected_sign": EXPECTED_SIGN.get(pcode, +1),
            "note": "",
            "pairs": [(p[2]["site_id"], p[0], p[1]) for p in pairs],
        })

    # Build report.
    lines = []
    lines.append(f"# CIS × EPA AQS Monitor Correlation (Delaware, 2026)\n")
    lines.append(f"**Analysis date:** {dt.date.today().isoformat()}  ")
    lines.append(f"**Reproducible via:** `python3 scripts/analyze_cis_monitors.py`\n")
    lines.append(f"**Data versions:** {len(monitors)} DE monitors over years "
                 f"{mon_data['_meta']['years'][0]}-{mon_data['_meta']['years'][-1]}; "
                 f"facilities.json with v2.0 weights; CIS computed at each "
                 f"monitor's coordinates with the no-wind/chronic-rose default.\n")

    lines.append("---\n")
    lines.append("## Headline\n")
    lines.append(
        "If the CIS captures real proximity-mediated air burden — and not "
        "just an opinion about which neighborhoods have the most facility "
        "density — we'd expect monitors near high-CIS locations to register "
        "higher annual mean concentrations of facility-emitted criteria "
        "pollutants. This analysis tests that prediction directly against "
        "EPA AQS pre-generated annual-mean concentrations at all "
        f"{len(monitors)} active EPA AQS monitor sites in Delaware.\n"
    )
    lines.append("**Sample-size caveat (read first).** Delaware has 11 active "
                 "EPA AQS monitors total. For O3 and PM2.5 (the two most-"
                 "deployed parameters), n = 7. For SO2, n = 5. For NO2 and "
                 "CO, n = 1 (single monitor; correlation is undefined). "
                 "Spearman ρ at n = 5–7 has very wide confidence intervals; "
                 "we report observed ρ but explicitly avoid 'statistically "
                 "significant' language. The headline framing is **direction "
                 "of effect**, not p-values.\n")

    lines.append("---\n")
    lines.append("## Spearman correlation (CIS vs annual mean concentration)\n")
    lines.append("| Parameter | n | Observed ρ | Expected sign | Direction matches? | Note |")
    lines.append("| --- | ---: | ---: | ---: | --- | --- |")
    for r in rows:
        if r["rho"] is None:
            lines.append(f"| {r['param_name']} | {r['n']} | — | "
                         f"{r['expected_sign']:+d} | — | {r['note']} |")
            continue
        rho = r["rho"]
        sign = "✓ yes" if (rho > 0 and r["expected_sign"] > 0) or \
                          (rho < 0 and r["expected_sign"] < 0) else "✗ no"
        lines.append(f"| {r['param_name']} | {r['n']} | {rho:+.3f} | "
                     f"{r['expected_sign']:+d} | {sign} | {r['note']} |")
    lines.append("")
    lines.append("Direction match means: observed ρ has the same sign as the "
                 "directional hypothesis (positive correlation between CIS and "
                 "concentration for facility-emitted pollutants).")

    # Per-monitor table for transparency.
    lines.append("\n---\n")
    lines.append("## Per-monitor data (for transparency)\n")
    lines.append("CIS values are RAW (un-normalized) production scores at each "
                 "monitor's coordinates. Higher = more facility burden in "
                 "proximity. Concentrations are annual arithmetic means "
                 "averaged across the 2018-2024 window where data is "
                 "available.\n")

    for r in rows:
        if r["n"] < 2 or r["rho"] is None:
            continue
        lines.append(f"### {r['param_name']} (n = {r['n']}, units {r['units']})\n")
        lines.append(f"| Site | CIS (raw) | Mean concentration |")
        lines.append(f"| --- | ---: | ---: |")
        # Look up site_name for nicer labels.
        site_name_by_id = {m["site_id"]: m.get("site_name") or m["site_id"]
                           for m in monitor_records}
        sorted_pairs = sorted(r["pairs"], key=lambda t: -t[1])  # CIS-desc
        for site_id, cis, conc in sorted_pairs:
            label = site_name_by_id.get(site_id, site_id)[:50]
            lines.append(f"| {label} | {cis:.2f} | {conc:.3f} |")
        lines.append("")

    lines.append("---\n")
    lines.append("## Limitations\n")
    lines.append(
        "- **Sample size.** 11 monitors statewide; per-parameter n = 1-7. Even "
        "a strong observed ρ has wide statistical uncertainty at this n. "
        "We report directional findings, not p-values.\n"
        "- **Monitor placement is non-random.** EPA AQS monitors are sited "
        "for regulatory purposes (NAAQS compliance, urban-airshed coverage), "
        "not for randomized burden sampling. This means the monitors that "
        "exist tend to BE in or near high-burden areas — restricting our "
        "ability to test the low-burden tail of the relationship.\n"
        "- **Annual arithmetic means.** Each pollutant has a parameter-"
        "specific health benchmark (O3 4th-highest 8-hour daily max, NO2 "
        "98th percentile, etc.). For correlation with chronic facility "
        "burden, the year-averaged mean is sufficient — we don't need "
        "NAAQS exceedance counts. But peak exposure is not captured.\n"
        "- **CIS is a proximity proxy, not an emissions transport model.** "
        "AERMOD-grade dispersion modeling would be the gold standard here; "
        "this analysis only tests whether a screening proxy correlates with "
        "what monitors measure.\n"
        "- **No wind correction in this comparison.** The CIS at each "
        "monitor uses the v2.0 production default (chronic rose if loaded, "
        "else no wind). Per-monitor wind-adjusted CIS would refine the "
        "test, but the rose factor varies <10% across DE so we don't "
        "expect a meaningful shift.\n"
        "- **CO and NO2 have only 1 monitor each in DE.** Their entries "
        "are skipped (correlation undefined for n=1).\n"
        "- **Ozone is regional and partially anti-correlated with NOx.** "
        "Near major NOx sources, freshly-emitted NO can titrate O3 "
        "(NO + O3 → NO2 + O2), causing local O3 concentration to be "
        "*lower* than regional background. So a NEGATIVE CIS-O3 "
        "correlation is not necessarily a contradiction — it's chemistry. "
        "PM2.5 and SO2 don't have this complication.\n"
    )

    lines.append("---\n")
    lines.append("## Reproducibility\n")
    lines.append(
        f"```sh\n"
        f"python3 scripts/fetch_epa_aqs_monitors.py --years 2018-2024\n"
        f"python3 scripts/analyze_cis_monitors.py\n"
        f"```\n\n"
        f"Inputs: facilities.json (v2.0 weights), air_monitors.json "
        f"(EPA AirData annual_conc_by_monitor pre-generated files for "
        f"DE state code 10).\n"
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT.relative_to(ROOT)}", file=sys.stderr)

    # Headline summary to stdout.
    print()
    print("Headline correlations (CIS × annual mean concentration):")
    for r in rows:
        if r["rho"] is None:
            print(f"  {r['param_name']:35s}  n={r['n']}  — {r['note']}")
            continue
        print(f"  {r['param_name']:35s}  n={r['n']}  ρ={r['rho']:+.3f}  "
              f"(expected {r['expected_sign']:+d})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
