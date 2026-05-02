# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""
EPA Envirofacts source — covers SEMS (Superfund / CERCLA) + RCRAInfo.

Envirofacts is a thin REST layer over EPA databases. URL pattern:
    https://data.epa.gov/efservice/<TABLE>/<COL>/<VAL>/JSON

Docs: https://www.epa.gov/enviro/envirofacts-data-service-api

We pull facility-level state filtered records and treat each row as a
candidate alert. Diffing against state file means we only email when a
new SEMS site appears or when a new RCRA generator is registered, etc.
"""

from __future__ import annotations

from .base import Alert, http_get_json

SOURCE = "epa_envirofacts"
BASE = "https://data.epa.gov/efservice"

# Each entry: (program_label, table, state-column-name)
QUERIES = [
    ("CERCLA / SEMS site",     "SEMS_FAC_DETAIL",  "STATE_CODE"),
    ("RCRA handler",           "RCR_HD_HANDLER",   "LOCATION_STATE"),
    ("RCRA Corrective Action", "RCR_CORRECT_EVENT","LOCATION_STATE"),
]


def _row_id(table: str, row: dict) -> str:
    """Pick a stable per-row identifier."""
    for key in ("EPA_ID", "REGISTRY_ID", "EPA_HANDLER_ID", "HANDLER_ID",
                "SITE_EPA_ID", "EVENT_ID", "CA_EVENT_CODE"):
        v = row.get(key) or row.get(key.lower())
        if v:
            return f"{table}:{key}={v}"
    # last resort — hash a sorted tuple of values
    return f"{table}:" + "|".join(f"{k}={row[k]}" for k in sorted(row)[:5])


def _row_title(table: str, row: dict) -> str:
    for key in ("SITE_NAME", "FACILITY_NAME", "HANDLER_NAME", "EPA_HANDLER_NAME"):
        v = row.get(key) or row.get(key.lower())
        if v:
            return v
    return f"{table} record"


def fetch(states: set[str]) -> list[Alert]:
    alerts: list[Alert] = []
    for label, table, state_col in QUERIES:
        for st in states:
            url = f"{BASE}/{table}/{state_col}/{st}/JSON"
            try:
                rows = http_get_json(url)
            except RuntimeError:
                continue
            if not isinstance(rows, list):
                continue
            for row in rows:
                # Envirofacts returns lowercase keys in some endpoints; normalize.
                row = {k.upper(): v for k, v in row.items()}
                alerts.append(Alert(
                    source=SOURCE,
                    id=_row_id(table, row),
                    title=f"{label}: {_row_title(table, row)} ({st})",
                    body=(row.get("LOCATION_ADDRESS") or row.get("STREET_ADDRESS") or "") + " "
                         + (row.get("CITY_NAME") or row.get("CITY") or ""),
                    url=f"https://enviro.epa.gov/enviro/efsystemquery.{table.lower()}",
                    date=str(row.get("CREATE_DATE") or row.get("ACTION_DATE")
                             or row.get("LAST_UPDATE_DATE") or "")[:10],
                    state=st,
                ))
    return alerts
