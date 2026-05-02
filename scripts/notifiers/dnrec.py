# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""
DNREC scrapers — Delaware-only public-notice + SIRS sources.

These are HTML scrapers and the most fragile of the bunch. Both pages
follow simple list-of-rows layouts; selectors will need updating when
DNREC redesigns.

Sources:
  - DAQ public notice archive (air-quality permits, exceedances)
  - DAQ public notice current page
  - SIRS site list (DNREC hazardous-substance cleanup tracker)

Only fires for state == "DE".
"""

from __future__ import annotations

import hashlib
import re

from .base import Alert, http_get_text

SOURCE_PUBLIC_NOTICES = "dnrec_public_notices"
SOURCE_SIRS = "dnrec_sirs"

PUBLIC_NOTICE_PAGES = [
    "https://dnrec.delaware.gov/dnrec-public-notices/",
    "https://dnrec.delaware.gov/dnrec-public-notices/daq-archive/",
]
SIRS_LIST_URL = "https://dnrec.alpha.delaware.gov/waste-hazardous/remediation/sirs/"


_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', re.IGNORECASE)
_DATE = re.compile(r'\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b')


def _hash(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def _scrape_public_notices() -> list[Alert]:
    alerts: list[Alert] = []
    for page in PUBLIC_NOTICE_PAGES:
        try:
            html = http_get_text(page)
        except RuntimeError:
            continue
        for href, text in _LINK.findall(html):
            text = text.strip()
            if not text or len(text) < 8:
                continue
            # Heuristic: notices reference permits / exceedances / hearings
            if not re.search(r"(permit|notice|exceedance|hearing|notification|consent|CERCLA|RCRA)",
                             text, re.IGNORECASE):
                continue
            absolute = href if href.startswith("http") else "https://dnrec.delaware.gov" + href
            date_match = _DATE.search(text)
            alerts.append(Alert(
                source=SOURCE_PUBLIC_NOTICES,
                id=f"dnrec_pn:{_hash(absolute, text)}",
                title=f"DNREC public notice: {text[:200]}",
                body="",
                url=absolute,
                date=(date_match.group(1) if date_match else ""),
                state="DE",
            ))
    return alerts


def _scrape_sirs() -> list[Alert]:
    try:
        html = http_get_text(SIRS_LIST_URL)
    except RuntimeError:
        return []
    alerts: list[Alert] = []
    for href, text in _LINK.findall(html):
        text = text.strip()
        # SIRS links typically point to site-detail pages on the DNREC domain.
        if "sirs" not in href.lower() and "remediation" not in href.lower():
            continue
        if len(text) < 6:
            continue
        absolute = href if href.startswith("http") else "https://dnrec.alpha.delaware.gov" + href
        alerts.append(Alert(
            source=SOURCE_SIRS,
            id=f"sirs:{_hash(absolute, text)}",
            title=f"DNREC SIRS site: {text[:200]}",
            body="",
            url=absolute,
            date="",
            state="DE",
        ))
    return alerts


def fetch(states: set[str]) -> list[Alert]:
    if "DE" not in states:
        return []
    return _scrape_public_notices() + _scrape_sirs()
