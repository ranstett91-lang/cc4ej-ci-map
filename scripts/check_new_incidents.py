#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""
Driver: poll every notification source, diff against per-source seen-IDs in
notification_state.json, render an email, and (if creds are present) send
via Resend.

Sources live in scripts/notifiers/. Each exposes:
    fetch(states: set[str]) -> list[Alert]

State file shape:
    {
      "sources": {
        "<source_name>": ["id1", "id2", ...]
      }
    }

A missing source key on first encounter is treated as "seed silently" — we
record current IDs without emailing, so a newly added source doesn't dump
its entire backlog into a single mail.

Env vars (all optional; missing keys turn off the corresponding step):
  RESEND_API_KEY     — Resend API key for outbound email
  NOTIFY_FROM        — From: address (must be a verified Resend sender)
  NOTIFY_RECIPIENTS  — comma-separated recipient list
  NOTIFY_STATES      — comma-separated state filter (default: DE,PA,NJ,MD)
"""

from __future__ import annotations

import json
import os
import sys
import traceback
import urllib.error
import urllib.request
from collections import defaultdict
from html import escape
from pathlib import Path

from notifiers import (
    chemical_disasters,
    dnrec,
    epa_echo,
    epa_envirofacts,
    federal_register,
    nrc,
    phmsa,
)
from notifiers.base import Alert

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "notification_state.json"

SOURCES = [
    chemical_disasters,
    federal_register,
    epa_envirofacts,
    epa_echo,
    phmsa,
    nrc,
    dnrec,
]


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"sources": {}}
    raw = json.loads(STATE_PATH.read_text())
    # Migrate from the original flat shape: {"seen_ids": [...]}.
    if "sources" not in raw:
        return {"sources": {"chemical_disasters": raw.get("seen_ids", [])}}
    return raw


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def collect(states: set[str]) -> tuple[dict[str, list[Alert]], dict[str, set[str]]]:
    """Run every source. Returns (alerts_by_source, current_ids_by_source)."""
    alerts: dict[str, list[Alert]] = defaultdict(list)
    ids: dict[str, set[str]] = defaultdict(set)
    for mod in SOURCES:
        name = getattr(mod, "SOURCE", mod.__name__.split(".")[-1])
        try:
            results = mod.fetch(states)
        except Exception:
            print(f"[{name}] fetch failed:\n{traceback.format_exc()}", file=sys.stderr)
            continue
        for a in results:
            alerts[a.source].append(a)
            ids[a.source].add(a.id)
        print(f"[{name}] returned {len(results)} alert(s)")
    return alerts, ids


def render_email(new_by_source: dict[str, list[Alert]]) -> tuple[str, str, str]:
    total = sum(len(v) for v in new_by_source.values())
    subject = f"CC4EJ alert: {total} new environmental record(s) for your watchlist"

    html = ["<h2>New environmental records on the CC4EJ watchlist</h2>"]
    text = [subject, ""]

    for source, items in sorted(new_by_source.items()):
        if not items:
            continue
        html.append(f"<h3>{escape(source)} — {len(items)} new</h3><ul>")
        text.append(f"\n## {source} — {len(items)} new")
        for a in items:
            title = escape(a.title or "(untitled)")
            body = escape(a.body or "")
            url = a.url or ""
            date = a.date or ""
            html.append(
                f"<li><b>{title}</b>"
                + (f" <span style='color:#666'>{escape(date)}</span>" if date else "")
                + (f"<br>{body}" if body else "")
                + (f'<br><a href="{escape(url)}">Open</a>' if url else "")
                + "</li>"
            )
            text.append(f"- {a.title} {('(' + date + ')') if date else ''}")
            if a.body:
                text.append(f"  {a.body}")
            if url:
                text.append(f"  {url}")
        html.append("</ul>")

    html.append('<hr><p style="font-size:12px;color:#999">'
                'Sources: chemical_disasters.json, federalregister.gov, EPA Envirofacts '
                '(SEMS + RCRAInfo), EPA ECHO, PHMSA, NRC, DNREC public notices + SIRS.</p>')
    return subject, "\n".join(html), "\n".join(text)


def send_via_resend(subject: str, html: str, text: str) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    sender = os.environ.get("NOTIFY_FROM")
    recipients = [r.strip() for r in os.environ.get("NOTIFY_RECIPIENTS", "").split(",") if r.strip()]
    if not (api_key and sender and recipients):
        print("Resend env vars not set — skipping email send (dry run mode).", file=sys.stderr)
        return

    payload = json.dumps({
        "from": sender,
        "to": recipients,
        "subject": subject,
        "html": html,
        "text": text,
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"Resend response: {resp.status} {resp.read().decode()}")


def main() -> int:
    states = {s.strip() for s in os.environ.get("NOTIFY_STATES", "DE,PA,NJ,MD").split(",") if s.strip()}
    state = load_state()
    seen = {k: set(v) for k, v in state.get("sources", {}).items()}

    _alerts_by_source, ids_by_source = collect(states)

    new_by_source: dict[str, list[Alert]] = {}
    is_first_run_overall = STATE_PATH.exists() is False

    for source, alerts in _alerts_by_source.items():
        if source not in seen:
            print(f"[{source}] first-time encounter — seeding {len(alerts)} ID(s) without emailing.")
            continue
        prior = seen[source]
        new = [a for a in alerts if a.id not in prior]
        if new:
            new_by_source[source] = new

    # Persist current IDs for every source (even ones with zero alerts this run —
    # an empty list is meaningful: "we know this source, we just got nothing").
    state["sources"] = {k: sorted(v) for k, v in {**seen, **ids_by_source}.items()}
    # Overwrite seeded sources with their current IDs.
    for source, ids in ids_by_source.items():
        state["sources"][source] = sorted(ids)

    if is_first_run_overall:
        save_state(state)
        print("Seed run complete — no emails sent.")
        return 0

    if not new_by_source:
        save_state(state)
        print("No new items across any source.")
        return 0

    subject, html, text = render_email(new_by_source)
    print(f"Sending: {subject}")
    try:
        send_via_resend(subject, html, text)
    except urllib.error.HTTPError as e:
        print(f"Resend HTTP error: {e.code} {e.read().decode(errors='replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"Resend network error: {e}", file=sys.stderr)
        return 1

    save_state(state)
    print("State updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
