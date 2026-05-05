# Accessibility Audit: CC4EJ Cumulative Impacts Map (`index.html`)

**Standard:** WCAG 2.1 AA · **Date:** 2026-05-05 · **Scope:** the single-file `index.html` (9,503 lines, the entire interactive map app)

---

## Summary

**Issues found:** 19 · **Critical:** 2 · **Major:** 9 · **Minor:** 8

The site has a strong baseline — `focus-visible`, `prefers-reduced-motion`, `aria-live` regions, an `aria-modal` dialog with focus restore, a colorblind-friendly palette toggle, an `sr-only` utility, and `font-size:16px` inputs to prevent iOS zoom. The remaining failures are concentrated in three places: (1) the methods modal does not trap focus, (2) several text/UI color combinations miss the 4.5:1 / 3:1 contrast bars, and (3) decorative emoji bleed into accessible names because `aria-hidden="true"` was applied inconsistently.

**Already in place (do not regress):**
- `<html lang="en">`, theme-color, viewport-fit safe-area
- `:focus-visible` outline (3px solid `#ffa500`, 2px offset) globally
- `@media (prefers-reduced-motion: reduce)` zeroes animations/transitions
- `.sr-only` utility used to label the geocoder
- Methods modal: `role="dialog"` + `aria-modal="true"` + `aria-labelledby` + Escape handler + focus restore to the trigger
- `role="status"` + `aria-live="polite"` on Wind/AQI/Temp/Year/Data-Year widgets
- `role="radiogroup"` on the era and scenario toggles, `role="switch"` + `aria-checked` on the CIS toggle (JS keeps `aria-checked` in sync at line 8446)
- `role="img"` + `aria-label` on inline SVG sparklines and histogram cells
- `font-size:16px` on inputs (prevents iOS Safari zoom-on-focus)
- `target="_blank"` external links carry `rel="noopener"`
- Native `<button>`/`<input type="checkbox">` everywhere — no fake-button divs

---

## Findings

### Perceivable

| # | Issue | WCAG Criterion | Severity | Recommendation |
|---|-------|---------------|----------|----------------|
| P1 | EFA-Moderate badge text `#d46b08` on `#fff3e0` measures **3.67:1** ([index.html:471](index.html:471)) | 1.4.3 Contrast (Minimum) | Major | Darken to `#a85100` (≈4.7:1) or `#9c4a00` (≈5.2:1). |
| P2 | Share-menu header `color:#888` on white at `.78rem` measures **3.79:1** ([index.html:271](index.html:271)) | 1.4.3 | Major | Use `#666` (≈5.7:1) or bump to `#555` (≈7.5:1). Same `#888` reused on `.vintage-note` ([index.html:478](index.html:478)). |
| P3 | Compare-chip hint `color:#a08000` on `rgba(255,249,228,0.95)` measures **~4.05:1** ([index.html:661,667-668](index.html:661)) | 1.4.3 | Major | Drop to `#7a5800` (≈6.0:1) — already used elsewhere on the same background. |
| P4 | Decorative emoji are **not** `aria-hidden`, so screen readers read "BLACK FLAG", "BOOKS", "DROPLET", "PRINTER", "DOWNWARDS ARROW" as part of the heading or button name. Inconsistent with the welcome card, which does wrap each emoji in `<span aria-hidden="true">`. Affected: [1956 (⚠)](index.html:1956), [1972 (⚑)](index.html:1972), [1979 (→)](index.html:1979), [1985 (💧)](index.html:1985), [1994-1999 (🔗 ↗)](index.html:1994), [2095 (⎙)](index.html:2095), [2096 (⬇)](index.html:2096), [2235 / 2330 (ℹ)](index.html:2330), [2387 (📚)](index.html:2387) | 1.1.1 Non-text Content; 4.1.2 Name, Role, Value | Major | Wrap each decorative emoji in `<span aria-hidden="true">…</span>`. For the few emoji that *are* the meaning (e.g., the ⚠ chemical-disaster swatch at [1955](index.html:1955)), give the parent an explicit `aria-label`. |
| P5 | Focus ring `#ffa500` on white panels measures **~1.98:1** ([index.html:52](index.html:52)). Required ≥3:1 for non-text contrast. | 1.4.11 Non-text Contrast | Major | Use a darker amber (`#b35900` ≈4.6:1 vs white) or pair the outline with a 2px offset of a complementary color to satisfy "adjacent color" contrast on both panel and header. The methods-close ring uses `var(--green)` and is fine. |
| P6 | Heat-day badge text `color:#8a6200` on `#fff4da` is borderline (~5.04:1). Pass — keep, but watch for any future lightening. | 1.4.3 | Minor | Note only. |
| P7 | The geocoder dropdown inherits Mapbox's default styles and has not been verified for contrast; suggestion text on white can be light grey. | 1.4.3 | Minor | Override `.mapboxgl-ctrl-geocoder--suggestion` color to `#222`. |

### Operable

| # | Issue | WCAG Criterion | Severity | Recommendation |
|---|-------|---------------|----------|----------------|
| O1 | **Methods modal does not trap Tab focus.** [openMethodsModal()](index.html:2563) moves focus to the close button and Escape closes it, but `Tab`/`Shift+Tab` can leave the modal and reach controls in the (now visually obscured) sidebar. `aria-modal="true"` is set but not behaviorally enforced. | 2.4.3 Focus Order; 2.1.2 No Keyboard Trap (positive form) | **Critical** | Add a focus-trap: on `keydown` `Tab` while modal is open, if focus is on the last tabbable element move it to the first (and reverse for Shift+Tab). Reference list: `methods-close`, every `<summary>`, every `<a>` inside `.methods-body`, the close button again. |
| O2 | **No skip link.** Keyboard users must Tab through ~12 header + sidebar controls (Methods, Share, the share menu inputs, geocoder, Layers toggle, every checkbox) before reaching the map and time-bar. | 2.4.1 Bypass Blocks | **Critical** | Add a visually-hidden skip link as the first focusable element: `<a class="sr-only-focusable" href="#map">Skip to map</a>`. Reveal on focus. The map container at [index.html:1713](index.html:1713) already has an `id`. |
| O3 | **Overlays popover** at [index.html:2335](index.html:2335) is `role="dialog"` but has no `aria-modal`, no focus management on open, and only closes on Escape — focus is *not* moved into the popover or back to the trigger. | 2.4.3 Focus Order; 4.1.2 | Major | Either (a) drop `role="dialog"` and treat it as a disclosure-style menu (just `aria-expanded` on the trigger, which is already there), or (b) move focus to the first checkbox on open and back to `#overlays-btn` on close. Option (a) is closer to the actual UX. |
| O4 | Mapbox block-group polygons are not keyboard-reachable. Tab order skips the map; only mouse/touch can open the info panel for a neighborhood. | 2.1.1 Keyboard | Major | Add a hidden, keyboard-focusable list of block groups (e.g., `<select>` or `<ul>` of buttons) that calls the same `showInfo()` handler. Or surface "Jump to Claymont" / address search as the supported keyboard path and document it in the welcome card. |
| O5 | Several × close buttons measure under 44×44 — `#welcome-dismiss` (~24×24, [1724](index.html:1724)), `#sidebar-close` (~28×28, [1721](index.html:1721)), `#info-close` (~24×24, [427](index.html:427)), `#compare-chip-clear` (~24×24, [2085](index.html:2085)). The methods-close at [181-191](index.html:181) is correctly 44×44. | 2.5.5 Target Size (AAA — note: WCAG 2.2's 2.5.8 minimum is 24×24, which these meet) | Minor | This is a mobile-first site; matching the methods-close pattern (44×44, slight grey background) on all four buttons would be consistent and prevent fat-finger frustration. Not required for AA strict, but recommended given Roby's mobile audit context. |
| O6 | Welcome-card emoji + dismiss button overlap on small viewports — the × is positioned `top:6px;right:8px` over the heading, which is fine, but the touch target is only 24×24. | 2.5.5 / 2.5.8 | Minor | Bump `padding` to at least `8px 10px`. |

### Understandable

| # | Issue | WCAG Criterion | Severity | Recommendation |
|---|-------|---------------|----------|----------------|
| U1 | Heading hierarchy jumps `h1` → `h3` (the sidebar cards). The `h2` elements live inside the conditional info-panel and methods-modal. | 1.3.1 Info & Relationships; 2.4.6 Headings & Labels | Major | Promote sidebar-card `h3`s ("Map Features", "Show impact types", "Claymont Focus", "Water Quality", "Combined Burden", "What the scores mean") to `h2`. Promote the `h4` sub-headings inside the info-panel to `h3` to match. |
| U2 | The `h2#info-name` block is populated dynamically when a user clicks a block group ([index.html:2098](index.html:2098)). It is not in a live region, so screen reader users hearing the click handler open the panel will not be told the new neighborhood name unless they re-navigate. | 4.1.3 Status Messages; 1.3.1 | Major | Wrap the dynamic content under `<div role="region" aria-live="polite" aria-labelledby="info-name">`, or programmatically move focus to the panel's heading (with `tabindex="-1"`) on open. The `info-data-year` `aria-live` already exists nearby — extend the pattern. |
| U3 | The colorblind toggle [index.html:1963](index.html:1963) communicates its purpose only via the parent `<label>`'s `title="Switches facility + burden colors to an Okabe-Ito deuteranopia/protanopia-safe palette."`. `title` is unreliable on touch and inconsistent across screen readers. | 3.3.2 Labels or Instructions | Minor | Add visible help text or move the explanation into an `aria-describedby` `<span class="sr-only">`. |
| U4 | `target="_blank"` external links do not announce that they open in a new tab beyond a trailing `↗` glyph that is itself read aloud. | 3.2.4 Consistent Identification (advisory) | Minor | Add `<span class="sr-only">(opens in new tab)</span>` to external links, or set `aria-label` on each. |

### Robust

| # | Issue | WCAG Criterion | Severity | Recommendation |
|---|-------|---------------|----------|----------------|
| R1 | `<div id="compare-chip" role="status">` ([2082](index.html:2082)) contains a focusable `<button>` (clear). ARIA spec says `status` must not have interactive descendants — assistive tech may suppress the button's announcement. | 4.1.2 Name, Role, Value | Major | Move the `role="status"` and `aria-live` onto a sibling `<span>` that holds only the text, and let the button live outside. Or replace the button with a non-focusable element and a global keyboard shortcut. |
| R2 | `<div class="methods-card" role="document">` ([2384](index.html:2384)) — `role="document"` is non-standard outside an `application` context and has been removed from many AT support matrices. | 4.1.2 | Minor | Drop the role; `<div class="methods-card">` is enough. |
| R3 | The page wraps content in `<div id="main">` ([1713](index.html:1713)) — there is no `<main>` landmark. Screen reader users have no "main content" landmark to jump to (the `<nav>` exists, but no main). | 1.3.1; 4.1.2 | Minor | Change `<div id="main">` to `<main id="main">`. Free landmark. |

---

## Color Contrast Check (computed)

| Element | Foreground | Background | Ratio | Required | Pass? |
|---------|-----------|------------|-------|----------|-------|
| Body text | `#1a1a1a` | `#f8f7f4` | 16.4:1 | 4.5:1 | ✅ |
| Header label | `white` | `#2d6a4f` | 5.80:1 | 4.5:1 | ✅ |
| Muted text `--muted` | `#555` | `#f8f7f4` | 6.51:1 | 4.5:1 | ✅ |
| Share-menu header | `#888` | white | **3.79:1** | 4.5:1 | ❌ (P2) |
| Vintage-note | `#888` | white | **3.79:1** | 4.5:1 | ❌ (P2) |
| EFA-Significant | `#b5000c` | `#fde8e8` | 6.43:1 | 4.5:1 | ✅ |
| EFA-Moderate | `#d46b08` | `#fff3e0` | **3.67:1** | 4.5:1 | ❌ (P1) |
| EFA-Not-EFA | `#2d6a4f` | `#e8f5e9` | 6.05:1 | 4.5:1 | ✅ |
| Era-postwar chip | `#2d6a4f` | `#e7f2ec` | 5.96:1 | 4.5:1 | ✅ |
| Compare-chip hint | `#a08000` | ~`#fff9e4` | **~4.05:1** | 4.5:1 | ❌ (P3) |
| Water-quality link | `#1a4e8b` | `#e8f4fc` | 7.14:1 | 4.5:1 | ✅ |
| Help-badge text | `#6b5a1a` | `#f0e9d8` | 5.52:1 | 4.5:1 | ✅ |
| Focus ring | `#ffa500` | white | **1.98:1** | 3:1 (non-text) | ❌ (P5) |
| Focus ring | `#ffa500` | `#2d6a4f` (header) | 2.93:1 | 3:1 | ❌ borderline (P5) |

---

## Keyboard Navigation

| Element | Tab Order | Enter/Space | Escape | Notes |
|---------|-----------|-------------|--------|-------|
| Header `Methods` button | ✅ in order | ✅ opens modal | n/a | `aria-label` set |
| Header `Share` button | ✅ | ✅ opens menu | ❌ doesn't close menu | Menu closes only on outside click |
| Geocoder input | ✅ | ✅ submits | n/a | `sr-only` label present |
| Sidebar `Layers` toggle | ✅ | ✅ | n/a | mobile-only |
| Sidebar checkboxes | ✅ | ✅ Space toggles | n/a | All implicit-labelled |
| Era/year chips | ✅ | ✅ activates | n/a | Native `<button>` |
| Overlays `Layers` button | ✅ | ✅ | ✅ closes popover | But focus not moved into popover |
| Methods modal | first focus on close × | ✅ | ✅ closes | ❌ **focus not trapped (O1)** |
| Map polygons | ❌ skipped | ❌ | n/a | Mapbox limitation (O4) |
| × close buttons (info, compare-chip-clear, sidebar-close, welcome-dismiss) | ✅ | ✅ | n/a | Sub-44 target size (O5) |

---

## Screen Reader Spot-Checks

| Element | Likely Announcement | Issue |
|---------|---------------------|-------|
| `<h2 id="methods-title">📚 Data & Methods</h2>` | "BOOKS Data and Methods, heading 2" | Emoji not aria-hidden (P4) |
| `<h3>⚑ Claymont Focus (ZIP 19703)</h3>` | "BLACK FLAG Claymont Focus…" | Same (P4) |
| `<button>⎙ Print</button>` | "PRINTER Print, button" | Same (P4) |
| `<a>🔗 EWG — Veolia NCC Tap Water (DE0000564) ↗</a>` | "LINK SYMBOL EWG dash Veolia NCC Tap Water DE0000564 NORTH EAST ARROW, link" | Same (P4) plus no "opens in new tab" cue (U4) |
| Block-group click → info panel opens, populates `#info-name` with neighborhood | Silent — no live region; user has to navigate to panel | U2 |
| Wind/AQI/Temp widgets update on map move | "Wind 12 mph from northwest" — fires correctly | ✅ working |
| Year-chip click | "2024" announced via `aria-live` on `#yr-label` | ✅ working |
| CIS toggle activated | "Exposure surface, switch, on" | ✅ working — `aria-checked` updated by JS |

---

## Priority Fixes

1. **Trap focus inside the methods modal (O1).** `aria-modal="true"` is a contract; not enforcing it confuses keyboard users and screen readers. ~15 lines of JS.
2. **Add a "Skip to map" link (O2).** First focusable element, `sr-only` until focused. The map already has `id="main"` to target.
3. **Mark decorative emoji `aria-hidden` everywhere, not just in the welcome card (P4).** Highest-volume fix; biggest impact for screen reader users. The pattern is already established in the welcome tiles.
4. **Fix the four contrast failures (P1, P2, P3, P5).** Adjust six hex values:
   - `#d46b08` → `#a85100` (EFA-Moderate text)
   - `#888` → `#666` (share-menu header, vintage-note)
   - `#a08000` → `#7a5800` (compare-chip hint)
   - Focus ring `#ffa500` → `#b35900` (or pair with a complementary inner outline)
5. **Promote sidebar `h3`s to `h2` (U1).** Restores heading hierarchy.
6. **Make the dynamic info-panel announce itself (U2).** Either move focus to `#info-name` or wrap the panel in `aria-live="polite"`.
7. **Move `role="status"` off `#compare-chip` to a text-only sibling (R1).**
8. **Change `<div id="main">` to `<main id="main">` (R3).** Free landmark.
9. **Decide whether the overlays popover is a dialog or a menu (O3).** Pick one model and apply it consistently.

Items 1–3 are the biggest wins for the smallest effort. Item 4 is a 6-line CSS change. Item 8 is a one-character change.

---

## Notes Outside the WCAG Scorecard

- **Mapbox keyboard accessibility (O4)** is a known industry-wide gap. The "Jump to Claymont" red button + the geocoder cover the keyboard happy-path, but a screen reader user cannot browse arbitrary block groups. Surfacing a hidden `<select>` of all DE block groups (already in `de_blockgroups.geojson`) and wiring its `change` event to `showInfo()` would close this gap with low complexity.
- **The reduced-motion media query** is excellent and rare to see — keep it.
- **`font-size: 16px` on inputs** prevents iOS zoom-on-focus and is the right call for a mobile-first site. Nice touch.
- **The `Okabe-Ito` colorblind palette toggle** is genuinely above-and-beyond; the WCAG 2.1 AA requirement is "info not conveyed by color alone," and your impact-swatch letters (`C`, `R`, `S`, `W`, `T`, `A`) already satisfy that. The toggle is icing.
