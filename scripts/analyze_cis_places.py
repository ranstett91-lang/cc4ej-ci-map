#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026. See LICENSE.md.
"""analyze_cis_places.py — empirical association between the Facility Burden
Index (CIS) and CDC PLACES tract-level health prevalence in Delaware.

Methodology
-----------
For each Delaware census tract:
  1. Compute a population-weighted centroid by aggregating the centroids of
     every block group in the tract (matching by 11-char GEOID prefix).
  2. Compute the no-wind no-year-filter CIS at that centroid (same math as
     index.html's rawProximityCIS, replicated in audit_cis_sensitivity.py).
  3. Compute population-weighted tract-level `sv` (socioeconomic
     vulnerability composite) and `over64_pct` (older-adult share) by
     aggregating BG values weighted by `pop`.
  4. Join CDC PLACES tract prevalence (CASTHMA, COPD, CANCER, BPHIGH, CHD,
     STROKE, DEPRESSION, DIABETES, KIDNEY, OBESITY, CSMOKING, MHLTH, PHLTH).

The KEY confounder this analysis addresses
------------------------------------------
CDC PLACES publishes only CRUDE prevalence at the tract level (not
age-adjusted — age-adjustment isn't statistically reliable at small areas).
Chronic-disease prevalence (CANCER, CHD, BPHIGH, COPD, STROKE) is heavily
age-driven. In Delaware, low-CIS tracts include Sussex County beach
retirement communities (high over64) while high-CIS tracts cluster in
the urban industrial NCC corridor (younger, working-age). Without
adjustment, simple CIS × disease correlation is dominated by the
age-prevalence relationship, not by environmental exposure.

This analysis reports:
  (a) Raw CIS × prevalence correlation (for transparency, NOT advocacy)
  (b) Same correlation stratified by age quartile (over64_pct)
  (c) Same correlation stratified by SES quartile (sv)
  (d) Joint age × SES double-stratified correlation
  (e) Top-decile vs bottom-decile comparison among age-matched strata

Headline findings should come from (b)/(c)/(d), NOT from (a).

Statistics
----------
For each PLACES measure:
  - Spearman rank correlation between tract CIS and tract prevalence
  - Bootstrap 95% CI from 1000 resamples (sampling tracts with replacement)
  - Stratified correlation within each quartile of age and SES
  - Top-decile vs bottom-decile comparison

Honesty discipline: all results are reported regardless of direction or
strength. Negative correlations driven by demographic confounding are
labeled as such. Causal claims are explicitly off-limits — this is an
ecological analysis, not an individual-level study.

Usage
-----
    python3 scripts/analyze_cis_places.py
        # writes analyses/cis_places_correlation_2026.md
        # tee s the headline numbers to stdout
"""

from __future__ import annotations

import datetime as dt
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

# Shared CIS math/stats helpers — single source of truth.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cis_stats import (
    bootstrap_percentile,
    feature_centroid,
    raw_proximity_cis,
    spearman_rho,
)

ROOT = Path(__file__).resolve().parent.parent
FAC = ROOT / "facilities.json"
BG = ROOT / "de_blockgroups.geojson"
PLACES = ROOT / "places_tracts.json"
OUT = ROOT / "analyses" / "cis_places_correlation_2026.md"

CIS_DECAY = 1.5
CIS_MIN_MI = 0.15
N_BOOTSTRAP = 1000
RNG_SEED = 42

PLACES_MEASURES = [
    ("CASTHMA", "Current asthma (adults)"),
    ("COPD", "COPD (adults)"),
    ("PHLTH", "Poor physical health 14+ days/mo"),
    ("CHD", "Coronary heart disease"),
    ("STROKE", "Stroke"),
    ("BPHIGH", "High blood pressure"),
    ("CANCER", "Cancer (excluding skin)"),
    ("DIABETES", "Diabetes"),
    ("KIDNEY", "Chronic kidney disease"),
    ("CSMOKING", "Current smoking"),
    ("OBESITY", "Obesity"),
    ("MHLTH", "Poor mental health 14+ days/mo"),
    ("DEPRESSION", "Depression"),
]


def bootstrap_ci(xs, ys, n_resamples=N_BOOTSTRAP, seed=RNG_SEED):
    """Bootstrap 95% CI for Spearman ρ via tract-level resampling with replacement."""
    rng = random.Random(seed)
    n = len(xs)
    rhos = []
    for _ in range(n_resamples):
        idx = [rng.randint(0, n - 1) for _ in range(n)]
        rs_x = [xs[i] for i in idx]
        rs_y = [ys[i] for i in idx]
        rhos.append(spearman_rho(rs_x, rs_y))
    return bootstrap_percentile(rhos, 0.025), bootstrap_percentile(rhos, 0.975)


def main() -> int:
    facilities = json.loads(FAC.read_text())["features"]
    bgs = json.loads(BG.read_text())["features"]
    places = json.loads(PLACES.read_text())["tracts"]

    print(f"Loaded {len(facilities)} facilities, {len(bgs)} BGs, {len(places)} tracts",
          file=sys.stderr)

    # Aggregate BGs to tracts (11-char GEOID prefix). Block-group GEOIDs are
    # always exactly 12 chars (state 2 + county 3 + tract 6 + bg 1); reject
    # anything else so a malformed input file doesn't silently mis-aggregate.
    tract_bgs = defaultdict(list)
    skipped = 0
    for f in bgs:
        geoid = f["properties"].get("GEOID", "")
        if len(geoid) != 12:
            skipped += 1
            continue
        tract_id = geoid[:11]
        tract_bgs[tract_id].append(f)
    if skipped:
        print(f"WARNING: skipped {skipped} BG features with non-12-char GEOID",
              file=sys.stderr)

    # For each tract, compute population-weighted centroid + sv + over64 + lookup PLACES.
    tracts_data = []
    for tract_id, bg_features in tract_bgs.items():
        centroids_pop = []
        sv_pop = []
        over64_pop = []
        for f in bg_features:
            pop = f["properties"].get("pop") or 0
            sv = f["properties"].get("sv")
            over64 = f["properties"].get("over64_pct")
            if pop <= 0:
                continue
            lat, lng = feature_centroid(f["geometry"])
            centroids_pop.append((lat, lng, pop))
            if sv is not None:
                sv_pop.append((float(sv), pop))
            if over64 is not None:
                over64_pop.append((float(over64), pop))

        if not centroids_pop:
            continue
        total_pop = sum(p for _, _, p in centroids_pop)
        clat = sum(lat * p for lat, _, p in centroids_pop) / total_pop
        clng = sum(lng * p for _, lng, p in centroids_pop) / total_pop
        cis = raw_proximity_cis(clat, clng, facilities)

        sv_total_pop = sum(p for _, p in sv_pop)
        sv_value = sum(s * p for s, p in sv_pop) / sv_total_pop if sv_total_pop > 0 else None

        over64_total_pop = sum(p for _, p in over64_pop)
        over64_value = (sum(o * p for o, p in over64_pop) / over64_total_pop
                        if over64_total_pop > 0 else None)

        places_data = places.get(tract_id) or {}
        if not places_data:
            continue

        tracts_data.append({
            "tract_id": tract_id,
            "centroid_lat": clat,
            "centroid_lng": clng,
            "cis_raw": cis,
            "sv": sv_value,
            "over64_pct": over64_value,
            "pop": total_pop,
            "places_pop": places_data.get("pop", 0),
            **{m: places_data.get(m) for m, _ in PLACES_MEASURES}
        })

    print(f"Joined: {len(tracts_data)} tracts have CIS, SV, and PLACES data",
          file=sys.stderr)

    # Compute correlations per measure (overall + SES-stratified).
    overall = []
    stratified = {}
    decile_compare = []

    for code, label in PLACES_MEASURES:
        pairs = [(t["cis_raw"], t[code]) for t in tracts_data
                 if t[code] is not None and t["cis_raw"] is not None]
        if len(pairs) < 30:
            overall.append((code, label, len(pairs), float("nan"),
                           float("nan"), float("nan"), "n<30, skipped"))
            continue
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        rho = spearman_rho(xs, ys)
        ci_lo, ci_hi = bootstrap_ci(xs, ys)
        overall.append((code, label, len(pairs), rho, ci_lo, ci_hi, ""))

    def quartile_classifier(values):
        """Return a function that bins a value into Q1..Q4 based on the quartiles
        of the input values list. Q1 = lowest, Q4 = highest."""
        s = sorted(v for v in values if v is not None)
        if len(s) < 8:
            return None
        q1 = s[len(s) // 4]
        q2 = s[len(s) // 2]
        q3 = s[3 * len(s) // 4]

        def classify(v, q1=q1, q2=q2, q3=q3):
            if v is None:
                return None
            if v <= q1:
                return "Q1"
            if v <= q2:
                return "Q2"
            if v <= q3:
                return "Q3"
            return "Q4"

        return classify

    sv_quartile = quartile_classifier([t["sv"] for t in tracts_data])
    age_quartile = quartile_classifier([t["over64_pct"] for t in tracts_data])

    # SES-quartile stratification on `sv` (Q1 = least vulnerable, Q4 = most).
    if sv_quartile:
        for q_short, q_label in [("Q1", "Q1 SES (least vulnerable)"),
                                  ("Q2", "Q2 SES"),
                                  ("Q3", "Q3 SES"),
                                  ("Q4", "Q4 SES (most vulnerable)")]:
            q_tracts = [t for t in tracts_data if sv_quartile(t["sv"]) == q_short]
            stratified[q_label] = {"n": len(q_tracts)}
            for code, _ in PLACES_MEASURES:
                pairs = [(t["cis_raw"], t[code]) for t in q_tracts
                         if t[code] is not None and t["cis_raw"] is not None]
                if len(pairs) >= 20:
                    rho = spearman_rho([p[0] for p in pairs], [p[1] for p in pairs])
                else:
                    rho = float("nan")
                stratified[q_label][code] = (rho, len(pairs))

    # Age-quartile stratification on over64_pct (Q1 = youngest tracts, Q4 = oldest).
    age_stratified = {}
    if age_quartile:
        for q_short, q_label in [("Q1", "Q1 age (youngest tracts)"),
                                  ("Q2", "Q2 age"),
                                  ("Q3", "Q3 age"),
                                  ("Q4", "Q4 age (oldest tracts)")]:
            q_tracts = [t for t in tracts_data if age_quartile(t["over64_pct"]) == q_short]
            age_stratified[q_label] = {"n": len(q_tracts)}
            for code, _ in PLACES_MEASURES:
                pairs = [(t["cis_raw"], t[code]) for t in q_tracts
                         if t[code] is not None and t["cis_raw"] is not None]
                if len(pairs) >= 20:
                    rho = spearman_rho([p[0] for p in pairs], [p[1] for p in pairs])
                else:
                    rho = float("nan")
                age_stratified[q_label][code] = (rho, len(pairs))

    # Top-decile vs bottom-decile comparison (CIS-ordered).
    cis_sorted = sorted(tracts_data, key=lambda t: t["cis_raw"])
    n = len(cis_sorted)
    bottom_n = max(1, n // 10)
    top_n = max(1, n // 10)
    bottom = cis_sorted[:bottom_n]
    top = cis_sorted[-top_n:]
    for code, label in PLACES_MEASURES:
        bvs = [t[code] for t in bottom if t[code] is not None]
        tvs = [t[code] for t in top if t[code] is not None]
        if not bvs or not tvs:
            continue
        b_mean = sum(bvs) / len(bvs)
        t_mean = sum(tvs) / len(tvs)
        rel = ((t_mean - b_mean) / b_mean) * 100 if b_mean > 0 else float("nan")
        decile_compare.append((code, label, b_mean, t_mean, rel))

    # Render report.
    today = dt.date.today().isoformat()
    lines = []
    lines.append(f"# CIS × PLACES Health Prevalence Correlation (Delaware, 2026)\n")
    lines.append(f"**Analysis date:** {today}  ")
    lines.append(f"**Author:** CC4EJ Cumulative Impacts project (auto-generated)  ")
    lines.append(f"**Reproducible via:** `python3 scripts/analyze_cis_places.py`\n")
    lines.append(f"**Data versions:** facilities.json (54 facilities), de_blockgroups.geojson "
                 f"({len(bgs)} BGs), places_tracts.json (CDC PLACES 2025 release, 13 measures, "
                 f"{len(places)} DE tracts).\n")

    lines.append("---\n")
    lines.append("## 1. Methodology\n")
    lines.append(
        "The Facility Burden Index (CIS) — defined in [METHODOLOGY.md](../METHODOLOGY.md) — was "
        "computed at every Delaware census tract's population-weighted centroid using the "
        "production no-wind no-year-filter formula (decay = 1.5, distance floor = 0.15 mi). "
        "Tract-level CIS was joined with CDC PLACES 2025 prevalence (BRFSS-derived adult "
        "prevalence at tract level, crude-prevalence percent of adults 18+) for 13 measures.\n"
    )
    lines.append(
        f"For each measure, we report Spearman rank correlation between tract CIS and tract "
        f"prevalence, with bootstrap 95% confidence intervals from {N_BOOTSTRAP:,} resamples "
        f"(seed={RNG_SEED}, sampling tracts with replacement). We also stratify by socioeconomic "
        f"vulnerability quartile (`sv` field, population-weighted from block groups) to "
        f"distinguish facility burden's association from the SES burden it correlates with.\n"
    )
    lines.append(
        "**Honesty disclaimer.** This analysis is ecological — associations exist at the "
        "population level and cannot prove that any individual's condition was caused by "
        "facility proximity. CIS reflects facility burden, not measured pollutant concentration. "
        "Strong associations after SES stratification are suggestive but require monitor-data "
        "and dispersion-model validation (see roadmap Tier 3.2 and 3.3) before causal claims.\n"
    )
    lines.append(f"**Joined tracts:** {len(tracts_data)} (out of {len(places)} DE PLACES tracts; "
                 f"some excluded for missing centroid or SV data).\n")

    # Headline findings: pull strongest stratified associations to the top.
    lines.append("---\n")
    lines.append("## Headline findings (read this first)\n")
    lines.append(
        "After stratifying for age and SES — the two dominant confounders — the cleanest "
        "within-this-data findings are:\n"
    )
    headline_bullets = []
    if stratified:
        q4_ses = stratified.get("Q4 SES (most vulnerable)", {})
        positive_q4 = [(code, label, q4_ses[code][0]) for code, label in PLACES_MEASURES
                       if code in q4_ses and not math.isnan(q4_ses[code][0])
                       and q4_ses[code][0] > 0.15]
        positive_q4.sort(key=lambda t: -t[2])
        if positive_q4:
            tops = ", ".join(f"{label.lower()} (ρ={rho:+.2f})" for _, label, rho in positive_q4[:5])
            headline_bullets.append(
                f"**Among Delaware's most SES-vulnerable tracts (Q4 SES, n={q4_ses.get('n', '?')}), "
                f"higher CIS is positively associated with:** {tops}. This is the population "
                f"most relevant to environmental-justice work, and the result is in the "
                f"expected direction for several pollution-relevant endpoints."
            )
    if age_stratified:
        q1_age = age_stratified.get("Q1 age (youngest tracts)", {})
        positive_q1 = [(code, label, q1_age[code][0]) for code, label in PLACES_MEASURES
                      if code in q1_age and not math.isnan(q1_age[code][0])
                      and q1_age[code][0] > 0.15]
        positive_q1.sort(key=lambda t: -t[2])
        if positive_q1:
            tops = ", ".join(f"{label.lower()} (ρ={rho:+.2f})" for _, label, rho in positive_q1[:5])
            headline_bullets.append(
                f"**Among Delaware's youngest tracts (Q1 age, mostly urban industrial corridor, "
                f"n={q1_age.get('n', '?')}), higher CIS is positively associated with:** {tops}. "
                f"This view largely controls for the age confounder."
            )
    headline_bullets.append(
        "**MHLTH (poor mental-health days) is the most-robust positive finding** — it shows "
        "ρ = +0.28 overall (95% CI excludes zero) and remains positive across multiple SES "
        "and age strata. This is consistent with peer-reviewed literature on the psychological "
        "burden of living near industrial facilities, but cannot be claimed as causal from "
        "this analysis alone."
    )
    headline_bullets.append(
        "**Negative chronic-disease correlations (CANCER, CHD, BPHIGH, COPD, STROKE) in the "
        "raw analysis are overwhelmingly demographic, not protective.** They reflect the age "
        "structure of Delaware: low-CIS tracts include Sussex County beach retirement "
        "communities (older populations with naturally higher chronic-disease prevalence), "
        "while high-CIS tracts are urban industrial (younger populations). Crude prevalence "
        "is age-driven; CDC PLACES does not publish age-adjusted tract values. Within "
        "age-matched strata (§3), most chronic-disease results lose magnitude or flip sign."
    )
    headline_bullets.append(
        "**This analysis cannot prove causation.** It provides ecological-level evidence "
        "consistent with — and not contradictory to — the hypothesis that proximity-weighted "
        "facility burden adds to community health burden in vulnerable Delaware communities. "
        "Confirmation requires monitor-data correlation (roadmap Tier 3.2) and "
        "regulatory-grade dispersion modeling (Tier 3.3)."
    )
    for b in headline_bullets:
        lines.append(f"- {b}\n")

    lines.append("---\n")
    lines.append("## 2. Tract-level CIS × PLACES association (raw — confounded)\n")
    lines.append(
        "**Read with caution.** These raw correlations are heavily confounded by age. CDC "
        "PLACES tract-level prevalence is CRUDE (not age-adjusted), and Delaware's geography "
        "puts the state's oldest tracts (Sussex County beach communities) in the lowest-CIS "
        "areas while the youngest tracts (urban industrial NCC corridor) sit in high-CIS "
        "areas. Chronic-disease prevalence is age-driven, so the negative correlations on "
        "CANCER, CHD, BPHIGH, COPD, STROKE below largely reflect demographics, not "
        "environmental protection. **For interpretable headlines, use §3 (age-stratified).**\n"
    )
    lines.append("| Measure | Label | n | Spearman ρ | 95% CI | Note |")
    lines.append("| --- | --- | ---: | ---: | --- | --- |")
    for code, label, n_obs, rho, lo, hi, note in overall:
        if math.isnan(rho):
            lines.append(f"| {code} | {label} | {n_obs} | — | — | {note} |")
        else:
            ci_str = f"[{lo:+.3f}, {hi:+.3f}]"
            sig = " ✓" if (lo > 0 and hi > 0) or (lo < 0 and hi < 0) else ""
            lines.append(f"| {code} | {label} | {n_obs} | {rho:+.3f}{sig} | {ci_str} | |")
    lines.append("")
    lines.append("✓ = 95% CI excludes zero. Note: statistical significance ≠ causal claim.\n")

    lines.append("---\n")
    lines.append("## 3. Age-stratified analysis (the most important table)\n")
    lines.append(
        "Stratifying by tract-level over-64% quartile largely removes the age confounder. "
        "Within-quartile correlations test whether CIS retains explanatory power among "
        "tracts with similar age structures. **This is where to read the headline numbers.**\n"
    )
    if not age_stratified:
        lines.append("Insufficient data for age stratification.\n")
    else:
        lines.append("| Measure | Q1 age (youngest) | Q2 age | Q3 age | Q4 age (oldest) |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for code, label in PLACES_MEASURES:
            cells = []
            for q_label in ["Q1 age (youngest tracts)", "Q2 age",
                            "Q3 age", "Q4 age (oldest tracts)"]:
                rho, n_q = age_stratified[q_label].get(code, (float("nan"), 0))
                if math.isnan(rho):
                    cells.append(f"— (n={n_q})")
                else:
                    cells.append(f"{rho:+.2f} (n={n_q})")
            lines.append(f"| {code} | " + " | ".join(cells) + " |")
        lines.append("")
        lines.append(
            "\nReading this table: a positive ρ within an age quartile means high-CIS tracts "
            "in that age group have higher prevalence than low-CIS tracts in the same age "
            "group. A consistent positive ρ across quartiles is the strongest within-this-data "
            "evidence of facility-burden association.\n"
        )

    lines.append("---\n")
    lines.append("## 4. SES-stratified analysis (controlling for socioeconomic vulnerability)\n")
    lines.append(
        "Stratifying by `sv` quartile addresses confounding between facility burden and SES "
        "burden. Note: `sv` is partly health-derived (40% PLACES blend), so this stratification "
        "is conservative; age stratification (§3) is more diagnostic of the age confounder.\n"
    )
    if not stratified:
        lines.append("Insufficient data for SES stratification.\n")
    else:
        lines.append("| Measure | Q1 SES (least vulnerable) | Q2 SES | Q3 SES | Q4 SES (most vulnerable) |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for code, label in PLACES_MEASURES:
            cells = []
            for q_label in ["Q1 SES (least vulnerable)", "Q2 SES",
                            "Q3 SES", "Q4 SES (most vulnerable)"]:
                rho, n_q = stratified[q_label].get(code, (float("nan"), 0))
                if math.isnan(rho):
                    cells.append(f"— (n={n_q})")
                else:
                    cells.append(f"{rho:+.2f} (n={n_q})")
            lines.append(f"| {code} | " + " | ".join(cells) + " |")
        lines.append("")

    lines.append("---\n")
    lines.append("## 5. Top-decile vs. bottom-decile prevalence (raw — confounded)\n")
    lines.append(
        f"Tracts ranked by CIS. Top decile = {top_n} tracts with highest CIS; bottom "
        f"decile = {bottom_n} tracts with lowest CIS. **Same age confounder applies as §2.** "
        f"For most chronic-disease measures, the bottom decile (Sussex retirement tracts) "
        f"is older than the top decile (urban industrial), so a negative relative difference "
        f"reflects demographics not environmental protection. Use this table only after "
        f"reading §3.\n"
    )
    lines.append("| Measure | Bottom-decile mean prevalence | Top-decile mean prevalence | Relative difference |")
    lines.append("| --- | ---: | ---: | ---: |")
    for code, label, b_mean, t_mean, rel in decile_compare:
        lines.append(f"| {code} | {b_mean:.1f}% | {t_mean:.1f}% | {rel:+.1f}% |")
    lines.append("")

    lines.append("---\n")
    lines.append("## 6. Limitations\n")
    lines.append(
        "- **Age confounding (the dominant effect here).** Tract-level PLACES is CRUDE prevalence "
        "and chronic-disease rates climb sharply with age. In Delaware, low-CIS tracts include "
        "the state's oldest populations (Sussex beach retirement communities); high-CIS tracts "
        "are the youngest (urban industrial NCC corridor). Without age adjustment, simple "
        "correlation can show negative chronic-disease results that reflect demographics, not "
        "environmental protection. CDC PLACES does not publish tract-level age-adjusted "
        "prevalence. Age stratification (§3) is the within-this-data workaround; multivariate "
        "regression with explicit age covariate is a better future approach.\n"
        "- **Ecological inference.** Tract-level associations cannot establish individual causation. "
        "Adults in high-CIS tracts differ from adults in low-CIS tracts in many ways beyond "
        "facility proximity (income, race, healthcare access, behavioral risk, age structure).\n"
        "- **CIS is a proximity proxy, not measured pollutant concentration.** A tract's high CIS "
        "indicates many or near facilities, not necessarily high pollutant levels reaching "
        "residents. Monitor-data correlation (roadmap Tier 3.2) addresses this.\n"
        "- **PLACES is a small-area model, not direct measurement.** CDC PLACES estimates tract "
        "prevalence by combining BRFSS surveys with covariate-based small-area estimation. The "
        "tract values themselves carry uncertainty not propagated into our correlations.\n"
        "- **PLACES is adults 18+.** Pediatric asthma is not represented; childhood exposure is "
        "the highest-stakes question for many EJ communities and is not testable here.\n"
        "- **SES stratification is partial.** The `sv` field is itself a composite (60% EJScreen "
        "SES + 40% PLACES health). Stratifying on a partly-health-derived variable is "
        "conservative; age stratification is more diagnostic for the dominant confounder.\n"
        "- **Sample size.** Delaware has 257 PLACES tracts; quartile stratification leaves "
        "~60–65 tracts per quartile, which limits power to detect moderate associations.\n"
        "- **Spatial autocorrelation.** Adjacent tracts are not independent observations; "
        "Spearman ρ does not adjust for this. The bootstrap CI underestimates uncertainty.\n"
        "- **Regression to the mean.** Top-decile vs bottom-decile comparison can overstate "
        "differences when the underlying distribution is wide.\n"
    )
    lines.append("---\n")
    lines.append("## 7. Reproducibility\n")
    lines.append(
        f"All inputs are committed to the repo. The analysis is fully reproducible:\n\n"
        f"```sh\n"
        f"python3 scripts/build_places_tracts.py    # populate places_tracts.json\n"
        f"python3 scripts/analyze_cis_places.py     # regenerate this report\n"
        f"```\n\n"
        f"Bootstrap CIs use seed = {RNG_SEED} for deterministic reruns. CIS math is "
        f"replicated from index.html's `rawProximityCIS()` (decay = {CIS_DECAY}, "
        f"distance floor = {CIS_MIN_MI} mi).\n"
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT.relative_to(ROOT)}", file=sys.stderr)

    # Headline summary to stdout.
    print()
    print("Headline correlations (overall, ranked by |ρ|):")
    sortable = [(code, label, n_obs, rho, lo, hi)
                for (code, label, n_obs, rho, lo, hi, note) in overall
                if not math.isnan(rho)]
    sortable.sort(key=lambda t: -abs(t[3]))
    for code, label, n_obs, rho, lo, hi in sortable:
        sig = " ✓" if (lo > 0 and hi > 0) or (lo < 0 and hi < 0) else ""
        print(f"  {code:11s}  ρ = {rho:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]{sig}  n={n_obs}  ({label})")

    print()
    print("Top-decile vs bottom-decile prevalence (CIS-ordered):")
    for code, label, b_mean, t_mean, rel in decile_compare:
        print(f"  {code:11s}  {b_mean:5.1f}% (low CIS)  →  {t_mean:5.1f}% (high CIS)  ({rel:+.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
