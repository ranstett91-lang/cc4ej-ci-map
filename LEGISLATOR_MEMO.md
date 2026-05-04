# MEMO

**To:** [Legislator]
**From:** Chief of Staff
**Re:** Office position on CC4EJ Delaware Cumulative Impacts Map (cc4ej.org)
**Date:** 2026-05-03
**Length:** 2 pages

---

## 1. Recommendation

**CITE WITH CAVEATS.** This tool is methodologically sound, the data passes spot-checks against the federal source, and EPA's interactive EJScreen was discontinued Feb 5, 2025 — meaning this is now the only interactive way for Delawareans to look up their neighborhood's cumulative pollution-and-vulnerability picture. The fixes we'd require before linking it from the office newsletter are small and named below.

## 2. Why (3 bullets)

- **It checks out.** All three random spot-checks against the federal CDC PLACES API matched **exactly** — not within 10%, exactly to the decimal.
- **It admits what it can't do.** A "Known limitations" section is right in the methodology modal. That's the opposite of vapor.
- **It has one visible loose thread** (a "pending" data section that's been pending six months) and **two pieces of contested vocabulary** ("cumulative" and "environmental justice") that we'd want softened before we attach our name.

## 3. Hearing line we could use today

> "Independent verification of the Delaware Cumulative Impacts Map shows the adult-asthma data the tool publishes for Claymont — 10.2 percent — is identical to the figure the CDC's BRFSS survey reports for that same census tract. When constituents ask whether the data is real, the answer is: yes, this is the federal data, made local."
>
> Source links: [CC4EJ map](https://cc4ej.org/) · [CDC PLACES BRFSS 2023, tract 10003010300](https://chronicdata.cdc.gov/resource/cwsq-ngmh.json?$where=stateabbr%3D%27DE%27%20AND%20measureid%3D%27CASTHMA%27%20AND%20locationname%3D%2710003010300%27)

## 4. Constituent reply we could send today

> Hi Mrs. Johnson — thanks for reaching out about pollution near your home on Naamans Road. The Delaware Cumulative Impacts Map at cc4ej.org lets you type your address and see your neighborhood's score for pollution, health risk, and the factories nearby. The numbers come from EPA, the CDC, and the U.S. Census. If you'd like our office to walk through the report with you, please reply to this email and we'll set up a call.
>
> Map link: https://cc4ej.org/

## 5. What the opposition would attack — and our response

| # | Attack | Pre-built response |
|---|--------|---------------------|
| 1 | **"This is an advocacy tool, not a data source."** Built by an environmental-justice nonprofit. Will frame it as activist scoring. | Underlying data is 100 percent federal/state public datasets (EPA EJScreen 2024, CDC PLACES, US Census ACS, NOAA, DelDOT). The methodology modal documents every formula. Independent spot-check matches CDC raw data to the decimal. Same data, different interface. |
| 2 | **"Cumulative-impacts framing is contested."** "Cumulative impacts" and "environmental justice" code as policy stances some chambers reject. | The math is industry-neutral: pollution burden × vulnerability. Same approach EPA uses internally. Our office can describe the tool as a "neighborhood pollution and health-risk lookup" without invoking either contested phrase, while leaving the underlying data intact. |
| 3 | **"At-risk populations section is empty — what else is missing?"** Currently shows 12 "pending" rows on every panel. A hostile reviewer will screenshot this. | Already named in our request list (item 1 below). The maintainer has the build pipeline ready; the gap is in transcribing one PDF table from the American Lung Association's 2025 State of the Air report into a CSV. We can offer to fund or assign the transcription if needed. |

## 6. Constituent reach assessment

**WEAK.** A constituent with limited time, low patience, or low technical literacy can complete one useful interaction (search address → see scores → read the plain-English summary) — but they have to push past 21 tappable controls visible on first load and several jargon walls. The maintainer has already shipped a substantial mobile-usability fix (touch targets, hash-state sync, welcome-card reposition) but the surface still over-presents to a phone user. **Single biggest blocker:** decision overload on first paint. (See Appendix A for the underlying audit.)

For our recommendation purposes: this works for staff use today, works for engaged constituents today, and will work for the average constituent after the maintainer ships the visibility-progressive-disclosure fix described in item 4 below.

## 7. Methodology assessment

**PASS.**
- **Source attribution:** Methods modal lists EPA EJScreen 2016–2024, US Census Decennial + ACS 5-year, CDC PLACES, CDC EPHT, NOAA SLR, DelDOT EFA, EPA RMP/PHMSA/NRC. Direct download link to raw block-group scores as CSV. ✓
- **Methodology TL;DR:** Six expandable sections in plain-ish English: Data sources, How EB is scored, How SV is scored, Combined Burden + overburdened threshold, Post-2025 projections + assumptions, Known limitations. ✓
- **Data freshness disclosed:** "Showing 2024 data (nearest available to 2026)" pill on every panel. ✓
- **Cross-source contradiction test:** 3 of 3 BGs (Claymont, Wilmington, Lewes) match CDC PLACES BRFSS 2023 adult-asthma values **exactly** (10.2% / 13.3% / 10.6% — no rounding error). ✓ See Appendix B.
- **Reproducibility:** Methodology shows the burden formula, the vulnerability formula, the combined-burden formula. CSV download provided. An independent analyst could replicate. ✓
- **Honest about gaps:** "Known limitations" section explicitly acknowledged. The "At-risk populations pending" section is the one place this honesty principle slipped — see fix request #1. ⚠

## 8. Specific fixes the office would request before citing

In order of impact-to-fix ratio, lowest cost first:

1. **Fill or hide the "At-risk populations" section.** All 12 rows have shown "pending —" since at least 2026-04-23. Either transcribe the ALA SOTA 2025 county tables into `scripts/sota_de_2025.csv` and re-run the build script, or hide the section until at least one row has data. Reads as broken loader; opposition will screenshot. (P0)

2. **Fix the over-65 demographic build for 2024.** Statewide, 26 BGs report `over64_pct ≥ 60%` in 2024 (vs. 17 in 2023), and one Sussex BG (`100050512043`) reports literally 100% over 64 — mathematically impossible. Single Claymont BG (`100030101063`) jumped from 66.9% in 2023 to 87% in 2024. Likely a build-script bug in `scripts/build_acs5_history.py`. Will be caught by any opposition demographer. (P0)

3. **Replace "RCP 4.5 / 8.5" labels** with "Best case (current commitments)" and "Worst case (no further action)" — keep the RCP code as a footnote subtitle. Industry counsel will use the RCP labels to claim the tool assumes "worst-case alarmism." Plain labels neutralize the attack. (P1)

4. **Progressive disclosure on first load.** Hide weather widgets, CIS toggle, time-bar, and Layers tab behind a "Show map controls" toggle by default. First load = welcome card + map + search. This is the single biggest constituent-reach fix; affects the recommendation we can make to the average district email subscriber. (P1)

5. **Soften two contested terms in user-facing copy.** Tagline "Delaware Cumulative Impacts Map" → "Delaware Pollution and Health-Risk Map" (keep "Cumulative Impacts" as the technical name in the methodology modal). Welcome-card line "cumulative environmental risk" → "pollution and health risk." This survives a hostile committee question without weakening the underlying analysis. (P1)

6. **Add a footnote-source link next to every score.** Currently the source is in the methodology modal three taps away. Adding a small "ⓘ source" tap-affordance next to each score would let our staffer cite the federal source from the panel itself in 1 click instead of 3. (P2)

7. **Add trust signals to the footer.** Funder/partner names, contact email, last-updated date, version. Currently absent on the map page. Lets the office's communications team verify quickly when a constituent asks "who built this?" (P2)

8. **Methods modal TL;DR.** Add a 1-sentence summary at the top of the modal: "Where the numbers come from. EPA, CDC, Census, NOAA, DelDOT. Tap any section to see the formula and the original source." Currently opens directly into dense detail. (P2)

## 9. Trust gaps (≤ 5)

1. **At-risk populations section showing 12 "pending" rows.** Six months stale. Reads as a loader that never fires. (P0 — addressed in fix #1)
2. **Over-65 demographic anomaly in 2024 build.** 100% over-64 in one BG; multiple BGs jumped 20+ points YoY. Will be caught by any reviewer who checks. (P0 — addressed in fix #2)
3. **No funder / partner / version / contact on the map page.** Constituent or journalist can't find a human in two clicks. (P2 — addressed in fix #7)
4. **`cancer_pct = 0` in 351 of 700 BGs (50% of state).** Likely real EJScreen behavior (NATA cancer-risk has thresholds), but we should confirm with EPA before citing this layer. Footnote needed: "no data below screening threshold" vs. "0 risk." (Watch — needs internal verification, not necessarily a fix.)
5. **Mapbox tile-cache offline behavior partial.** App data + recently-visited tiles cache for offline; tiles outside the visited area do not. Constituents in poor-signal areas may see app-shell-without-basemap. Acceptable but worth disclosing in any "use offline" guidance. (Nit)

## 10. Appendices

### Appendix A — Driver-persona findings (10th-grader, severe ADHD)

Source: [ADHD_AUDIT.md](ADHD_AUDIT.md). Top 6 ranked by impact:

| # | Finding | Severity | One-line |
|---|---|---|---|
| 1 | First-load decision overload | P0 | 21 tappable items in viewport on cold load; persona ceiling is 5–8. |
| 2 | At-risk populations 12 "pending" rows | P0 | Reads as broken loader; trust collapse on first panel open. |
| 3 | Jargon barrier ("cumulative", "block group", "vulnerability", "percentile", "RCP", "above median") | P0 | A 10th grader will not Google any of these. Closes the tab. |
| 4 | Compare flow holds 3+ working-memory items | P0 | Drops at item 3. Persona either re-taps confused or × out. |
| 5 | Score numbers without adjacent verdict words | P1 | "4.8 / 10" alone reads as "I guess that's middling?" → no decision. |
| 6 | Methods modal opens to dense paragraph | P1 | Walls of text. Persona × out without reading. |

**Hyperfocus moments (don't redesign these away):**
- The plain-English score paragraph at the bottom of every panel ("Children and elderly residents face elevated risk… Cumulative exposure adds up even when no single source is illegal.")
- The proximity-burden interpretation ("Very High — extreme clustering of industrial sources at close range.")
- The "Dominant nearby source: I-95 / I-495 / Route 13 (0.5 mi)" line — concrete roads + concrete distance.
- The 💨 wind indicator next to facility names.
- The "Jump to Claymont" welcome-card tile (lowest-friction useful interaction in the app).

### Appendix B — Cross-source methodology spot-check

Test method: pulled CDC PLACES BRFSS 2023 adult-asthma current-prevalence (CASTHMA) for the underlying census tract of three random block groups via the public Socrata API. Compared to the value rendered in the CC4EJ info panel for the same block group.

| BG (GEOID) | Location | EFA status | CC4EJ adult asthma % | CDC PLACES API value | Match |
|---|---|---|---|---|---|
| 100030103002 | Claymont (Tract 10003010300) | Significant | **10.2%** | **10.2%** | ✓ exact |
| 100030006013 | Wilmington (Tract 10003000601) | Significant | **13.3%** | **13.3%** | ✓ exact |
| 100050505062 | Lewes / Sussex (Tract 10005050506) | Not EFA | **10.6%** | **10.6%** | ✓ exact |

Source for the CDC values: `https://chronicdata.cdc.gov/resource/cwsq-ngmh.json?$where=stateabbr%3D%27DE%27%20AND%20measureid%3D%27CASTHMA%27%20AND%20locationname%20IN%20(%2710003000601%27,%2710005050506%27,%2710003010300%27)`

**Methodology note for hearings:** CDC PLACES publishes per-tract; CC4EJ stores per-block-group, so all BGs within a single tract show the same asthma value. This is faithful to the source's resolution and disclosed in the methodology modal.

**Other internal-consistency checks:**
- Wind-adjusted proximity burden formula: documented in methods modal under "How Pollution Burden (EB) is scored." Reproducible.
- Combined Impact Index: panel shows the math inline ("Proximity burden (10.0) × vulnerability (3.3) ÷ 10 = 3.3"). Defensible to a numerate reviewer.
- Data vintage pill on every panel ("Showing 2024 data (nearest available to 2026)") — honest about lag.
- Federal source attribution: methods modal lists EPA EJScreen 2016–2024, US Census Decennial + ACS 5-year, CDC PLACES, CDC EPHT, NOAA, DelDOT. CSV of raw scores is downloadable.

---

## Bottom line for the legislator

The data is real, the federal sources match to the decimal, the methodology is documented and honest, and EPA's own interactive EJScreen has been offline for over a year. There is no comparable interactive tool for Delaware. With the eight fixes above (most of which the maintainer can ship in a single afternoon), this becomes a tool the office can reference in newsletters, link in constituent replies, and quote in committee without exposure.

**Recommended next step:** authorize comms to draft a one-paragraph map mention for the next district email, blocked on fixes #1 (At-risk populations) and #2 (over-65 build bug) landing first. Estimated time-to-citable: under two weeks if the maintainer accepts the request list.

— Chief of Staff
