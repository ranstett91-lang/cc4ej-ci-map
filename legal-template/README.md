# Legal Template — IP protection starter kit for new tools

Copy this directory into the root of any new project you want to protect
against commercial extraction while keeping source readable. Designed for a
**$0 budget**: no lawyer, no USPTO filing, no patents.

## Anti-monetization posture

The default license (PolyForm Noncommercial 1.0.0) explicitly bars commercial
use. You keep the right to relicense commercially yourself — so when someone
with money shows up, you have a product to sell them.

## Seven free protection layers

| # | File | Protects |
|---|------|----------|
| 1 | `LICENSE.md` | Code — noncommercial copyleft-ish |
| 2 | `DATA_LICENSE.md` | Curated data — CC BY-NC-SA 4.0 |
| 3 | `NOTICE` | Third-party attribution (keeps you clean) |
| 4 | `TRADEMARK.md` | Project name and logo (common-law ™) |
| 5 | `CONTRIBUTING.md` | Contributor provenance (DCO sign-off) |
| 6 | `spdx-headers/` | Per-file license + copyright markers |
| 7 | A public GitHub push | Prior art — blocks others from patenting |

## How to apply to a new project

```sh
# From your new project's repo root:
cp -r /path/to/legal-template/. .
rm -rf legal-template  # remove the nested template copy if any

# Find-replace placeholders in the copied files:
#   <PROJECT>    -> your project's display name (e.g. "MyTool")
#   <YEAR>       -> current year or year range (e.g. "2026" or "2024-2026")
#   <YOUR NAME>  -> your legal name or company name
#   <YOUR EMAIL> -> contact email for commercial-license inquiries
#   <REPO URL>   -> e.g. https://github.com/you/project

# Add SPDX headers to every source file (see spdx-headers/)

git add LICENSE.md NOTICE TRADEMARK.md CONTRIBUTING.md DATA_LICENSE.md README.md
git commit -s -m "Add IP protection scaffolding"
git push
```

## Decision tree

```
Do you want to keep the option to monetize yourself?
├─ YES → PolyForm Noncommercial 1.0.0  (this template)
└─ NO, I just want credit → MIT or Apache-2.0 (swap LICENSE.md)

Does your tool run as a hosted SaaS that could be cloned by competitors?
├─ YES and you want it "open source" branded → consider AGPL-3.0
└─ Otherwise → keep PolyForm NC (more direct)

Are you shipping curated datasets too?
├─ YES → keep DATA_LICENSE.md (CC BY-NC-SA 4.0)
└─ NO  → delete DATA_LICENSE.md
```

## What this does NOT protect

- A bad actor ignoring the license (enforcement = lawsuit $$$; file is your
  standing to send a cease-and-desist)
- Independent reimplementation of your ideas (copyright protects expression,
  not ideas — that's what patents are for, and patents cost $15k+)
- Publicly reachable runtime secrets (API keys, Mapbox tokens — those need
  their own secret-management strategy)

## Upgrade path (for when budget grows)

- **~$350** — register the trademark with USPTO (strengthens `TRADEMARK.md`)
- **~$300** — file a provisional patent on a novel algorithm (12-month shelf
  life to decide on a full utility patent)
- **~$3–5k** — attorney-drafted EULA / commercial license template
- **~$500/yr** — form an LLC to hold the IP (caps personal liability when you
  start commercial licensing)

## Files in this template

- `LICENSE.md` — PolyForm Noncommercial 1.0.0, verbatim
- `NOTICE` — template for third-party attribution + your copyright
- `TRADEMARK.md` — common-law trademark assertion template
- `CONTRIBUTING.md` — DCO sign-off requirement
- `DATA_LICENSE.md` — CC BY-NC-SA 4.0 for curated data (optional; delete if
  code-only project)
- `spdx-headers/` — one-line snippets for JS, Python, HTML
- `README-license-section.md` — paste-into-README license banner
