#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""
Detect new entries in chemical_disasters.json since the last run and email
subscribers. State (which incident IDs have already been notified) is kept in
notification_state.json so the diff is robust across rebases and force-pushes.

Env vars (all optional; missing keys turn off the corresponding step):
  RESEND_API_KEY     — Resend API key for outbound email
  NOTIFY_FROM        — From: address (must be a verified Resend sender)
  NOTIFY_RECIPIENTS  — comma-separated recipient list
  NOTIFY_STATES      — comma-separated state filter (default: DE,PA,NJ,MD)

Exit codes:
  0  — ran cleanly (may or may not have sent mail)
  1  — fatal config or I/O error
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INCIDENTS_PATH = REPO_ROOT / "chemical_disasters.json"
STATE_PATH = REPO_ROOT / "notification_state.json"


def incident_id(props: dict) -> str:
    """Stable ID per incident. Prefer NRC, then RMP, then name+date."""
    for key in ("nrc_id", "rmp_id"):
        if props.get(key):
            return f"{key}:{props[key]}"
    return f"name:{props.get('name', '')}|date:{props.get('date', '')}"


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"seen_ids": []}
    return json.loads(STATE_PATH.read_text())


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def find_new_incidents(states: set[str]) -> tuple[list[dict], set[str]]:
    data = json.loads(INCIDENTS_PATH.read_text())
    state = load_state()
    seen = set(state.get("seen_ids", []))

    new_features = []
    all_ids = set()
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        if props.get("state") not in states:
            continue
        iid = incident_id(props)
        all_ids.add(iid)
        if iid not in seen:
            new_features.append(feat)
    return new_features, all_ids


def render_email(features: list[dict]) -> tuple[str, str, str]:
    subject = f"CC4EJ alert: {len(features)} new chemical incident(s) in or near Delaware"
    lines_html = ["<h2>New incidents added to the CC4EJ Cumulative Impacts Map</h2>", "<ul>"]
    lines_text = [subject, ""]
    for feat in features:
        p = feat.get("properties", {})
        title = f"{p.get('name', 'Unnamed incident')} ({p.get('state', '?')}, {p.get('date', '?')})"
        body = p.get("consequences", "")
        url = p.get("source_url", "")
        lines_html.append(
            f"<li><b>{title}</b><br>{body}"
            + (f'<br><a href="{url}">Source</a>' if url else "")
            + "</li>"
        )
        lines_text.append(f"- {title}")
        if body:
            lines_text.append(f"  {body}")
        if url:
            lines_text.append(f"  {url}")
    lines_html.append("</ul>")
    lines_html.append('<p><a href="https://cc4ej-ci-map.vercel.app/">Open the map</a></p>')
    return subject, "\n".join(lines_html), "\n".join(lines_text)


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
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"Resend response: {resp.status} {resp.read().decode()}")


def main() -> int:
    if not INCIDENTS_PATH.exists():
        print(f"Missing {INCIDENTS_PATH}", file=sys.stderr)
        return 1

    states = {s.strip() for s in os.environ.get("NOTIFY_STATES", "DE,PA,NJ,MD").split(",") if s.strip()}
    new_features, all_ids = find_new_incidents(states)

    if not STATE_PATH.exists():
        # First run: seed the state with what's already there, don't email.
        save_state({"seen_ids": sorted(all_ids)})
        print(f"Seeded notification_state.json with {len(all_ids)} existing incident IDs. No emails sent.")
        return 0

    if not new_features:
        print("No new incidents. Nothing to send.")
        return 0

    subject, html, text = render_email(new_features)
    print(f"Found {len(new_features)} new incident(s). Subject: {subject}")
    try:
        send_via_resend(subject, html, text)
    except urllib.error.HTTPError as e:
        print(f"Resend HTTP error: {e.code} {e.read().decode(errors='replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"Resend network error: {e}", file=sys.stderr)
        return 1

    save_state({"seen_ids": sorted(all_ids)})
    print(f"Updated notification_state.json ({len(all_ids)} IDs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
