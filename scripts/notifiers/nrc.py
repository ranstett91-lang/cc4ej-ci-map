# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""
National Response Center (NRC) release-report source.

NRC publishes annual CSV rollups under https://nrc.uscg.mil/FOIAFiles/.
File names follow the pattern CY{year}.csv. Columns may shift; we read
defensively and key on INCIDENT_REPORT_NO (stable across re-publications).
"""

from __future__ import annotations

import csv
import io
from datetime import date

from .base import Alert, http_get_text

SOURCE = "nrc"
URL_TEMPLATE = "https://nrc.uscg.mil/FOIAFiles/CY{year}.csv"


def _year_candidates() -> list[int]:
    y = date.today().year
    return [y, y - 1]


def _row_state(row: dict) -> str:
    for k in ("INCIDENT_STATE", "STATE", "STATE_ABBR"):
        v = row.get(k)
        if v:
            return str(v).strip().upper()
    return ""


def fetch(states: set[str]) -> list[Alert]:
    alerts: list[Alert] = []
    for year in _year_candidates():
        url = URL_TEMPLATE.format(year=year)
        try:
            text = http_get_text(url)
        except RuntimeError:
            continue
        try:
            reader = csv.DictReader(io.StringIO(text))
        except csv.Error:
            continue
        for row in reader:
            st = _row_state(row)
            if st not in states:
                continue
            rid = row.get("INCIDENT_REPORT_NO") or row.get("REPORT_NO")
            if not rid:
                continue
            material = (row.get("MATERIAL_NAME") or row.get("CHEMICAL") or "").strip()
            location = (row.get("INCIDENT_CITY") or row.get("CITY") or "").strip()
            alerts.append(Alert(
                source=SOURCE,
                id=f"nrc:{rid}",
                title=f"NRC release report #{rid}: {material or 'unspecified material'} ({location}, {st})",
                body=(row.get("INCIDENT_DESC") or row.get("DESCRIPTION") or "")[:500],
                url=f"https://nrc.uscg.mil/IncidentDetail.aspx?id={rid}",
                date=(row.get("INCIDENT_DATE_TIME") or row.get("CALL_DATE_TIME") or "")[:10],
                state=st,
            ))
    return alerts
