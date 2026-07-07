#!/usr/bin/env python3
"""
Probe every source in feeds.json and update data/source_health.json with the
result. Optionally open a GitHub issue listing sources that have consecutively
returned zero items for N+ probes.

This script is a reporter, not a gate — it never fails the main data-refresh
pipeline. Its output tells maintainers which URLs have gone stale so they can
be replaced or dropped.

Usage:
  python3 scripts/check_source_health.py                # probe + update JSON
  python3 scripts/check_source_health.py --report-only  # print stale sources, no probe
  python3 scripts/check_source_health.py --open-issue   # also open a GH issue

Env vars:
  GH_TOKEN         # required for --open-issue
  GH_REPO          # e.g. "Varnasr/PolicyDhara"; required for --open-issue
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FEEDS_FILE = PROJECT_ROOT / "feeds.json"
HEALTH_FILE = DATA_DIR / "source_health.json"

STALE_STREAK_THRESHOLD = 3  # weeks of zero-item probes before we flag
TIMEOUT = 12
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)


def load_health() -> dict:
    if HEALTH_FILE.exists():
        try:
            return json.loads(HEALTH_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_health(health: dict) -> None:
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_FILE.write_text(json.dumps(health, indent=2, ensure_ascii=False))


def probe(url: str) -> tuple[int, int]:
    """HEAD-like probe. Returns (status_code, body_bytes). status 0 = network error."""
    try:
        req = Request(url, headers={"User-Agent": UA})
        with urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(4096)
            return resp.status, len(body)
    except HTTPError as e:
        return e.code, 0
    except URLError:
        return 0, 0
    except (OSError, ValueError):
        return 0, 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--open-issue", action="store_true")
    args = ap.parse_args()

    feeds = json.loads(FEEDS_FILE.read_text())
    sources = feeds["sources"]
    health = load_health()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not args.report_only:
        print(f"Probing {len(sources)} sources...")
        for i, (sid, cfg) in enumerate(sources.items(), 1):
            url = cfg.get("url", "")
            if not url:
                continue
            status, body_len = probe(url)
            entry = health.setdefault(sid, {"first_probed": today, "streak": 0})
            entry["last_probed"] = today
            entry["last_status"] = status
            entry["last_body_len"] = body_len
            # A source is "healthy" this probe if we got 2xx AND a non-trivial body
            healthy = 200 <= status < 300 and body_len > 200
            if healthy:
                entry["streak"] = 0
                entry["last_healthy"] = today
            else:
                entry["streak"] = entry.get("streak", 0) + 1
            if i % 25 == 0:
                print(f"  {i}/{len(sources)}...")
            time.sleep(0.15)  # be polite

        save_health(health)
        print(f"Health data written to {HEALTH_FILE}")

    # Report stale sources
    stale = []
    for sid, entry in health.items():
        if entry.get("streak", 0) >= STALE_STREAK_THRESHOLD and sid in sources:
            stale.append(
                (sid, sources[sid].get("name", sid), entry.get("streak", 0),
                 entry.get("last_status", 0), entry.get("last_healthy", "never"))
            )

    print(f"\nStale sources (>= {STALE_STREAK_THRESHOLD} consecutive failing probes): {len(stale)}")
    for sid, name, streak, status, last_healthy in stale[:30]:
        print(f"  {sid:35} streak={streak:2} last_status={status:3} last_healthy={last_healthy} | {name}")

    if args.open_issue and stale:
        _open_issue(stale)

    return 0


def _open_issue(stale: list) -> None:
    token = os.environ.get("GH_TOKEN", "").strip()
    repo = os.environ.get("GH_REPO", "").strip()
    if not token or not repo:
        print("  GH_TOKEN/GH_REPO not set — skipping issue creation")
        return

    body_lines = [
        f"Automated source-health report — {datetime.now(timezone.utc).date()}",
        "",
        f"The following {len(stale)} source(s) have returned no usable content "
        f"for {STALE_STREAK_THRESHOLD}+ consecutive weekly probes. Consider "
        "updating the URL, replacing the source, or removing the entry.",
        "",
        "| Source ID | Streak | Last HTTP | Last healthy | Name |",
        "|---|---|---|---|---|",
    ]
    for sid, name, streak, status, last_healthy in stale:
        body_lines.append(f"| `{sid}` | {streak} | {status} | {last_healthy} | {name} |")

    payload = json.dumps({
        "title": f"[source-health] {len(stale)} sources have gone stale",
        "body": "\n".join(body_lines),
        "labels": ["source-health", "maintenance"],
    }).encode("utf-8")
    req = Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "policydhara-source-health",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.load(resp)
            print(f"  Opened issue #{data.get('number')}: {data.get('html_url')}")
    except HTTPError as e:
        print(f"  ! Failed to open issue: HTTP {e.code} {e.read()!r}")


if __name__ == "__main__":
    sys.exit(main())
