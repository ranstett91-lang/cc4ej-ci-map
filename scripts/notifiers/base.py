# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Shared data shapes + HTTP helpers for all notification sources."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = "CC4EJ-Notifier/1.0 (+https://github.com/ranstett91-lang/cc4ej-ci-map)"
DEFAULT_TIMEOUT = 30


@dataclass
class Alert:
    """One notifiable item from a source. `id` must be stable across runs."""
    source: str
    id: str
    title: str
    body: str
    url: str
    date: str   # ISO yyyy-mm-dd if known, else ""
    state: str  # two-letter; "" if multi-state or unknown

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def http_get_json(url: str, params: dict | None = None, retries: int = 2) -> Any:
    """GET a JSON endpoint with simple retry. Returns parsed JSON."""
    full = url + ("?" + urlencode(params) if params else "")
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = Request(full, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"GET {full} failed after {retries + 1} attempts: {last_err}")


def http_get_text(url: str, params: dict | None = None, retries: int = 2) -> str:
    """GET a text/CSV/HTML endpoint with simple retry."""
    full = url + ("?" + urlencode(params) if params else "")
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = Request(full, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"GET {full} failed after {retries + 1} attempts: {last_err}")
