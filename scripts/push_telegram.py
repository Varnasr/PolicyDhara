#!/usr/bin/env python3
"""
Push high-priority new policies to a Telegram channel/chat.

Reuses the snapshot machinery from send_newsletter.py: anything in
data/policies.json that is NOT in data/.policy_ids_snapshot.json is
considered "new this cycle". Of those, we filter to "critical" or
"high" priority items and post each to Telegram.

Usage:
  python3 scripts/push_telegram.py            # post all new + high-priority items
  python3 scripts/push_telegram.py --dry-run  # print what would be sent
  python3 scripts/push_telegram.py --max 10   # cap at N posts (default 20)
  python3 scripts/push_telegram.py --all      # ignore priority filter, post all new

Required env vars (set as GitHub Secrets and exposed in workflow):
  TELEGRAM_BOT_TOKEN  — bot token from @BotFather
  TELEGRAM_CHAT_ID    — channel @username (e.g. @policydhara) or numeric chat id

Setup (one-time):
  1. Open Telegram → message @BotFather → /newbot → follow prompts → copy token
  2. Create a channel; add the bot as administrator (with "Post Messages" right)
  3. Get the chat id: forward any message from the channel to @userinfobot,
     OR use @username for public channels
  4. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to the repo's GitHub Secrets
"""

import argparse
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).parent))
from classifier import is_broadcast_relevant  # noqa: E402

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SNAPSHOT_FILE = DATA_DIR / ".policy_ids_snapshot.json"
POLICIES_FILE = DATA_DIR / "policies.json"
SITE_URL = "https://varnasr.github.io/PolicyDhara"

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
SLEEP_BETWEEN_SENDS = 0.6  # respect Telegram's 30 msg/sec channel rate limit


def load_snapshot() -> set[str]:
    if not SNAPSHOT_FILE.exists():
        return set()
    with open(SNAPSHOT_FILE) as f:
        return set(json.load(f))


def find_new_policies() -> list[dict]:
    old_ids = load_snapshot()
    if not old_ids:
        print("  No previous snapshot — nothing to alert on this run")
        return []
    if not POLICIES_FILE.exists():
        print("  policies.json missing — nothing to alert on")
        return []
    with open(POLICIES_FILE) as f:
        policies = json.load(f)
    new = [p for p in policies if p["id"] not in old_ids]
    print(f"  Found {len(new)} new policies since last snapshot")

    # Defense-in-depth: never broadcast spectacle/tabloid noise or unfiltered
    # media items, even if one reached policies.json (stale snapshot, a
    # mislabeled source, an official feed with a lurid title).
    relevant = [
        p for p in new
        if is_broadcast_relevant(
            p.get("title", ""), p.get("description", "") or "", p.get("level", "")
        )
    ]
    if len(relevant) != len(new):
        print(f"  Dropped {len(new) - len(relevant)} as non-broadcastable "
              f"(spectacle / non-policy); {len(relevant)} remain")
    return relevant


def is_high_priority(policy: dict) -> bool:
    """Mirror the JS getPriority() in src/lib/data.ts. Returns True if
    policy is 'critical' or 'high'."""
    title = (policy.get("title") or "").lower()
    desc = (policy.get("description") or "").lower()
    combined = f"{title} {desc}"
    type_ = policy.get("type", "")
    sectors = policy.get("sectors", [])

    if re.search(
        r"constitutional amendment|finance bill|union budget|national security|emergency",
        combined,
    ):
        return True
    if type_ in ("legislation", "act", "bill") and re.search(r"\bact\b|\bbill\b", title):
        return True
    if re.search(r"crore|lakh crore|billion|nationwide|all states|pan-india", combined):
        return True
    if type_ == "scheme" and len(sectors) >= 2:
        return True
    if type_ in ("notification", "rules") and re.search(r"gazette|notification|rules", title):
        return True
    if type_ == "draft":  # consultations are time-bound — always worth alerting
        return True
    return False


def telegram_escape(text: str) -> str:
    """Escape for Telegram HTML parse mode (only <, >, & need escaping in
    text content; tag attribute values use a separate escape)."""
    return html.escape(text or "", quote=False)


def format_message(policy: dict) -> str:
    title = telegram_escape(policy.get("title", "Untitled policy"))
    desc = telegram_escape(policy.get("description", "") or "")
    if len(desc) > 280:
        desc = desc[:277].rstrip() + "…"
    sectors = ", ".join(telegram_escape(s) for s in policy.get("sectors", []))
    source = telegram_escape(policy.get("source_short", "") or policy.get("source_name", ""))
    type_ = telegram_escape(policy.get("type", "policy"))
    date = telegram_escape(policy.get("date", ""))
    detail_url = f"{SITE_URL}/policies/{policy.get('id', '')}/"
    source_url = policy.get("link") or detail_url

    type_emoji = {
        "legislation": "⚖️",
        "act": "⚖️",
        "bill": "🏛",
        "rules": "📜",
        "notification": "📜",
        "draft": "✍️",
        "question": "❓",
        "committee_report": "🗂",
        "judgment": "⚖️",
        "scheme": "🎯",
        "budget": "💰",
        "research": "📊",
        "report": "📊",
        "analysis": "📊",
        "longform": "📖",
        "announcement": "📢",
        "release": "📢",
        "policy": "📋",
    }.get(policy.get("type", "policy"), "📋")

    parts = [
        f'{type_emoji} <b>{title}</b>',
        '',
        f'<i>{type_.title()}</i> · {source} · {date}',
    ]
    deadline = policy.get("comment_deadline", "")
    if deadline:
        parts.append(f'⏳ <b>Comments close {telegram_escape(deadline)}</b>')
    if desc:
        parts.append('')
        parts.append(desc)
    if sectors:
        parts.append('')
        parts.append(f'<b>Sectors:</b> {sectors}')
    parts.append('')
    parts.append(f'🔗 <a href="{telegram_escape(source_url)}">Source</a> · <a href="{telegram_escape(detail_url)}">PolicyDhara</a>')
    return "\n".join(parts)


def send_message(token: str, chat_id: str, text: str, dry_run: bool = False) -> bool:
    if dry_run:
        print("  [DRY-RUN] Would send:")
        print("  " + text.replace("\n", "\n  "))
        print()
        return True

    url = TELEGRAM_API.format(token=token, method="sendMessage")
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "disable_notification": False,
    }).encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=10) as resp:
            body = json.load(resp)
            if not body.get("ok"):
                print(f"  ! Telegram API error: {body}")
                return False
            return True
    except HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        print(f"  ! HTTP {e.code} from Telegram: {err_body}")
        return False
    except URLError as e:
        print(f"  ! Network error sending to Telegram: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Push new policies to Telegram")
    parser.add_argument("--dry-run", action="store_true", help="Print messages instead of sending")
    parser.add_argument("--max", type=int, default=20, help="Max messages to send per run (default: 20)")
    parser.add_argument("--all", action="store_true", help="Skip priority filter; send all new policies")
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not args.dry_run and (not token or not chat_id):
        print("  TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID not set — skipping")
        return 0

    new_policies = find_new_policies()
    if not new_policies:
        print("  Nothing new to alert on. Exiting cleanly.")
        return 0

    if args.all:
        candidates = new_policies
    else:
        candidates = [p for p in new_policies if is_high_priority(p)]
        print(f"  {len(candidates)} of {len(new_policies)} new policies are high-priority")

    if not candidates:
        print("  No high-priority new policies. Exiting cleanly.")
        return 0

    candidates.sort(key=lambda p: p.get("date", ""), reverse=True)
    to_send = candidates[: args.max]
    print(f"  Sending {len(to_send)} alert(s) to Telegram (max={args.max}, dry_run={args.dry_run})")

    sent = 0
    for policy in to_send:
        text = format_message(policy)
        if send_message(token, chat_id, text, dry_run=args.dry_run):
            sent += 1
        if not args.dry_run:
            time.sleep(SLEEP_BETWEEN_SENDS)

    print(f"  Done. Sent {sent}/{len(to_send)} alerts.")
    return 0 if sent == len(to_send) else 1


if __name__ == "__main__":
    sys.exit(main())
