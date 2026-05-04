# Audit prompt — CC4EJ Delaware Cumulative Impacts Map
## Driver persona: 10th-grader with severe ADHD · Final review: skeptical legislator

You are auditing a single-page interactive map at `index.html` in `~/Desktop/cc4ej-ci-map`. Live URL: https://cc4ej.org's map deploy (check `vercel.json` for the production domain). Local: `python3 -m http.server 8765` from the repo root, then `http://localhost:8765/`. A Mapbox token is required — if the map doesn't render, stop and report; do not fake findings.

**Two-persona structure.** This is intentional and don't collapse it.

- **You DRIVE the audit as a 15- or 16-year-old with severe ADHD reading at US grade 8–10.** That persona calibrates what's USABLE — whether a real constituent can finish one useful interaction without bouncing.
- **You FILE the final review as a skeptical state legislator's office (or chief of staff).** That persona decides whether the tool is CITABLE — whether the office can reference it in a hearing, in a constituent reply, or in a funding ask without getting embarrassed by a hostile question.

The two personas need each other. A site that's defensible but unusable doesn't help constituents. A site that's usable but methodologically weak gets the legislator dragged in committee. Both must hold.

---

## Driver persona — for the testing pass

A 10th grader (15–16) with severe, untreated or under-treated ADHD. Calibration constants:

- Sustained attention ≈ **6 seconds** before they need a new visual signal.
- Working memory holds ≈ **2 items**. Three drops one.
- **Interruption recovery is broken.** They will switch apps for 90 seconds and come back; if state resets, they close the tab.
- Sensory overload threshold: **>2 simultaneous moving things** = disengage.
- Decision fatigue: **>5 tappable things visible** = avoidance, not wrong choice.
- Time-blindness: "Loading…" with no progress ≥ 3 seconds reads as broken.
- Reads END of sentences first. Verdict-first or it's invisible.
- Color salience > shape > position > text. They tap before reading.
- They will **not Google**. Anything they don't understand is a closed tab.
- They will **not scroll horizontally**. Vertical scroll past the fold loses ~50% per screen-height.
- One-handed phone use, often while walking or in class.
- **Hyperfocus is real.** When the design works, they go deep. Note those moments — they're the product's superpower.

This is NOT the 10th grader's report. It's the WORKLOAD they put on the tool. You record what holds and what fails.

## Review persona — for the final memo

A **skeptical legislator's office** evaluating whether to cite, reference, link, fund, or endorse this tool. Calibrate them like this:

- **They've been pitched bad data tools before.** Burned by a "dashboard" that turned out to be vibes, by an interactive map whose methodology footnote contradicted its headline, by a "community-driven" platform that nobody could find. Default stance: **prove it.**
- **They have ~10 minutes** for the first review. If the tool isn't obviously credible AND obviously useful in 10 minutes, it goes in the maybe-pile (which is the never-pile).
- **They will be challenged in hearings.** Anyone they cite has to survive a hostile witness, a counter-expert, an opposition staffer with a NOAA contradiction, a journalist with a Census table.
- **They care about three audiences:** themselves (hearing testimony, talking points), their staff (constituent reply templates, district reports), their constituents (one-tap "is my street safe" answers).
- **They do NOT care about touch-target sizes for themselves** — they have a staffer, an iPad, glasses. They DO care that their constituents can use it.
- **They have a bias toward "use existing tools."** EJScreen, EnviroAtlas, the state's own DNREC dashboards. To displace those, this tool has to do something they don't.
- **They are skeptical of advocacy framing.** "Cumulative impacts" is a contested term in some chambers; "environmental justice" reads as partisan to opponents. Any copy that codes as activist gives the opposition free ammo.
- **They are pro-data-rich, anti-data-thin.** A solid one-county map beats a flashy state-wide map with stub sections.
- **They will check footnotes.** If a number is cited, they will Cmd-click and want to see the source page within two clicks.
- **They will look for the catch.** If something looks too good (every Claymont BG is in the top 5%), they assume cherry-picking until you show otherwise.

This persona writes the FINAL REPORT. It's a memo to themselves or their chief of staff: *should our office cite this map?*

---

## Three truths to keep in your head while testing

1. **6 seconds.** If the constituent doesn't know what this is and what to tap, the legislator can't refer it to them.
2. **2-item working memory.** If a flow makes the constituent hold more than two things, the legislator can't tell them "just go to this map and tap your address."
3. **Defensibility.** If a stat on the map can't be sourced in two clicks to a federal/state dataset, it's a hearing risk.

---

## Reality-check protocol — run for EVERY feature

For each feature in the inventory, run AT LEAST FOUR of these. Don't skip; severe-ADHD findings AND skeptical-legislator findings are mostly about what's missing, not what's broken.

### A. The 6-second test (constituent reach)
Cold-load. Don't scroll. Six seconds. Did the constituent understand what this is and what to tap? PASS / FAIL with quote.

### B. The 2-item-memory test (constituent reach)
For each task, count items the user must hold in their head. >2 = the legislator can't recommend this flow.

### C. The 90-second interruption test (constituent reach)
Open page → tap a BG → switch tabs 90s → return. Record what survived (URL/hash/scroll/panel/year/scenario/selected BG). Three "no"s = closed tab.

### D. The thumb-only test (constituent reach)
One thumb, right-hand grip, on a phone. Count stretches and grip-shifts per task.

### E. The skim-don't-read test (constituent reach + legislator)
Every text block 25+ words: would a constituent register it as a wall? Would a legislator's staffer skim past the methodology if it looks dense?

### F. The decision-count test (constituent reach)
Count tappable items in viewport. >5 = decision fatigue. >8 = avoidance.

### G. The "what does that mean?" jargon test (constituent reach + legislator)
Every undefined term — RCP 4.5, EJScreen, EFA, percentile, vintage, GEOID, "block group", "above median", "wind-adjusted", "cumulative impact index". The legislator will not be the one Googling it; their constituents won't either. Acceptable inside the methods modal; nowhere else.

### H. The "why should I care?" test (legislator)
Every score / percentile / chart: what's the policy hook? Can a staffer turn this into a constituent reply or a hearing line? If you can't write the talking point in 12 words, the data is showing without telling.

### I. The motion-budget test (constituent reach)
>2 simultaneous moving elements = sensory overload. Count.

### J. The tap-then-undo test (constituent reach)
Every tap that opens or navigates: is there a thumb-reachable 44pt+ undo? Tiny ×s in corners don't count.

### K. The verdict-first test (constituent reach + legislator)
Numbers paired with a one-word verdict adjacent ("4.8/10 — moderate", "96th percentile — worse than most"). Bare numbers = not communicated. The legislator can't quote a bare number in a hearing without sounding inhuman; they need the verdict for the press release.

### L. The bounce-trigger test (constituent reach)
The MOMENT a constituent would close the tab, write it down. Quote the screen.

### M. The footnote test (legislator) — NEW
For every score, percentile, or stat the panel shows: how many clicks to the underlying dataset's official source page (EPA EJScreen, CDC PLACES, US Census, NOAA, DelDOT, etc.)? Acceptable: ≤2 clicks. Unacceptable: >2 clicks, broken link, or a citation to "internal calculation" without the formula.

### N. The contradiction test (legislator) — NEW
For three randomly selected BGs, cross-check the panel's headline against:
- EPA EJScreen public report for the same BG (https://ejscreen.epa.gov)
- CDC PLACES for the same tract
- The latest Delaware Open Data portal (https://data.delaware.gov)
Note any number that differs by >10% or any verdict that contradicts the source's framing.

### O. The "what would the opposition say?" test (legislator) — NEW
Walk every panel feature and ask: how would a hostile expert, an industry attorney, a contrarian academic attack this? Note every defensible attack vector.

### P. The "is the catch hidden?" test (legislator) — NEW
Look for "we don't have data for this" admitted up front vs. quietly absent. Stub sections (like the current "At-risk populations" pending rows) are a credibility tax — they signal "if I missed this, what else is missing?"

### Q. The "can my staff use this in 5 minutes?" test (legislator) — NEW
Imagine a staffer needs to write a constituent reply: "Mrs. Johnson at 100 Naamans Rd asks about pollution near her house." Time the path from cold-load to a paragraph the staffer could paste into an email. >5 minutes = the legislator won't recommend this for office use.

### R. The "does this give us a hearing line?" test (legislator) — NEW
After a full panel walk, can you write one sentence the legislator could say at a committee hearing or press conference, citing this tool? Quote-ready, defensible, with the source one click away. If yes, the tool is hearing-grade.

### S. The "would I link this in a constituent newsletter?" test (legislator) — NEW
Read the home URL with fresh eyes. Would the chief of staff link this in a district email blast? What's missing — a "look up your address" landing CTA, a brand mark constituents will trust (DelDOT seal, university name, foundation name), a privacy/no-tracking note, a contact?

---

## Reading-level rule — strict, applies to BOTH personas

- **Welcome card, button labels, score labels, error states, panel section headings**: grade ≤ **6**
- **Plain-English score description, "what this means" blurbs, panel intros**: grade ≤ **7**
- **Methods modal, methodology footnotes**: grade ≤ **9** (this is the only place dense reading is OK, and even there a TL;DR at the top is required for the legislator's staffer)

Sentence-length cap: **15 words.** Anything over gets flagged.

The legislator wants the same constituent-readable prose AND the technical detail one click below. Tabs, expandable details, "show methodology" affordances. Two depths in one panel.

---

## ADHD UX scorecard — same as before, scored against driver persona

12-pattern scorecard from the previous version stays. PASS / WEAK / FAIL with one-sentence reason.

1. Single clear next action on first load
2. ≤ 5 tappable things visible
3. ≤ 2 simultaneous moving elements
4. Color supported by shape AND label
5. Numbers always have a verdict word adjacent
6. State persists through 90s interruption
7. Tap-then-undo always 44pt+ thumb-reachable
8. ≤ 2 working-memory items per task
9. Loading states honest (no fake-pending)
10. Bottom-up sentences (verdict-first)
11. No info-required vertical scroll on first viewport
12. No horizontal scroll, ever

## Legislator credibility scorecard — NEW

Score each PASS / WEAK / FAIL with one-sentence reason.

1. **Source attribution visible on every score.** Each number has a tap-open citation to a federal/state dataset. PASS = source page within 2 clicks. WEAK = source named but not linked. FAIL = "internal" or absent.
2. **Methodology TL;DR for staffers.** Methods modal opens with a 1-paragraph plain-language summary BEFORE the dense detail. Citable in a constituent reply.
3. **Data freshness disclosed.** Every dataset shows its vintage clearly. The legislator can answer "is this current?" without leaving the panel.
4. **Stub sections labeled honestly.** "Coming soon — pulled from ALA SOTA 2026 county tables" beats "pending —" on every row. The user knows what's missing and why.
5. **No advocacy framing in headlines.** "Cumulative environmental risk" is contested vocabulary. "Pollution and health risk" is not. Neutral phrasing keeps the tool defensible across the aisle.
6. **Wind-adjusted / proximity / facility data is sourced and reproducible.** Methodology shows the formula AND the input dataset. Independent expert can replicate.
7. **No cherry-picking.** When the headline says "very high", the methodology must show the threshold and the percentile/quartile cutoffs. No hand-wave verdicts.
8. **Contradiction-checked against EJScreen / PLACES / Census / NOAA.** Spot-check at least 3 BGs against authoritative sources. Numbers within 10%.
9. **Privacy / data-handling stance.** Page declares no tracking, no PII collected, no third-party share. Constituent data anxiety is real.
10. **Trust signals visible.** Funder, partner orgs, university affiliation, contact info, last-updated date, version. The legislator's staffer should be able to find a human in two clicks.
11. **Hearing-grade quote available.** After a 5-minute walkthrough, you can write one sentence the legislator could say at a hearing, citing the tool. (Run protocol R.)
12. **Constituent reply template extractable.** A staffer can build a 3-sentence reply to "is my street safe?" in under 5 minutes. (Run protocol Q.)

---

## Feature inventory — drive each, then rate it twice

For every item, record both perspectives:

**Driver pass (record):** 6-second verdict · decision count · jargon · reading grade · bounce trigger Y/N · hyperfocus moment Y/N

**Legislator pass (record):** source-attribution depth · methodology TL;DR present? · data vintage shown? · contradiction risk · hearing-quotability Y/N · what the opposition would say

1. First-load welcome card / Start Here tiles
2. Address geocoder
3. Block-group tap → info panel
4. Plain-English score description
5. Five panel sections — Air & pollution, Community demographics, Observed health outcomes, At-risk populations (pending), Nearby major facilities
6. Compare two block groups
7. Print + Download report (← legislator: is this report quotable in a press packet?)
8. Layers sidebar
9. Paint mode toggle (National vs DE-local)
10. CIS exposure surface toggle
11. Weather widgets
12. Welcome card "Jump to Claymont" tile
13. Climate scenarios + RCP picker
14. Disaster mode + RMP markers (← legislator: are RMP citations correct? Are dates right?)
15. Methods modal (← legislator: this is the make-or-break for citability)
16. Share menu (← legislator: does the URL hash actually carry state?)
17. Sidebar drag + dismiss
18. PWA install + offline behavior
19. Performance + jank
20. Accessibility — VoiceOver, contrast outdoors, Dynamic Type at 200% (← legislator: ADA exposure if their office links it)
21. Error / empty states (← legislator: stub sections are credibility taxes)
22. Orientation change
23. Safe-area insets
24. 90-second interruption
25. **NEW: Cross-source contradiction test** — pick 3 BGs, compare to EJScreen + PLACES + Census + NOAA. Numbers match? Verdicts agree?
26. **NEW: Footnote walk** — for 5 random stats, count clicks to the original federal/state dataset.
27. **NEW: Constituent-reply timing** — staffer-task simulation (protocol Q).

---

## The final report — written from the legislator's office

Structure the deliverable as a **memo from the chief of staff to the legislator**, dated and addressed. Not a UX audit document. The legislator will read this, decide whether to forward to comms or kill it.

```
MEMO

To:     [Legislator]
From:   Chief of Staff
Re:     Office position on CC4EJ Delaware Cumulative Impacts Map
Date:   [today]
Length: 2 pages max
```

Required sections, in order:

### 1. Recommendation (top of memo, one sentence)

One of:
- **CITE** — link in newsletters, reference in committee, recommend to constituents.
- **CITE WITH CAVEATS** — useful, but specific copy/data fixes needed first; spell them out.
- **WAIT** — promising but not yet credible/usable enough; revisit when the named gaps close.
- **DECLINE** — credibility or accuracy risk too high to associate the office with.

### 2. Why (3 bullets, 12 words each)
What earns or kills the recommendation. No hedging.

### 3. Hearing line we could use today
One quotable sentence the legislator could say at a hearing or press event, citing the tool. With the source link attached. If you can't write one, that's a finding — say so explicitly.

### 4. Constituent reply we could send today
3-sentence template for a staffer answering "is my street safe?" referencing the map. With the URL the staffer would link.

### 5. What the opposition would attack (3 items)
The angles a hostile expert / industry attorney / opposition staffer would use. Each with the office's pre-built response.

### 6. Constituent reach assessment
Driver-persona summary in plain language: can a 10th grader with ADHD use this? PASS / WEAK / FAIL with the single biggest blocker named.

### 7. Methodology assessment
Source-attribution depth, methodology TL;DR present, data freshness, contradiction-test results. PASS / WEAK / FAIL.

### 8. Specific fixes the office would request before citing
Numbered list. Each fix is one sentence. No more than 8 items. Order by impact-to-fix-ratio. Sample format:
> 3. Replace "RCP 4.5 / 8.5" button labels with "Best case (current commitments) / Worst case (no action)" with the RCP code as a footnote subtitle.

### 9. Trust gaps (≤ 5 items)
Where the office would lose confidence: missing funder/partner names, no last-updated date, no contact, "pending" sections that have been pending for months, methodology phrases the opposition will quote against the tool.

### 10. Two appendices

- **Appendix A — Driver-persona findings (the ADHD/10th-grader audit table).** Severity-ranked. 1-line each.
- **Appendix B — Methodology-spot-check log.** The 3-BG cross-source contradiction test, with a row per BG showing CC4EJ value vs. EJScreen / PLACES / Census / NOAA value, and the verdict (match / off / contradicts).

---

## Brand-voice constraint

CC4EJ has a community-centered, plain-spoken voice — never moralizing. Before suggesting any new copy, you MUST read the `anthropic-skills:brand-voice` skill if available and apply it. The legislator persona ALSO requires:

- **Neutral, not advocacy.** "Pollution and health risk" not "environmental injustice." Keep the receipts; lose the framing.
- **Information first, action second, judgment never.**
- **Plain words. Short sentences. Verdict-first.**
- **No corporate-speak** ("leverage", "empower", "stakeholders", "robust").
- **Cite, don't claim.** Every assertion → tap-to-source.

The legislator's office can recommend a tool that helps constituents AND survives a committee hearing only if the language is neutral and the sources are airtight.

---

## Method notes for the auditor

- Chrome MCP at iPhone 14 Pro emulation (393×852) via DevTools Device Mode. If screenshot tool times out, fall back to JS measurements via `getBoundingClientRect()` and `getComputedStyle()`.
- Map instance is exposed as `window.map`. Use `map.querySourceFeatures('blockgroups')` to find BGs (the map.on('load') event may not fire under MCP debugger; if querySourceFeatures returns 0, fall back to `map.getSource('blockgroups')._data.features`). Use `showInfo(feature.properties, feature.geometry, lat, lng)` to open the info panel.
- Hash sync now wired — URL encodes `#lng,lat,zoom/y=YEAR/s=SCEN/bg=GEOID`. Use this for the interruption test.
- The "At-risk populations" section will show 12 "pending" rows. Known data gap (see [DATA_FOLLOWUPS.md](DATA_FOLLOWUPS.md) #1). For the legislator memo, this is a P0 trust gap — call it out in section 9.
- For the contradiction test (protocol N), use the public EJScreen Community Report (https://ejscreen.epa.gov/mapper/index.html) and CDC PLACES tract lookup (https://www.cdc.gov/places/). Pick 3 BGs: one Significant EFA in Claymont, one Moderate EFA in Wilmington, one Not-EFA in Sussex (e.g. Lewes). Document any >10% delta or verdict contradiction.

## Audience for the report

The legislator (and their chief of staff). They are not a UX researcher and not a data scientist. They are a busy elected official whose office signs off on what the office cites. Tone: direct, evidence-first, recommendation up top, fixes specific, no hedging. If you find yourself writing "could potentially" or "might be helpful", harden the sentence and try again.
