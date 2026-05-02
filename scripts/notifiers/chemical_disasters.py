# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Diff the in-repo chemical_disasters.json file."""

from __future__ import annotations

import json
from pathlib import Path

from .base import Alert

SOURCE = "chemical_disasters"
PATH = Path(__file__).resolve().parent.parent.parent / "chemical_disasters.json"


def _id(props: dict) -> str:
    for key in ("nrc_id", "rmp_id"):
        if props.get(key):
            return f"{key}:{props[key]}"
    return f"name:{props.get('name', '')}|date:{props.get('date', '')}"


def fetch(states: set[str]) -> list[Alert]:
    if not PATH.exists():
        return []
    data = json.loads(PATH.read_text())
    alerts: list[Alert] = []
    for feat in data.get("features", []):
        p = feat.get("properties", {})
        if p.get("state") not in states:
            continue
        alerts.append(Alert(
            source=SOURCE,
            id=_id(p),
            title=f"{p.get('name', 'Unnamed incident')} ({p.get('state', '?')})",
            body=p.get("consequences", "") or p.get("health_risk", ""),
            url=p.get("source_url", ""),
            date=p.get("date", ""),
            state=p.get("state", ""),
        ))
    return alerts
