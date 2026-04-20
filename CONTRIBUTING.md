# Contributing to CC4EJ

Thanks for your interest in improving the CC4EJ Delaware Cumulative Impacts
Map. This project is licensed under the PolyForm Noncommercial License 1.0.0
(see `LICENSE.md`) and the curated data assets under CC BY-NC-SA 4.0 (see
`DATA_LICENSE.md`).

## Before you contribute

1. **Open an issue first** for anything larger than a typo or obvious bug fix.
   This protects your time (and the maintainer's) from PRs that would be
   closed for scope reasons.
2. **Respect the mission.** This tool exists to help Delaware residents
   understand cumulative environmental burden. Contributions that advance
   that mission are welcome; contributions that would gate functionality,
   insert tracking, or repurpose the tool for commercial extraction will be
   declined.

## Developer Certificate of Origin (DCO)

All contributions to this repository must be signed off under the
[Developer Certificate of Origin 1.1](https://developercertificate.org/).

The DCO is a lightweight, widely used statement (originated by the Linux
kernel) that you have the right to submit the contribution under the
project's license. It is not a CLA and does not transfer copyright.

By signing off on a commit, you certify the following:

> Developer Certificate of Origin
> Version 1.1
>
> Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
> 1 Letterman Drive
> Suite D4700
> San Francisco, CA, 94129
>
> Everyone is permitted to copy and distribute verbatim copies of this
> license document, but changing it is not allowed.
>
> Developer's Certificate of Origin 1.1
>
> By making a contribution to this project, I certify that:
>
> (a) The contribution was created in whole or in part by me and I
>     have the right to submit it under the open source license
>     indicated in the file; or
>
> (b) The contribution is based upon previous work that, to the best
>     of my knowledge, is covered under an appropriate open source
>     license and I have the right under that license to submit that
>     work with modifications, whether created in whole or in part
>     by me, under the same open source license (unless I am
>     permitted to submit under a different license), as indicated
>     in the file; or
>
> (c) The contribution was provided directly to me by some other
>     person who certified (a), (b) or (c) and I have not modified
>     it.
>
> (d) I understand and agree that this project and the contribution
>     are public and that a record of the contribution (including all
>     personal information I submit with it, including my sign-off) is
>     maintained indefinitely and may be redistributed consistent with
>     this project and the open source license(s) involved.

### How to sign off

Use the `-s` (or `--signoff`) flag when committing:

```sh
git commit -s -m "Fix label clipping on mobile facility popover"
```

This appends a line to your commit message like:

```
Signed-off-by: Jane Doe <jane@example.com>
```

The sign-off must use your real name (pseudonyms and "anonymous" are not
accepted) and a working email address. Commits without a DCO sign-off will
not be merged.

## License of contributions

By submitting a contribution, you agree that:

- Your code contribution is licensed under the PolyForm Noncommercial License
  1.0.0 (same as the rest of the repository).
- Your data contribution (if any) is licensed under CC BY-NC-SA 4.0.
- The maintainer may offer commercial licenses of the combined work to third
  parties and is not obligated to share that revenue with contributors unless
  a separate written agreement says so.

If you are not comfortable with the above, please do not submit a
contribution.

## Code style

- Python: PEP 8, keep scripts runnable as `python scripts/<name>.py` from the
  repo root; `requests` is the only allowed hard dependency.
- JavaScript in `index.html`: plain ES2020+, no build step, no new framework
  dependencies.
- Run scripts locally and commit refreshed JSON/GeoJSON outputs alongside the
  script changes that produced them.

## Reporting issues

Open a GitHub issue describing: what you expected, what you saw, browser +
OS, and (if possible) the neighborhood coordinates that reproduce the
problem.
