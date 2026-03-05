#!/usr/bin/env python3
"""
Detects new policies added during the latest fetch cycle and sends
a digest email via the Buttondown API (free tier).

Usage: python3 scripts/send_newsletter.py [--draft]

Requires BUTTONDOWN_API_KEY env var.
Pass --draft to create a draft instead of sending immediately.
"""

import html as html_mod
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SNAPSHOT_FILE = DATA_DIR / ".policy_ids_snapshot.json"
POLICIES_FILE = DATA_DIR / "policies.json"
SITE_URL = "https://varnasr.github.io/PolicyDhara"

BUTTONDOWN_API = "https://api.buttondown.email/v1/emails"


def load_snapshot() -> set[str]:
    """Load the set of policy IDs from before the latest fetch."""
    if not SNAPSHOT_FILE.exists():
        return set()
    with open(SNAPSHOT_FILE) as f:
        return set(json.load(f))


def save_snapshot():
    """Save current policy IDs as a snapshot for next run."""
    if not POLICIES_FILE.exists():
        return
    with open(POLICIES_FILE) as f:
        policies = json.load(f)
    ids = [p["id"] for p in policies]
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump(ids, f)
    print(f"  Snapshot saved: {len(ids)} policy IDs")


def find_new_policies() -> list[dict]:
    """Compare current policies against snapshot to find new ones."""
    old_ids = load_snapshot()
    if not old_ids:
        print("  No previous snapshot found — saving current state (no email this run)")
        save_snapshot()
        return []

    with open(POLICIES_FILE) as f:
        policies = json.load(f)

    new_policies = [p for p in policies if p["id"] not in old_ids]
    print(f"  Found {len(new_policies)} new policies since last run")
    return new_policies


def format_email(policies: list[dict]) -> tuple[str, str]:
    """Build email subject and HTML body from new policies."""
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subject = f"PolicyDhara Brief — {len(policies)} new update{'s' if len(policies) != 1 else ''} ({today})"

    # Group by sector
    by_sector: dict[str, list[dict]] = {}
    for p in policies:
        sectors = p.get("sectors", ["Uncategorized"])
        for s in sectors:
            by_sector.setdefault(s, []).append(p)

    rows = ""
    for sector in sorted(by_sector.keys()):
        items = by_sector[sector]
        sector_safe = html_mod.escape(sector)
        rows += f'<tr><td colspan="2" style="padding:12px 0 4px;font-weight:bold;'
        rows += f'color:#1e40af;border-bottom:1px solid #e5e7eb;">{sector_safe}</td></tr>\n'
        for p in items:
            title = html_mod.escape(p.get("title", "Untitled"))
            link = p.get("link", "")
            source = html_mod.escape(p.get("source_short", p.get("source_name", "")))
            date = html_mod.escape(p.get("date", ""))
            desc = html_mod.escape(p.get("description", "")[:150])
            if desc:
                desc = f'<br><span style="color:#6b7280;font-size:13px;">{desc}...</span>'

            # Only allow http/https links — reject javascript:, data:, etc.
            if link and re.match(r'^https?://', link):
                link_safe = html_mod.escape(link)
                title_html = f'<a href="{link_safe}" style="color:#111827;text-decoration:none;">{title}</a>'
            else:
                title_html = title
            rows += f'<tr><td style="padding:6px 0;line-height:1.4;">{title_html}{desc}</td>'
            rows += f'<td style="padding:6px 0;color:#6b7280;font-size:13px;white-space:nowrap;vertical-align:top;">{source}<br>{date}</td></tr>\n'

    body = f"""<div style="font-family:-apple-system,system-ui,sans-serif;max-width:640px;margin:0 auto;color:#111827;">
  <h2 style="color:#1e3a5f;margin-bottom:4px;">PolicyDhara Daily Brief</h2>
  <p style="color:#6b7280;margin-top:0;">{today} &mdash; {len(policies)} new policy update{'s' if len(policies) != 1 else ''} tracked</p>

  <table style="width:100%;border-collapse:collapse;font-size:14px;">
    {rows}
  </table>

  <p style="margin-top:24px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:13px;color:#6b7280;">
    <a href="{SITE_URL}" style="color:#1e40af;">Browse all policies</a> &bull;
    <a href="{SITE_URL}/digest" style="color:#1e40af;">Today's digest</a> &bull;
    <a href="{SITE_URL}/rss.xml" style="color:#1e40af;">RSS feed</a>
  </p>
</div>"""

    return subject, body


def send_via_buttondown(subject: str, body: str, draft: bool = False):
    """Create an email (or draft) via the Buttondown API."""
    api_key = os.environ.get("BUTTONDOWN_API_KEY", "")
    if not api_key:
        print("  ERROR: BUTTONDOWN_API_KEY not set — skipping email")
        sys.exit(1)

    payload = json.dumps({
        "subject": subject,
        "body": body,
        "status": "draft" if draft else "about_to_send",
    }).encode()

    req = Request(BUTTONDOWN_API, data=payload, method="POST")
    req.add_header("Authorization", f"Token {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read())
            status = "Draft created" if draft else "Email sent"
            print(f"  {status}: {result.get('id', 'ok')}")
    except HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"  ERROR ({e.code}): {error_body}")
        sys.exit(1)


def main():
    draft = "--draft" in sys.argv

    print("=" * 50)
    print("PolicyDhara Newsletter")
    print("=" * 50)

    # If called with --snapshot-only, just save and exit
    if "--snapshot-only" in sys.argv:
        print("  Saving pre-fetch snapshot...")
        save_snapshot()
        return

    new_policies = find_new_policies()

    if not new_policies:
        print("  No new policies — no email to send")
        save_snapshot()
        return

    subject, body = format_email(new_policies)
    print(f"  Subject: {subject}")

    mode = "draft" if draft else "send"
    print(f"  Mode: {mode}")

    send_via_buttondown(subject, body, draft=draft)

    # Update snapshot after successful send
    save_snapshot()
    print("  Done!")


if __name__ == "__main__":
    main()
