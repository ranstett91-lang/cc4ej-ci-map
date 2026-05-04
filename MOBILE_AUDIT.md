# CC4EJ Delaware Cumulative Impacts Map — Mobile Audit

**Audited:** 2026-05-03 · iPhone 14 Pro Max emulation in Chrome DevTools (Device Mode), viewport effective 331×690 in DevTools-docked layout (more aggressive than iPhone SE — findings hold conservatively for 375 and up). Mobile Safari UA, DPR 3, touch UA. Page served from `python3 -m http.server 8765`. Service worker registered, manifest linked.

**Audience for findings:** porch-standing Claymont resident, EJ door-knocker, on-site journalist, transit-reading staffer.

---

## TL;DR (mobile)

- **Biggest mobile win:** the info panel content itself — Pollution Burden / Vulnerability / Combined Burden / "PROXIMITY BURDEN — THIS EXACT LOCATION" with a wind-adjusted tag and a plain-English health-risk paragraph is **legitimately powerful for a non-expert** and reads well at phone width.
- **Biggest mobile-blocking problem:** the **Claymont quick-fly button is rendered inside the closed sidebar at x=-291** — invisible to first-time Claymont visitors, the primary audience. Combined with the welcome card also living inside the closed sidebar, a Claymont resident loading the site sees no path to "show me my neighborhood."
- **Biggest "is this worth keeping on mobile?" question:** **"Copy embed code"** in the share menu and the **two paint-mode buttons** (National vs DE-local) — neither has a believable mobile use case. The embed button is desktop-think; the paint-mode toggle is an analyst control most porch users won't understand.

---

## Findings table

| # | Feature | Severity | Axis | Viewport | Observed | What a real user feels | Fix |
|---|---------|----------|------|----------|----------|------------------------|-----|
| 1 | **Welcome card hidden on first load** | P0 | Usability | all | `#welcome-card` is inside `#sidebar`, which starts closed (`translateX(-100%)`). User sees map + weather chips with no orientation prompt. | "What is this? What do I do?" — bounce. | Render the welcome card as a bottom sheet or overlay that appears OUTSIDE the sidebar on first visit (`localStorage.cc4ej-welcome-dismissed` is already wired). |
| 2 | **Claymont fly-to button is offscreen** | P0 | Value | all | `[onclick="flyToClaymont()"]` rect.x = **-291** (lives in the closed sidebar). | The Claymont audience — the people the site is named for — can't find their own neighborhood without first tapping Layers. | Hoist a "Jump to Claymont" pill into the welcome card AND keep a duplicate inside the sidebar. |
| 3 | **Share URL preserves zero state** | P0 | Value | all | After `flyToClaymont()`, `#share-url-input.value` and `location.hash`/`location.search` remain bare `index.html`. | Resident shares "their" neighborhood; recipient sees default Delaware. The whole "look at this!" loop is broken. | Encode lat/lng/zoom/selected BG/active layers/year/scenario into a URL hash on every state change; rehydrate on load. Without this, the share menu is theater. |
| 4 | **H1 title clipped to 3 lines / 112px** | P0 | Usability | 331–393 | "Is My Neighborhood Safe?" rendered in a 112×54px column next to logo, wraps to 3 lines, "Saf..." gets truncated. | The page's tagline — its single best framing — is unreadable. | At <420px: drop the logo to 24px, give the H1 the full remaining width (≈260px), single line at smaller font. Or ditch the H1 from the header on mobile and put it in the welcome card. |
| 5 | **Open sidebar translates to x=-35** | P0 | Usability | 331 | When `#sidebar.open` is applied at narrow widths, computed transform is `translateX(-35.02px)` instead of `0`. Card padding starts at x=-6 — first character of every line is clipped. | Sidebar looks "broken" — half-words. Trust falls. | The transform math assumes a min viewport; clamp `translate` to `max(0, computed)` or switch to `right: 0` on the open state. |
| 6 | **Compare chip is invisible (z-index trapped under timeline)** | P0 | Usability | all | After pinning, `#compare-chip` has `display:flex, opacity:1, rect.y=556` — but the time-bar starts at y=549 and covers it. | User taps "+ Compare", info panel disappears, nothing happens visibly. The compare flow dies silently. | Move the chip to top-of-map (under the geocoder), or raise z-index above time-bar AND ensure the time-bar reserves space below it. |
| 7 | **All layer checkboxes are 14×14px** | P0 | Usability/A11y | all | 11 checkboxes (chemical, refinery, contamination, air, traffic, ag, warehouse, disasters, community names, colorblind, master). Label rows are 232×16–32px tall — wide but height-starved. | Mis-taps; user toggles the wrong layer; gives up on layer control. WCAG 2.5.5 Target Size fail; Apple HIG 44pt fail. | At <600px, swap to full-width row buttons with the swatch+label and a checkmark, min-height 44pt. Or use iOS-style switches. |
| 8 | **Info panel `×` close button is 11×19px** | P0 | Usability/A11y | all | Single tiny "×" at top-right of a panel that covers the entire viewport. No swipe-to-dismiss, no drag handle, no tap-outside-to-close. | User can't easily get rid of the info panel to see the map again. Frustration after every tap. | (a) Add a 4–6px drag handle on top + native sheet drag-to-dismiss. (b) Bump × to 44×44 with hit area. (c) Tapping the small map sliver visible at top should dismiss. |
| 9 | **Info panel covers the entire viewport (331/331)** | P1 | Usability | all | Panel rect: 0,151 → 331,690. The block group the user just tapped is invisible while reading about it. | Loses the spatial "I tapped HERE" anchor. Especially bad in the compare flow where two BGs need to be visualized. | Make the panel a half-sheet by default (60% viewport height), full-sheet only after user drag. Standard iOS sheet pattern. |
| 10 | **Info panel scroll height 3036px / clientHeight 538px** | P1 | Value | all | 5.6× viewport-equivalent of scroll inside the panel. EFA, climate-historical, climate-future, proximity, EJScreen, CDC PLACES, etc. | Important sections (climate-future, EFA) are buried below the fold. Most users never scroll that far. | Ruthlessly prioritize the top 700px: scores + proximity + plain-English summary. Move EJScreen detail to an "expand" affordance. |
| 11 | **2050 SCENARIO row appears below the viewport (y≈770)** | P0 | Usability | 331–430 | After `jumpToYear(2050)`, the "Moderate RCP 4.5 / High RCP 8.5 / Why?" row is rendered at y≈770, below the 690px viewport. User must scroll the whole page to use it. | User taps 2050 → sees no scenario picker → assumes there's nothing to choose → misses the point of the future-projection feature. | Bring the scenario row above the timeline scrubber, OR render it as an overlay anchored to the year button. |
| 12 | **Climate jargon "RCP 4.5 / RCP 8.5"** | P1 | Value | all | Buttons labeled "Moderate RCP 4.5" / "High RCP 8.5" in the 2050 scenario picker. | Most residents don't know what RCP means. The tooltip is a "Why?" link, but tooltips aren't reachable on touch. | Relabel: "Moderate (current commitments)" / "High (no further action)". Keep RCP as fine print. Make "Why?" a tap-open explainer not a hover. |
| 13 | **Methods modal Escape key doesn't close it** | P2 | A11y | all | Modal opens, ×=44×44 ✓, but `keydown Escape` doesn't dismiss. | Keyboard/external-keyboard iPad users stuck. WCAG 2.1.1. | `addEventListener('keydown', e => e.key === 'Escape' && closeMethodsModal())`. Also add backdrop tap-to-dismiss. |
| 14 | **Two × close buttons stacked at top-left of open sidebar** | P2 | Usability | all | The sidebar has its own × at top-right and the welcome card has its own × inside. Both visible simultaneously. | Confusion: which one closes what? | Drop the welcome card's × — let dismissal be one of the three orientation tiles ("Got it"). Or hide the welcome card automatically once user opens the sidebar. |
| 15 | **Redundant "What is this map?" card** | P2 | Value | all | After "START HERE" card with 3 tiles, the very next sidebar card "WHAT IS THIS MAP?" repeats the same orientation in numbered form. ~275px more vertical space. | Two answers to the same question = neither feels authoritative. Sidebar feels long. | Merge into one card or move "What is this map?" into the Methods modal. |
| 16 | **Sidebar is 2920px scroll height (9 cards)** | P1 | Usability | all | Open sidebar, scroll for days. Cards include Map Features, Show impact types, Claymont Focus, Water Quality (431px!), Combined Burden legend, What the scores mean (444px), Map Features again. | User opens Layers expecting to toggle layers, gets a tour of the entire app. Toggles are buried 1000+px down. | Sidebar = layers control only. Move Water Quality, "What the scores mean," score legend into separate flows (info panel, methods modal, on-map legend). |
| 17 | **Weather widgets occlude top of map (~75–100px)** | P1 | Value | all | Wind + AQI + temp stack vertically at the top of the map. Three rows. CIS toggle + "Showing conditions near…" caption overlap them. | A. Map is shorter than it should be. B. The widgets aren't useful enough to a porch-standing user (who already knows it's windy) to earn that space. | Collapse to a single chip ("AQI 47 · 6mph · 55°F") that opens detail on tap. Reclaim ~70px of map. |
| 18 | **CIS "Exposure surface" toggle visually overlaps weather chips** | P1 | Usability | all | CIS toggle at y=174–200; weather widgets at y=102–190; horizontal AND vertical overlap. | Looks broken. The CIS feature is hard to discover when it's tangled with weather. | Move CIS toggle into the layers sidebar where toggles live. The on-map placement is desktop-think. |
| 19 | **Address geocoder suggestion dropdown** | P1 | Usability | all | Geocoder input is 311×42 ✓, but its suggestion dropdown drops down INTO the weather-widget zone — partially obscured by wind/AQI/temp chips. | Suggestions clipped or unclickable. Address-search flow breaks. | When geocoder has focus, hide weather widgets temporarily; or float suggestions with z-index above everything. |
| 20 | **Mapbox tiles network-only — basemap is broken offline** | P1 | Value | all | `sw.js` explicitly excludes `mapbox`/`tiles` hostnames from caching. App data caches; tiles don't. | PWA installed, taken to a no-signal location, opens to a blank/gray map with floating colored polygons. | Cache a small set of zoomed-out tiles for the Delaware bbox at install time. Or use Mapbox offline regions API. Without this, the PWA promise is hollow. |
| 21 | **Open-Meteo weather network-only — widgets break offline** | P2 | Value | all | Same SW exclusion. | Offline = no weather chips. Acceptable, but show a "no data" state instead of vanishing. | Stale-while-revalidate with a max-age, show cached value with a "last updated" timestamp. |
| 22 | **No safe-area-inset CSS (notch/home-indicator)** | P1 | Usability | all | `viewport-fit=cover` declared, `apple-mobile-web-app-status-bar-style=black-translucent` (content goes behind status bar) — but no `--sat/--sab` CSS vars or `env(safe-area-inset-*)` usage. Header padding-top fixed 8px. Body padding-bottom 0. | When installed as PWA: header sits under Dynamic Island; time-bar sits under home indicator → bottom buttons hard to tap. | Add `padding-top: max(8px, env(safe-area-inset-top))` to header and equivalent on bottom of `#time-bar`. Test on installed PWA. |
| 23 | **Time-bar hugs viewport bottom (y=549–684)** | P1 | Usability | 331–430 | Climate scrubber buttons (1875/1920/1970/2016/2020/2024/2050/Now) live at y=549–684. Combined with no safe-area-bottom, on iPhone X+ they sit under the home indicator gesture zone. | Mis-swipes go to "go home" instead of changing year. | (a) Add safe-area-bottom padding. (b) The scrubber is also a busy 7-button bar — consider collapsing into a single year chip + on-tap full-screen year picker. |
| 24 | **Climate scrubber buttons 22–30px tall** | P1 | A11y | all | Year buttons (2016/2020/2024) = 22×46. Era buttons (1875/1920/1970/2050) = 30×55. | Below 44pt. Mis-taps. | Min-height 44pt. Reduce button count if needed (Now + a slider would be more honest about the data being a continuous time axis). |
| 25 | **Compare/Print/Report buttons in info panel: 25px tall** | P1 | A11y | all | Three buttons row at top of info panel, each ~57–78×25px. | Cramped row, easy to mis-tap. | Min-height 44pt. Drop "Print" on mobile (no one prints from a phone) — keep Compare and Report (Report on iOS triggers Files save). |
| 26 | **"Copy embed code" in share menu** | P2 | Value | all | Visible in mobile share sheet. | Nobody embeds an iframe from their phone. Pure desktop-think. | Hide on mobile (show only Copy URL + Native share). |
| 27 | **Body muted text 11.5–12.5px** | P1 | A11y | all | `#info-county` 12.48px, `#prox-note` 11.68px, `#prox-interp` 11.68px, `#info-data-year` 11.52px. Below the recommended 14px mobile-body minimum. Outdoor sun: probably illegible. | Critical context ("wind-adjusted", "Very High — extreme clustering of industrial sources at close range") becomes squint-text. | Bump muted text to 14px; bump body to 16px. Increase line-height. |
| 28 | **`#prox-interp` contrast borderline** | P2 | A11y | all | `color: rgb(119,119,119)` on `rgb(245,242,236)` ≈ 4.4:1. WCAG AA needs 4.5:1 for normal text. | Fails AA by a hair; outdoors it fails by a mile. | Darken to #555 (≈6.9:1) — already used elsewhere. |
| 29 | **No haptic / no scroll-snap on year scrubber** | Nit | Usability | all | The scrubber doesn't use scroll-snap or any iOS-native gestures. | Feels web-y, not native. | Optional — would make it feel more like the app reference. |
| 30 | **Welcome card persistence works ✓** | — | — | all | `localStorage.cc4ej-welcome-dismissed` correctly persists the dismissal. | (positive finding) | Keep. |

---

## Thumb-reach map (right-handed, one-handed grip on iPhone 14 Pro)

```
┌─────────────────────────┐  y=0
│ logo  H1(clipped)  Methods Share  │ ← stretch zone (top right corner)
├─────────────────────────┤  y=70
│ [geocoder full width]            │ ← thumb-reachable
├─────────────────────────┤
│ wind chip                        │
│ AQI chip       CIS toggle        │ ← stretch zone (top half)
│ temp chip                        │
│ "Showing conditions near…"       │
├─────────────────────────┤
│                                  │
│         MAP                      │
│                              [+] │ ← stretch zone (right edge)
│                              [-] │
│ Layers                           │ ← thumb zone if right-handed (LEFT edge!)
│  (vertical                       │   ← but Layers tab is LEFT-edge — bad for right-thumb users
│   tab)                           │
│                                  │
│ ┌─Combined Burden legend─┐       │ ← thumb zone
│ └────────────────────────┘       │
├─────────────────────────┤  y=549
│ era buttons | year buttons       │ ← thumb zone (bottom, but cramped)
│ Now    [hamburger]               │
├─────────────────────────┤  y=690 (viewport bottom)
│ 2050 SCENARIO ROW (BELOW FOLD)   │ ← unreachable without scroll
└─────────────────────────┘
```

**Key reach problems:**
- **Methods + Share buttons (top right)** — both require a stretch. Methods icon is 39×29 (below 44pt) and is the key trust-builder for the site.
- **Layers tab on LEFT edge** — fine for left-handed users, unreachable thumb-without-grip-shift for right-handed (~80% of users).
- **CIS toggle floating top-right of map** — stretch zone, and overlapping weather widgets.
- **Map zoom +/− on right edge** — stretch, but acceptable since pinch-zoom usually replaces them.

---

## Outdoor-readability findings

This app gets used outside, in sunlight, on cellular. The font-size and contrast issues compound:

- Body muted text at 11.5–12.5px in low-contrast grays (#555, #777, #8a6200) — **borderline indoors, illegible outdoors.**
- Score swatches (red gradient on legend, score-box backgrounds) rely on color alone to communicate severity. Colorblind mode exists ✓ but isn't surfaced — it's buried in the sidebar with a tiny 14×14 checkbox.
- Map polygon colors at the lighter end of the burden ramp (yellow-orange) wash out in bright sun, making "moderate" indistinguishable from "low."
- The amber "Showing 2024 data (nearest available to 2026)" tag uses #8a6200 on #fff4da — about 5.0:1, passes AA indoors, fails outdoors.

**Recommendation:** add an outdoor/high-contrast mode that bumps all body text to 16px+, switches muted text to near-black, and uses a higher-contrast burden ramp (white→deep red, skip the yellow midtones).

---

## PWA + offline findings

- Manifest: name, short_name, description, theme_color, 192/512 maskable icons all set ✓
- iOS apple-mobile-web-app meta tags set ✓
- Service worker registered, scope correct ✓
- Network-first for HTML/JSON/GeoJSON with cache fallback ✓ — **app shell + data work offline**
- **Mapbox tiles excluded from cache** — basemap broken offline (P1 for a field tool)
- **Open-Meteo excluded from cache** — weather chips silently disappear offline (P2)
- No `beforeinstallprompt` handling visible in HTML — PWA install must come from Safari "Add to Home Screen" menu, not surfaced in-app
- No "you are offline" UI state — broken map looks like a bug, not a known offline limitation
- **Welcome dismiss persistence ✓** survives reload via localStorage

---

## iOS VoiceOver + Dynamic Type findings

(Inferred from DOM structure — true VoiceOver pass requires real device, not DevTools emulation)

- `lang="en"` ✓, single H1 ✓, most interactive elements have `aria-label` ✓
- Geocoder has `<label class="sr-only">` ✓
- Sidebar `aria-label="Map controls and information"` ✓
- Wind/AQI/temp widgets have `role="status" aria-live="polite"` ✓ — VoiceOver will announce updates (good but possibly chatty)
- One button without an accessible name detected (likely the Mapbox geocoder Clear button — vendor)
- `paint-mode-toggle` uses `role="radiogroup"` ✓
- **Tap targets fail WCAG 2.5.5** at 14px checkboxes, 11–25px buttons (multiple — see findings 7, 8, 24, 25)
- **Text contrast borderline AA** for `#prox-interp` (finding 28)
- **Dynamic Type not tested** — but with 11.5px starting size, 200% Dynamic Type would push it to 23px which would break layouts assuming fixed sizes (the H1 truncation suggests rigid widths). Likely several layout breaks at large text sizes.

---

## Features that earn their keep on mobile

Don't cut these:

1. **Info panel core** — Pollution Burden / Vulnerability / Combined Burden / "PROXIMITY BURDEN — THIS EXACT LOCATION" with wind-adjusted tag and plain-English health-risk summary. **This is the product.** It works.
2. **The proximity burden formula** — showing `(10.0 × 3.3) ÷ 10 = 3.3` builds trust by being legible math.
3. **"Showing 2024 data (nearest available to 2026)"** vintage caption — exactly the right level of honesty.
4. **Weather widgets disappearing for historical years (1875)** — context-aware UI, smart.
5. **Methods modal density** — looks credible to a skeptical reader (EJScreen, Census, ACS, RMP all cited).
6. **Native share button** — works correctly via `navigator.share`.
7. **Colorblind mode option** — exists and persists ✓ (but is buried — see findings).
8. **Time-axis concept** (1875 → 2050) — bold and value-add. Just needs UI rework.
9. **Service worker for app shell + data** — solid foundation.

---

## Features I'd hide or strip on mobile

- **Copy embed code** in share menu — desktop-only.
- **Print button** in info panel — no one prints from a phone; iOS share sheet covers PDF saves.
- **Two paint-mode buttons** (National vs DE-local) — analyst feature; default to one and offer the other inside Methods.
- **CIS Exposure Surface toggle** as a top-of-map floating button — move into Layers sidebar with the other toggles.
- **Stacked weather widgets** — collapse to one chip.
- **"WHAT IS THIS MAP?" sidebar card** — redundant with welcome card; merge or delete.

---

## Three highest-leverage mobile changes

If you do nothing else:

1. **Fix the Claymont/welcome path on first load.** Hoist the welcome card and the Claymont fly button OUT of the closed sidebar so a Claymont resident's very first interaction can be "show me my neighborhood." (Findings #1, #2.)
2. **Make the share URL preserve state** — encode lat/lng/zoom/selected BG/year/scenario into the hash. Without this, every share is a misfire and the entire share menu is theater. (Finding #3.)
3. **Bump every interactive target to 44pt and bump muted body text to 14px.** Fixes findings #4, #7, #8, #24, #25, #27 simultaneously. Single CSS pass.

---

## Method notes

- Audit was driven via Chrome MCP with DevTools Device Mode (debugger attached, so interactions used DOM/JS dispatch rather than synthetic clicks — Mapbox click handlers were exercised via `map.fire('click', …)`).
- Could not verify on real iOS hardware (would catch: actual `navigator.share` UX, install-PWA flow, real safe-area inset behavior, real outdoor sun contrast, VoiceOver gesture-by-gesture, large Dynamic Type). Recommend a follow-up pass on a physical iPhone before next deploy.
- Could not test true offline — DevTools network throttling unavailable while debugger attached. Offline behavior inferred from `sw.js` source.
- Performance: DOM ready in 137ms, 250 resources, 37KB transfer (with cache warm), 33MB JS heap. No regressions found; mobile perf is fine.
