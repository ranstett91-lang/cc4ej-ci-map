# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""
EPA ECHO source — air/water quarterly noncompliance + enforcement actions.

ECHO REST docs: https://echo.epa.gov/tools/web-services
We hit the case-search endpoint for recent enforcement cases, filtered to
state. Diff catches new violations and consent decrees.
"""

from __future__ import annotations

from .base import Alert, http_get_json

SOURCE = "epa_echo"

CASE_ENDPOINT = "https://echodata.epa.gov/echo/case_rest_services.get_cases"


def fetch(states: set[str]) -> list[Alert]:
    alerts: list[Alert] = []
    for st in states:
        params = {
            "output": "JSON",
            "p_st": st,
            "p_act_date_min": "2020-01-01",   # filtered further by client-side dedupe
            "responseset": "1",
        }
        try:
            data = http_get_json(CASE_ENDPOINT, params=params)
        except RuntimeError:
            continue

        cases = (data.get("Results") or {}).get("Cases") or []
        for c in cases:
            case_num = c.get("CaseNumber") or c.get("case_number") or ""
            if not case_num:
                continue
            alerts.append(Alert(
                source=SOURCE,
                id=f"echo:{case_num}",
                title=f"ECHO enforcement case: {c.get('CaseName', case_num)} ({st})",
                body=(c.get("CaseTypeDesc") or c.get("CaseType") or "") + " — "
                     + (c.get("CaseStatus") or ""),
                url=f"https://echo.epa.gov/enforcement-case-report?id={case_num}",
                date=(c.get("SettlementDate") or c.get("FiledDate") or "")[:10],
                state=st,
            ))
    return alerts
