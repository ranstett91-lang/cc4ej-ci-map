# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""
PHMSA pipeline incident source.

PHMSA publishes annual rollups + monthly preliminary reports as ZIPped
Excel/CSV at https://www.phmsa.dot.gov/data-and-statistics/pipeline/
distribution-transmission-gathering-lng-and-liquid-accident-and-incident-data

The CSV column shapes have drifted across years; we read defensively.
We point at the gas-distribution + hazardous-liquid yearly CSVs.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from .base import Alert, http_get_text

SOURCE = "phmsa"

# Year is appended at runtime. PHMSA changes URLs occasionally — keep these
# easy to update.
URLS = [
    "https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/data_statistics/pipeline/hl{year}.csv",
    "https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/data_statistics/pipeline/gd{year}.csv",
]


def _year_candidates() -> list[int]:
    y = date.today().year
    return [y, y - 1]


def _row_state(row: dict) -> str:
    for k in ("LOCATION_STATE_ABBREVIATION", "ACCIDENT_STATE_ABBREVIATION",
              "INCIDENT_STATE_ABBREVIATION", "STATE_ABBREV"):
        v = row.get(k)
        if v:
            return str(v).strip().upper()
    return ""


def fetch(states: set[str]) -> list[Alert]:
    alerts: list[Alert] = []
    for year in _year_candidates():
        for tmpl in URLS:
            url = tmpl.format(year=year)
            try:
                text = http_get_text(url)
            except RuntimeError:
                continue
            try:
                reader = csv.DictReader(io.StringIO(text))
                for row in reader:
                    st = _row_state(row)
                    if st not in states:
                        continue
                    rid = row.get("REPORT_NUMBER") or row.get("REPORTID") or ""
                    if not rid:
                        continue
                    alerts.append(Alert(
                        source=SOURCE,
                        id=f"phmsa:{rid}",
                        title=f"PHMSA pipeline incident: {row.get('OPERATOR_NAME', '')} ({st})",
                        body=(row.get("NARRATIVE") or row.get("CAUSE") or "")[:500],
                        url=url,
                        date=(row.get("LOCAL_DATETIME") or row.get("IDATE") or "")[:10],
                        state=st,
                    ))
            except csv.Error:
                continue
    return alerts
