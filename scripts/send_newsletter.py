#!/usr/bin/env python3
"""
Detects new policies added during the latest fetch cycle and sends
a digest email via the Buttondown API (free tier).

Usage: python3 scripts/send_newsletter.py [--draft] [--sector SLUG] [--sector-alerts]

Requires BUTTONDOWN_API_KEY env var.
Pass --draft to create a draft instead of sending immediately.
Pass --sector SLUG to send an email filtered to a single sector.
Pass --sector-alerts to send per-sector digest emails for all sectors with new policies.
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
    """Compare current policies against snapshot to find new ones.

    Returns [] if no snapshot exists. The CI workflow always writes a
    pre-fetch snapshot via --snapshot-only before any consumer runs;
    a missing snapshot means there's nothing to diff against.
    """
    old_ids = load_snapshot()
    if not old_ids:
        print("  No previous snapshot found — nothing to diff this run")
        return []

    with open(POLICIES_FILE) as f:
        policies = json.load(f)

    new_policies = [p for p in policies if p["id"] not in old_ids]
    print(f"  Found {len(new_policies)} new policies since last run")
    return new_policies


def get_sector_slug(sector_name: str) -> str:
    """Convert sector name to URL slug, matching the Astro getSectorSlug()."""
    return sector_name.lower().replace(" & ", "-").replace(" ", "-")


def filter_by_sector(policies: list[dict], sector_slug: str) -> list[dict]:
    """Filter policies to only those belonging to the given sector slug."""
    return [
        p for p in policies
        if sector_slug in [
            get_sector_slug(s) for s in p.get("sectors", [])
        ]
    ]


def get_sectors_with_new_policies(policies: list[dict]) -> dict[str, list[dict]]:
    """Group new policies by sector. Returns {sector_name: [policies]}."""
    by_sector: dict[str, list[dict]] = {}
    for p in policies:
        for s in p.get("sectors", ["Uncategorized"]):
            by_sector.setdefault(s, []).append(p)
    return by_sector


def _policy_type_color(policy_type: str) -> str:
    """Return an inline color for a policy type badge."""
    colors = {
        "legislation": "#dc2626",
        "notification": "#d97706",
        "scheme": "#16a34a",
        "budget": "#ea580c",
        "research": "#7c3aed",
        "announcement": "#2563eb",
        "policy": "#9333ea",
    }
    return colors.get(policy_type.lower(), "#4a4a48")


def _policy_type_bg(policy_type: str) -> str:
    """Return a background color for a policy type badge."""
    bgs = {
        "legislation": "#fef2f2",
        "notification": "#fffbeb",
        "scheme": "#f0fdf4",
        "budget": "#fff7ed",
        "research": "#f5f3ff",
        "announcement": "#eff6ff",
        "policy": "#faf5ff",
    }
    return bgs.get(policy_type.lower(), "#f7f6f3")


def format_email(policies: list[dict], sector_filter: str | None = None) -> tuple[str, str]:
    """Build email subject and HTML body from new policies.

    If sector_filter is given (as a display name), only that sector's
    policies are shown and the subject reflects the sector.
    """
    today = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    count = len(policies)
    plural = "s" if count != 1 else ""

    if sector_filter:
        subject = f"PolicyDhara {sector_filter} Alert — {count} new update{plural} ({today})"
    else:
        subject = f"PolicyDhara Brief — {count} new update{plural} ({today})"

    # Group by sector
    by_sector: dict[str, list[dict]] = {}
    for p in policies:
        sectors = p.get("sectors", ["Uncategorized"])
        for s in sectors:
            by_sector.setdefault(s, []).append(p)

    # Build sector blocks
    sector_blocks = ""
    for sector in sorted(by_sector.keys()):
        items = by_sector[sector]
        sector_safe = html_mod.escape(sector)
        sector_slug = get_sector_slug(sector)
        sector_url = f"{SITE_URL}/sectors/{sector_slug}"

        sector_blocks += f'''
        <tr><td style="padding:0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
            <tr><td style="padding:24px 0 8px 0;">
              <a href="{sector_url}" style="font-family:'Georgia','Newsreader',serif;font-size:16px;font-weight:600;color:#1a1a18;text-decoration:none;letter-spacing:-0.01em;">{sector_safe}</a>
              <span style="display:inline-block;margin-left:8px;font-size:11px;color:#7a7a78;font-family:-apple-system,'DM Sans',system-ui,sans-serif;">{len(items)} update{("s" if len(items) != 1 else "")}</span>
            </td></tr>
            <tr><td style="padding:0;"><div style="height:2px;background:#16a34a;width:40px;border-radius:1px;"></div></td></tr>
          </table>
        </td></tr>'''

        for p in items:
            title = html_mod.escape(p.get("title", "Untitled"))
            link = p.get("link", "")
            source = html_mod.escape(p.get("source_short", p.get("source_name", "")))
            date = html_mod.escape(p.get("date", ""))
            desc_raw = p.get("description", "")[:180]
            desc = html_mod.escape(desc_raw)
            policy_type = p.get("type", "policy")
            type_color = _policy_type_color(policy_type)
            type_bg = _policy_type_bg(policy_type)
            type_label = html_mod.escape(policy_type.replace("_", " ").title())

            # Only allow http/https links
            if link and re.match(r'^https?://', link):
                link_safe = html_mod.escape(link)
                title_html = f'<a href="{link_safe}" style="color:#1a1a18;text-decoration:none;font-weight:500;">{title}</a>'
            else:
                title_html = f'<span style="font-weight:500;color:#1a1a18;">{title}</span>'

            desc_html = ""
            if desc:
                desc_html = f'<p style="margin:4px 0 0;font-size:13px;line-height:1.45;color:#4a4a48;">{desc}{"..." if len(desc_raw) >= 180 else ""}</p>'

            sector_blocks += f'''
        <tr><td style="padding:0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
            <tr><td style="padding:10px 12px;border-bottom:1px solid #f0ede6;">
              <div style="margin-bottom:5px;">
                <span style="display:inline-block;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:{type_color};background:{type_bg};padding:2px 7px;border-radius:3px;">{type_label}</span>
                <span style="font-size:12px;color:#a0a09e;margin-left:6px;">{source} &middot; {date}</span>
              </div>
              <div style="font-size:14px;line-height:1.4;">{title_html}</div>
              {desc_html}
            </td></tr>
          </table>
        </td></tr>'''

    heading = f"PolicyDhara {html_mod.escape(sector_filter)} Alert" if sector_filter else "PolicyDhara Daily Brief"
    subtitle = f"{count} new policy update{plural} tracked across India"
    alerts_link_html = ""
    if sector_filter:
        alerts_link_html = f'<a href="{SITE_URL}/alerts" style="color:#16a34a;text-decoration:none;font-weight:500;">Manage alerts</a> &nbsp;&middot;&nbsp; '

    body = f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f7f6f3;font-family:-apple-system,'DM Sans','Segoe UI',system-ui,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f7f6f3;">
  <tr><td align="center" style="padding:24px 16px;">
    <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;border-collapse:collapse;">

      <!-- Header -->
      <tr><td style="padding:28px 32px 24px;background:#fffef9;border-radius:12px 12px 0 0;border-bottom:2px solid #16a34a;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
          <tr>
            <td>
              <div style="font-family:'Georgia','Newsreader',serif;font-size:22px;font-weight:700;color:#1a1a18;letter-spacing:-0.02em;margin-bottom:2px;">{heading}</div>
              <div style="font-size:13px;color:#7a7a78;margin-top:4px;">{today}</div>
            </td>
            <td align="right" valign="top">
              <a href="{SITE_URL}" style="text-decoration:none;">
                <div style="display:inline-block;background:#16a34a;color:#ffffff;font-size:11px;font-weight:600;padding:6px 14px;border-radius:100px;letter-spacing:0.02em;">BROWSE ALL</div>
              </a>
            </td>
          </tr>
        </table>
      </td></tr>

      <!-- Summary bar -->
      <tr><td style="padding:14px 32px;background:#f0fdf4;font-size:13px;color:#15803d;font-weight:500;">
        {subtitle}
      </td></tr>

      <!-- Policy content -->
      <tr><td style="padding:0 32px 16px;background:#fffef9;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
          {sector_blocks}
        </table>
      </td></tr>

      <!-- Footer -->
      <tr><td style="padding:20px 32px 24px;background:#fffef9;border-top:1px solid #e5e2db;border-radius:0 0 12px 12px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
          <tr><td style="font-size:13px;color:#7a7a78;line-height:1.6;">
            {alerts_link_html}<a href="{SITE_URL}/digest" style="color:#16a34a;text-decoration:none;font-weight:500;">Today&#8217;s digest</a> &nbsp;&middot;&nbsp;
            <a href="{SITE_URL}/rss.xml" style="color:#16a34a;text-decoration:none;font-weight:500;">RSS feed</a> &nbsp;&middot;&nbsp;
            <a href="{SITE_URL}/alerts" style="color:#16a34a;text-decoration:none;font-weight:500;">Sector alerts</a>
          </td></tr>
          <tr><td style="padding-top:14px;font-size:11px;color:#a0a09e;">
            PolicyDhara by <a href="https://impactmojo.in" style="color:#a0a09e;">ImpactMojo</a> &mdash; Tracking 300+ official sources across India.
          </td></tr>
        </table>
      </td></tr>

    </table>
  </td></tr>
</table>
</body>
</html>'''

    return subject, body


def send_via_buttondown(subject: str, body: str, draft: bool = False,
                        metadata: dict | None = None):
    """Create an email (or draft) via the Buttondown API.

    metadata can include sector tags for filtering, e.g.:
        {"sectors": ["finance-economy", "health"]}
    """
    api_key = os.environ.get("BUTTONDOWN_API_KEY", "")
    if not api_key:
        print("  ERROR: BUTTONDOWN_API_KEY not set — skipping email")
        sys.exit(1)

    email_data: dict = {
        "subject": subject,
        "body": body,
        "status": "draft" if draft else "about_to_send",
    }
    if metadata:
        email_data["metadata"] = metadata

    payload = json.dumps(email_data).encode()

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


def send_sector_alerts(new_policies: list[dict], draft: bool = False):
    """Send per-sector digest emails for each sector that has new policies.

    Each sector email is tagged with metadata so Buttondown can filter
    delivery to subscribers interested in that sector.
    """
    sectors_map = get_sectors_with_new_policies(new_policies)

    if not sectors_map:
        print("  No sectors with new policies for sector alerts")
        return

    print(f"  Sending sector alerts for {len(sectors_map)} sectors...")

    for sector_name, sector_policies in sorted(sectors_map.items()):
        slug = get_sector_slug(sector_name)
        print(f"  -- {sector_name} ({slug}): {len(sector_policies)} policies")

        subject, body = format_email(sector_policies, sector_filter=sector_name)
        metadata = {
            "sectors": [slug],
            "sector_names": [sector_name],
            "type": "sector_alert",
        }
        send_via_buttondown(subject, body, draft=draft, metadata=metadata)

    print(f"  Sector alerts done: {len(sectors_map)} emails sent/drafted")


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
        return

    # --sector SLUG: send a single sector-filtered email
    if "--sector" in sys.argv:
        idx = sys.argv.index("--sector")
        if idx + 1 >= len(sys.argv):
            print("  ERROR: --sector requires a sector slug argument")
            sys.exit(1)
        sector_slug = sys.argv[idx + 1]
        filtered = filter_by_sector(new_policies, sector_slug)
        if not filtered:
            print(f"  No new policies in sector '{sector_slug}'")
            return
        # Find display name from first matching policy
        sector_name = sector_slug
        for p in filtered:
            for s in p.get("sectors", []):
                if get_sector_slug(s) == sector_slug:
                    sector_name = s
                    break
            if sector_name != sector_slug:
                break
        subject, body = format_email(filtered, sector_filter=sector_name)
        print(f"  Subject: {subject}")
        metadata = {"sectors": [sector_slug], "type": "sector_alert"}
        send_via_buttondown(subject, body, draft=draft, metadata=metadata)
        print("  Done!")
        return

    # --sector-alerts: send per-sector digests for all sectors with new policies
    if "--sector-alerts" in sys.argv:
        send_sector_alerts(new_policies, draft=draft)
        print("  Done!")
        return

    # Default: send the full digest
    # Collect sector slugs that have new policies for metadata tagging
    all_sector_slugs = list({
        get_sector_slug(s)
        for p in new_policies
        for s in p.get("sectors", [])
    })

    subject, body = format_email(new_policies)
    print(f"  Subject: {subject}")

    mode = "draft" if draft else "send"
    print(f"  Mode: {mode}")

    metadata = {
        "sectors": all_sector_slugs,
        "type": "daily_digest",
    }
    send_via_buttondown(subject, body, draft=draft, metadata=metadata)
    print("  Done!")


if __name__ == "__main__":
    main()
