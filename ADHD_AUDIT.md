# CC4EJ Delaware Cumulative Impacts Map — ADHD audit
## Persona: 15–16 yo with severe ADHD, 10th-grade reader

**Audited:** 2026-05-03 · iPhone 14 Pro Max emulation in Chrome DevTools (430×932), mobile Safari UA, DPR 3 · post-mobile-fix branch · `python3 -m http.server 8765`.

---

## TL;DR

1. **6-second test: FAIL.** First load shows 21 tappable items, three weather chips, a CIS toggle, a Layers tab, a sidebar, a busy time-bar, and a 54-word welcome card. The persona does not know what to tap.
2. **One useful interaction completion: WEAK.** A 10th grader can tap "Jump to Claymont" → see colors → tap a colored area → see scores. But the panel is 5.6× viewport-tall and most of what makes it valuable lives below the first screen, where this persona does not look.
3. **Biggest blocker: decision overload from second one.** 21 things to tap on a fresh load is 4× the persona's ceiling. The fix isn't more onboarding; it's hiding 16 controls behind a "Show more" affordance until the user has done one thing.

---

## The 6-second test

**What's on screen at t=0:** header (logo + clipped title + Methods icon + Share button), full-width search pill, three weather chips stacked (wind / AQI / temp), a CIS "Exposure surface" toggle floating top-right of the map, a vertical "Layers" tab on the left edge of the map, the map itself with a Combined Burden legend overlay, a 7-button time-bar at the bottom (1875 / 1920 / 1970 / 2016 / 2020 / 2024 / 2050 / Now / Layers / hamburger), AND a welcome card pinned above the time-bar with three tappable tiles + an × dismiss.

**Verdict: FAIL.** The welcome card does the work — its h1 ("Start here") + three labeled tiles tell the persona what to do. But the welcome card competes with everything else for first-glance attention. A persona with severe ADHD looks AT THE MAP first because that's the biggest visual element with the most color. The welcome card is small, in the lower-middle, and easy to miss against the colored map behind it.

---

## Bounce-trigger log

In order of likelihood that the persona closes the tab:

1. **First-load decision overload.** 21 tappable items in viewport before a single tap. Persona's ceiling is 5. Above 8 = avoidance. **They scroll once, see no obvious next action, close the tab.**

2. **The "Methods" button at top-right.** Tiny icon (39×29px) in the corner. If they tap it, they get a modal whose first sentence is *"Everything that drives the colors on this map — sources, weights, and the limits of what it can tell you."* — that's grade 9.5, 18 words, em-dash mid-sentence. Persona reads "everything", scans for the next interesting word, finds none, taps × and probably closes the tab.

3. **"Cumulative environmental risk in Delaware's ~700 block groups."** Welcome card line two. Grade 9.1, contains "cumulative" + "block groups" + "~700" — three things the persona doesn't know in 11 words. They will not parse this. They will tap one of the tiles below or close.

4. **Time-bar with 7 era/year buttons + Now + Layers + hamburger.** 10 controls in a strip at the bottom. Persona has no idea what "1875 / 1920 / 1970" is doing there or why "2050 What's coming" matters. They might tap one, see colors change, panic, tap "Now" to undo, lose trust.

5. **2050 → "Moderate RCP 4.5 / High RCP 8.5 / Why?"** If they accidentally tap 2050, the projection lane appears with two buttons named after Representative Concentration Pathways. They will not know what RCP is. The "Why?" link reads "RCP" and they bounce.

6. **At-risk populations section: 12 rows of "pending —".** They scroll the panel, see 12 lines of "pending", read "broken" not "loading", lose trust in the whole map.

7. **"PM2.5 air pollution — Above median".** Above what median? Persona has no baseline. PM2.5 needs translation: "tiny soot particles that get into your lungs". Above median needs translation: "more than half the country has it worse, but you have it pretty bad too" — or just "Worse than most places" with a verdict word.

8. **"Health burden composite (CDC PLACES) 3.3 / 10".** "Composite" is jargon. "(CDC PLACES)" is an unexplained acronym in parens. The number sits without a verdict word ("3.3/10 — moderate" would land; "3.3 / 10" alone reads as "I guess that's middling?").

9. **"Showing 2024 data (nearest available to 2026)".** Reads as "we don't have current data" — for a persona who doesn't know that EJScreen lags by 2 years, this is "broken".

10. **Compare flow.** Tap Compare → info panel disappears → the chip at the top of the time-bar says "📌 New Castle BG 103002 — click a block group to compare". Persona doesn't know what BG 103002 means, doesn't connect "click a block group" to "tap a colored area on the map." Three working-memory items: which one I pinned, what I'm doing, how to undo. **Drops at item 3.** Closes the tab or taps the × to give up.

---

## Hyperfocus moments

Where the design legitimately earns deep attention from the persona:

1. **The plain-English score description** at the bottom of the panel: *"This neighborhood carries a very high pollution burden. Children and elderly residents face elevated risk of asthma, lung disease, and cancer. Cumulative exposure from multiple sources adds up even when no single source is illegal."* Grade 10.2, 35 words. Slightly above the target but it READS as the answer to "is my neighborhood safe?" — which is the H1 question. Verdict-first ("very high"), then specific risks, then the killer line ("adds up even when no single source is illegal"). **This is the product.** Don't touch this paragraph.

2. **"Very High — extreme clustering of industrial sources at close range"** (proximity-burden interpretation). Grade 8.4, 10 words, verdict-first. Persona reads "Very High" first, gets the message, then has the option to read the qualifier. Exactly right.

3. **"Dominant nearby source: I-95 / I-495 / Route 13 (0.5 mi)."** Grade 1.5, names roads they recognize, gives a distance they understand. Concrete. Tappable mental model. Persona thinks "oh, the highway is half a mile away, that's why."

4. **The "⚑ Jump to Claymont" tile** in the welcome card (recently added). One tap and the map zooms to a relatable place. Lowest-friction useful interaction in the whole app.

5. **The wind 💨 indicator next to facility names** in the "Nearby major facilities" list — visual + spatial + immediate. "This factory is upwind of you right now."

6. **Score boxes (Pollution Burden / Vulnerability / Combined Burden 7.2 / 3.3 / 4.8)** rendered big and color-coded. Not perfect (no verdict word adjacent) but the visual hierarchy is right — persona reads the number, registers the color, gets the gist.

---

## Jargon table — what the persona doesn't know

Every item should be replaced or translated. Counts are visible-on-screen instances during a typical Claymont visit.

| Term | Where it appears | ~ Count | Persona-grade replacement |
|---|---|---|---|
| **cumulative** | Welcome card, header tagline, methods modal | 5+ | "added up", "stacked together" |
| **block group** | Welcome card, info panel, methods | 8+ | "neighborhood" or "small area" |
| **vulnerability** | Score box label | every panel | "Who's at risk" — a name, not a math word |
| **percentile** | Air & pollution rows | every panel | drop the word; say "Worse than 96 of 100 places in the US" |
| **above median** | Air & pollution rows | 4 per panel | "Worse than most places" (verdict) + tooltip with the number |
| **wind-adjusted** | Proximity tag | every panel | "wind matters here" with a small explainer pill |
| **proximity burden** | Section header | every panel | "Pollution from nearby sources" |
| **combined impact index** | Section + label | every panel | "Total pollution × who's at risk" — explicit math, not jargon |
| **CDC PLACES** | Health composite row | every panel | "(CDC health survey)" or just remove |
| **CDC EPHT** | Asthma rate rows | every panel | "(CDC tracking data)" or just remove |
| **EJScreen** | Methods modal | many | "EPA's environmental justice tool" |
| **EFA / Equity Focus Area** | EFA badge, methods | every panel | "DelDOT-flagged equity area" with a "what's that?" tap |
| **RCP 4.5 / RCP 8.5** | 2050 scenario picker | when projection on | "Moderate (current commitments)" / "High (no further action)"; keep RCP as fine print |
| **vintage / data_year** | Data-year pill | every panel | "From 2024" — drop the parenthetical |
| **GEOID 103002** | Panel title prefix | every panel | drop or tuck behind a "?" affordance |
| **Exposure surface (CIS)** | Top-of-map toggle | always | "Pollution heat-map" |
| **Composite** | Health row | every panel | "Combined health score" |
| **Linguistic isolation** | Demographics row | every panel | "Language barriers" (already used elsewhere — be consistent) |

---

## Reading-level table

Targets: buttons/labels ≤ 6 · blurbs ≤ 7 · methods ≤ 9. Sentence-length cap: 15 words.

| Location | Excerpt | Words | FK grade | Pass/fail | Rewrite |
|---|---|---|---|---|---|
| H1 | "Is My Neighborhood Safe?" | 4 | 3.7 | ✓ | keep |
| Tagline | "Delaware Cumulative Impacts Map · CC4EJ" | 5 | **12.3** | ✗ | "Delaware pollution map · CC4EJ" (grade 6) |
| Welcome intro | "This map shows cumulative environmental risk in Delaware's ~700 block groups. Pick a path:" | 15 | **9.1** | ✗ | "This map shows pollution and health risk in every Delaware neighborhood. Pick one:" (grade 6.2) |
| Tile 2 | "See my impacts — Tap any colored neighborhood for scores and nearby sources" | 11 | **11.2** | ✗ | "See my area — Tap any colored shape on the map" (grade 4.8) |
| `lbl-eb` | "Pollution Burden" | 2 | **14.7** | ✗ on the score-label rule (FK on 2-word phrases is unstable but flag the JARGON: "Burden") | "Pollution near you" |
| `lbl-sv` | "Vulnerability" | 1 | n/a | ✗ JARGON | "Who's at risk here" |
| `info-data-year` | "Showing 2024 data (nearest available to 2026)" | 7 | 7.4 | ⚠ borderline + "nearest available" jargon | "From 2024 (newest we have)" (grade 4.8) |
| `prox-interp` | "Very High — extreme clustering of industrial sources at close range." | 10 | 8.4 | ⚠ for blurb-target ≤ 7; verdict-first is good | "Very High — lots of factories and highways close by." (grade 5.4) |
| `info-score-desc` | (the 35-word killer paragraph above) | 35 | 10.2 | ⚠ above target but verdict-first; **keep** with minor tightening | (already good — see Hyperfocus #1) |
| `climate-future-section` intro | "Indicators derived from the selected year + emissions scenario (RCP 4.5 / 8.5). Heat & extreme-precipitation indices are modeled at block-group scale; sea-level rise is the NOAA regional projection above today's high-tide line." | 33 | **9.3** | ✗ jargon-laden, methods-modal-grade copy in a user-facing pill | "What 2050 might look like for this area, based on heat, rain, and sea level forecasts." (grade 7.4) |
| Methods modal head | "Everything that drives the colors on this map — sources, weights, and the limits of what it can tell you." | 21 | 9.5 | ✗ over methods-modal target only because TL;DR is missing | Add a 1-sentence TL;DR: "Where the numbers come from. Tap a section to dig in." |
| Indicator row | "Health burden composite (CDC PLACES) 3.3 / 10" | 7 | n/a | ✗ JARGON ("composite", "CDC PLACES") + no verdict | "Combined health score — 3.3/10 — moderate" |
| Indicator row | "Crude Rate of Hospitalizations for Asthma per 10,000 Population CDC EPHT · 2022" | 11 | **18+** | ✗ raw spec language wrapped onto 3 mobile lines | "Asthma hospital visits — 6.7 per 10,000 (2022)" |
| Time-bar era | "Before industry 1875" | 3 | n/a | ✓ with caveat (persona doesn't know why they should care about 1875) | keep label, add a 1-line caption above the bar: "Slide through time" |

---

## ADHD UX scorecard

| # | Pattern | Grade | Reason |
|---|---|---|---|
| 1 | Single clear next action on first load | **WEAK** | Welcome card has 3 (good) + 1 dismiss (acceptable), but it competes with 17+ other on-screen controls for attention. |
| 2 | ≤ 5 tappable things visible | **FAIL** | 21 on first load. 26 with info panel open. Above the persona's avoidance ceiling (8) by 3×. |
| 3 | ≤ 2 simultaneous moving elements | **PASS** | Loading spinner + map ease-in animation + (optional) flying = mostly within budget; weather widgets don't pulse. |
| 4 | Color supported by shape AND label | **WEAK** | Map uses color alone for burden; legend has shape (gradient bar) but BG polygons don't have a label or pattern. Colorblind mode helps but is buried. |
| 5 | Numbers always have a verdict word | **FAIL** | Most scores show as bare numbers ("3.3 / 10", "96th percentile", "10.2%") with no adjacent verdict. Only proximity-burden ("Very High") gets it right. |
| 6 | State persists through 90s interruption | **PASS** | Hash sync (newly added) restores lat/lng/zoom + year + scenario + selected BG on tab restore. Verified. Scroll position inside the panel does NOT persist — minor. |
| 7 | Tap-then-undo always 44pt+ thumb-reachable | **WEAK** | Info-panel × is now 44×44 ✓. But Methods × is top-right (stretch), Welcome dismiss × is 24×24 (under), share-menu items are reachable. Time-bar buttons are mostly 36–40px now. |
| 8 | ≤ 2 working-memory items per task | **FAIL** | Compare flow holds 3+ ("which BG I pinned" + "what I'm comparing it to" + "how to clear"). Climate scenario flow holds 3+ ("which year" + "which RCP" + "what indicator I'm reading"). |
| 9 | Loading states show progress within 1s / honest after 3s | **FAIL** | "At-risk populations" section shows 12 "pending —" lines with NO indication that this data has been pending for ~6 months. Reads as a stuck loader. |
| 10 | Bottom-up sentences (verdict-first) | **WEAK** | Plain-English score paragraph nails it. Most other copy ("Indicators derived from the selected year + emissions scenario...") buries the verdict at the end or never has one. |
| 11 | No info-required vertical scroll on first viewport | **FAIL** | Welcome card sits below the map controls; the persona has to scroll past the busy top of the map (or their eye does). The "what is this?" answer is below the welcome card in the sidebar, totally invisible. |
| 12 | No horizontal scroll, ever | **PASS** | No horizontal scroll detected on any view. ✓ |

---

## Decision-count audit

| Screen state | Tappable items in viewport | Pass (≤5) |
|---|---|---|
| First load (welcome card showing) | **21** | ✗ |
| Info panel open | **26** | ✗ |
| Sidebar drawer open | **23** | ✗ |
| Methods modal open | ~6 (modal close + 5+ details) | ⚠ borderline |
| Share menu open | ~5 (URL, Copy, Share via, dismiss path) | ✓ |

The decision count is the SINGLE biggest ADHD problem on this site. Every other finding shrinks if this one is fixed.

---

## Working-memory audit

| Task | Items to hold in head | Pass (≤2) | What gets dropped first |
|---|---|---|---|
| "What's the burden in my neighborhood?" | 1 (my address) | ✓ | — |
| "Compare my neighborhood to my school" | 4 (my BG, school BG, what comparison means, how to undo) | ✗ | "what comparison means" — they'll re-tap and confuse themselves |
| "What will 2050 look like?" | 3 (current year context, RCP scenario, which indicator) | ✗ | RCP 4.5 vs 8.5 — they pick one randomly and don't notice the other |
| "Toggle off traffic + warehouses" | 3 (Layers tab, scroll to layer, target right checkbox) | ✗ | Where the layer is in the list (sidebar is 2920px scroll) |
| "Save this view to send to mom" | 2 (Share button, Copy URL) | ✓ | — |

---

## Interruption-recovery audit

Ran protocol C (load → tap BG → switch tab 90s → return) using URL-hash restore.

- **Map view (lat/lng/zoom):** ✓ restored exactly via hash
- **Selected year:** ✓ restored via `y=` hash param
- **Scenario:** ✓ restored via `s=` hash param
- **Selected BG (info panel auto-opens):** ✓ restored via `bg=` hash param
- **Info-panel scroll position:** ✗ resets to top; user has to find their place
- **Sidebar open/closed state:** ✗ defaults to closed; minor
- **Welcome card dismissed state:** ✓ via localStorage

**Verdict for severe ADHD:** mostly recovered. The scroll-position-inside-panel reset is the one that bites — if the user was reading the EFA detail or the climate-future paragraph and got pulled away, they have to re-find their spot in a 3000px-tall panel.

---

## Findings table

| # | Feature | Severity | Persona reaction (1 sentence) | What they tap next | Where they get stuck | Fix |
|---|---|---|---|---|---|---|
| 1 | First-load decision overload | **P0** | "Too many things." | Often: nothing. Sometimes: random. | Decision avoidance. | Hide weather widgets, CIS toggle, time-bar, layers tab behind a "Show map controls" toggle. Welcome card + map only on first load. |
| 2 | Welcome card competes with map color | **P0** | "Where do I look?" | Map (it's bigger and more colorful). | Misses the welcome card entirely. | When welcome card is showing, dim the map to 30% opacity. Force focus. |
| 3 | "Cumulative" / "block group" / "vulnerability" / "percentile" / "RCP" jargon | **P0** | "I don't know what this means." | They don't tap; they close. | Vocabulary cliff. | Translate every term in the jargon table above. Keep technical names in tooltips for journalists/regulators. |
| 4 | At-risk populations: 12 "pending —" rows | **P0** | "This is broken." | × the panel. | Trust collapse. | Hide the section until at least one row has data. Or replace with "Coming soon — county-level at-risk numbers from the ALA SOTA report" (one row, honest, doesn't pretend to be loading). |
| 5 | "Above median" / "Top 22%" without verdict word | **P0** | "Is that bad?" | They scroll past. | No mental model of what's good or bad. | Every percentile gets a verdict: "Top 22% (worse than most)" or "Worse than 78% of US neighborhoods." |
| 6 | Compare flow holds 3+ items in working memory | **P0** | "Wait, what was I doing?" | Often: × out. | Memory overflow at item 3. | Make compare a SLIDE — split the panel into two sides; tap a second BG and the second side fills. Persistent visual = no memory load. |
| 7 | 2050 RCP picker buried below time-bar | **P1** | "Why are there two yellow buttons that say RCP?" | Random tap. | "I think I broke it." | Relabel: "Best case (current commitments)" / "Worst case (no action)". Add 1-sentence "Why?" tap-explainer (not hover). |
| 8 | Score numbers without adjacent verdict words | **P1** | "Is 4.8 / 10 bad?" | They re-read. | No interpretation. | Every score gets a one-word verdict in the same color box: "4.8/10 — moderate". |
| 9 | Methods modal opens to dense paragraph | **P1** | "Walls of text." | × out. | Won't read. | Add TL;DR at top: "Where the numbers come from. ⚪ EPA EJScreen ⚪ CDC ⚪ Census. Tap to dig in." |
| 10 | "Health burden composite (CDC PLACES) 3.3 / 10" | **P1** | "Composite what?" | Skip the row. | Jargon in label. | "Combined health score — 3.3/10 — moderate" (drop "(CDC PLACES)" — it's a footnote at most). |
| 11 | Asthma hospitalization row label wraps to 3 lines | **P1** | "Wall of small text." | Skip. | Visual noise. | "Asthma hospital visits — 6.7 per 10,000 (2022)" — one line, mobile-fit. |
| 12 | Climate-future section uses methods-modal language in a user pill | **P1** | "Indicators derived from..." → glaze. | × out the panel. | Reading skipped. | Replace with the 7.4-grade rewrite above. Move the technical caveat into a "ⓘ" tap. |
| 13 | Info-panel scroll position resets after interruption | **P2** | "Where was I?" | Re-scroll, re-find. | Lost their place in a 3000px panel. | `sessionStorage` the scroll offset on `scroll` event; restore on showInfo if same GEOID. |
| 14 | "Showing 2024 data (nearest available to 2026)" | **P2** | "Why do they have old data?" | Skip the pill. | Reads as broken/old. | "From 2024 (newest available)" — drop "nearest available", drop the parenthetical math. |
| 15 | Sidebar at 2920px scroll height | **P2** | "Why am I still scrolling?" | Stop scrolling. | Layer toggles buried. | Layers card first. Move Water Quality, "What the scores mean," Methods Features into the methods modal or the info panel. |
| 16 | Three weather chips burn the motion budget for novelty | **P2** | "Lots of stuff at the top." | Eye glides past. | Visual clutter. | Collapse to one chip ("AQI 47 · 6mph · 55°F"); tap to expand. |
| 17 | Print button on a phone | **P2** | "Why is this here?" | Ignore. | Confusion (low). | Already hidden on mobile in the recent CSS pass — confirm it sticks. |
| 18 | Welcome card position fights with map | **Nit** | (covered in #1, #2) | — | — | Modal-style overlay with a backdrop dim instead of floating bottom-sheet would make the persona look at it. |

---

## Three rewrites the site needs most

Each preserves CC4EJ brand voice — community-centered, plain, no moralizing. Apply through the brand-voice skill before shipping.

**1. Header tagline**
- Before: "Delaware Cumulative Impacts Map · CC4EJ" — FK 12.3
- After: "Delaware pollution map · CC4EJ" — FK 6.2
- Why: "cumulative impacts" is policy-speak. "Pollution" is what people actually search.

**2. Welcome card intro**
- Before: "This map shows cumulative environmental risk in Delaware's ~700 block groups. Pick a path:" — FK 9.1, 15 words, includes "cumulative" + "block groups" + "~700"
- After: "Find out how much pollution and health risk your Delaware neighborhood faces. Pick one:" — FK 6.4, 13 words
- Why: leads with the user's question. Drops "block group" jargon. Drops the meaningless "~700" count. (This phrasing is already in your manifest.json description — pull it forward.)

**3. Air & pollution row labels**
- Before: "PM2.5 air pollution — Above median" — FK n/a, jargon-loaded, no verdict
- After: "Tiny soot particles — Worse than most places (96th percentile)" — verdict-first, jargon translated, percentile kept as the proof
- Why: "PM2.5" is technical. "Tiny soot particles that get into your lungs" is what they are. "Above median" is meaningless without a baseline. Lead with the verdict; keep the number for the curious.

---

## Three patterns to remove

1. **The CIS "Exposure surface" floating toggle on the map.** Persona doesn't know what an exposure surface is. The toggle is competing for top-of-map attention with the search pill and the weather widgets. **Move it into the layers sidebar with the other on/off controls.** Keep the feature; lose the floating button.

2. **"Copy embed code" in the share menu on mobile.** Already hidden via the CSS pass — make sure it stays hidden. Persona has no use case for embedding an iframe from their phone.

3. **"RCP 4.5 / RCP 8.5" as button labels.** No 10th grader knows what an RCP is. Keep the data; relabel the buttons "Best case (current commitments)" / "Worst case (no action)" with the RCP code as a footnote subtitle. The "Why?" link should be a tap-open explainer, not a hover.

---

## Method notes

- Audited at iPhone 14 Pro Max emulation (430×932) in Chrome DevTools Device Mode with mobile Safari UA.
- Mapbox `load` event did not fire under the Chrome MCP debugger attachment — manually triggered via `map.fire('load')` to get the data layer rendering. **This is a test-rig artifact**, NOT a production bug. Confirmed during the original mobile-fix verification that real-browser load works correctly.
- Reading-grade calculations use the Flesch-Kincaid formula in JavaScript; reasonably accurate for body text, less reliable on 1–3 word labels (those flagged by jargon test instead).
- Decision-count audit measured visible tappable elements via `getBoundingClientRect()` and `offsetParent` — excluded micro-targets (<20×20px) and hidden inputs.
- Could NOT test in this pass: real-iPhone VoiceOver gestures, real outdoor sun contrast, real Dynamic Type at 200%, true 90-second interruption (simulated via tab-switch in DevTools). Recommend a follow-up pass on a physical iPhone before next deploy.

---

## What to do this week

If you only have 2–3 hours:

1. **Fix the decision count.** Hide weather widgets, CIS toggle, sidebar tab, time-bar behind a "Show map controls" toggle by default on first load. Reveals on first interaction OR after welcome-card dismiss.
2. **Hide the "At-risk populations" section** until the SOTA CSV gets filled (see [DATA_FOLLOWUPS.md](DATA_FOLLOWUPS.md) #1).
3. **Apply the three rewrites above** + the verdict-word pass on indicator rows. Run them through the `anthropic-skills:brand-voice` skill first.

Total impact: persona goes from "21 things to look at" to "1 question, 3 tiles, then I tap a colored area" — and once they tap, they get verdict-first scores instead of jargon. That's the path to a finished interaction.
