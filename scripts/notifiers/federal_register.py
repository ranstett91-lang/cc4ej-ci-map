# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""
federalregister.gov public-API source.

Catches CERCLA Records of Decision, RCRA permit notices, EPA cleanup actions,
and DNREC Federal Register submissions that mention any target state.

API docs: https://www.federalregister.gov/developers/documentation/api/v1
No auth required. We narrow by EPA agency + topic keywords + state.
"""

from __future__ import annotations

from datetime import date, timedelta

from .base import Alert, http_get_json

SOURCE = "federal_register"
ENDPOINT = "https://www.federalregister.gov/api/v1/documents.json"
LOOKBACK_DAYS = 60   # generous; client-side dedupe handles repeats

KEYWORDS = [
    "CERCLA", "Superfund", "Record of Decision",
    "RCRA", "Corrective Action", "Hazardous Waste",
    "Remedial Action", "Consent Decree",
]

STATE_NAMES = {"DE": "Delaware", "PA": "Pennsylvania", "NJ": "New Jersey", "MD": "Maryland"}


def fetch(states: set[str]) -> list[Alert]:
    since = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    alerts: list[Alert] = []

    for st in states:
        state_name = STATE_NAMES.get(st)
        if not state_name:
            continue
        for kw in KEYWORDS:
            params = {
                "conditions[publication_date][gte]": since,
                "conditions[term]": f'"{state_name}" "{kw}"',
                "conditions[agencies][]": "environmental-protection-agency",
                "per_page": "50",
                "fields[]": ["document_number", "title", "abstract", "html_url",
                             "publication_date", "type"],
            }
            try:
                data = http_get_json(ENDPOINT, params=params)
            except RuntimeError:
                continue
            for doc in data.get("results", []):
                alerts.append(Alert(
                    source=SOURCE,
                    id=f"fr:{doc.get('document_number', '')}",
                    title=doc.get("title", "Federal Register notice"),
                    body=(doc.get("abstract") or "")[:500],
                    url=doc.get("html_url", ""),
                    date=doc.get("publication_date", ""),
                    state=st,
                ))
    # Dedupe by ID (a doc may match multiple keywords/states).
    seen: dict[str, Alert] = {}
    for a in alerts:
        seen.setdefault(a.id, a)
    return list(seen.values())
