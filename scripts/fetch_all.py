#!/usr/bin/env python3
"""
Main orchestrator: fetches from all configured sources, classifies,
deduplicates, and writes policy items as JSON for Astro to consume.

Run: python3 scripts/fetch_all.py
"""

import json
import hashlib
import html
import os
import re
import signal
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from fetch_rss import fetch_rss_source
from fetch_scrape import fetch_scrape_source
from classifier import classify_policy, get_sector_slug

PROJECT_ROOT = Path(__file__).parent.parent
FEEDS_CONFIG = PROJECT_ROOT / "feeds.json"
DATA_DIR = PROJECT_ROOT / "data"
POLICIES_DIR = PROJECT_ROOT / "src" / "content" / "policies"
MAX_ITEMS_PER_SOURCE = 50
MAX_TOTAL_ITEMS = 2000
MAX_SOURCE_SECONDS = 30  # Per-source time limit (kills stuck fetches)
MAX_PIPELINE_SECONDS = 720  # 12 minutes total (leave 3 min for build/deploy)
HISTORICAL_SEED = PROJECT_ROOT / "data" / "historical_seed.json"


class SourceTimeout(Exception):
    pass


def _source_timeout_handler(signum, frame):
    raise SourceTimeout("Source fetch exceeded time limit")


def generate_id(title: str, source: str) -> str:
    """Generate a deterministic unique ID for a policy item.
    Uses source + title only (not date) so the same policy always gets
    the same ID even if its date is corrected later.
    """
    raw = f"{source}:{title}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


_KNOWN_EVENTS: dict[str, tuple[int, int]] = {
    "republic day": (1, 26),
    "army day": (1, 15),
    "national voters day": (1, 25),
    "national girl child day": (1, 24),
    "martyrs day": (1, 30),
    "world cancer day": (2, 4),
    "international women": (3, 8),
    "world wildlife day": (3, 3),
    "national science day": (2, 28),
    "world water day": (3, 22),
    "world health day": (4, 7),
    "ambedkar jayanti": (4, 14),
    "earth day": (4, 22),
    "labour day": (5, 1),
    "may day": (5, 1),
    "world environment day": (6, 5),
    "international yoga day": (6, 21),
    "world population day": (7, 11),
    "kargil vijay diwas": (7, 26),
    "independence day": (8, 15),
    "national sports day": (8, 29),
    "teachers day": (9, 5),
    "hindi diwas": (9, 14),
    "gandhi jayanti": (10, 2),
    "mahatma gandhi jayanti": (10, 2),
    "world food day": (10, 16),
    "national unity day": (10, 31),
    "rashtriya ekta diwas": (10, 31),
    "children's day": (11, 14),
    "childrens day": (11, 14),
    "national constitution day": (11, 26),
    "constitution day": (11, 26),
    "navy day": (12, 4),
    "armed forces flag day": (12, 7),
    "human rights day": (12, 10),
    "national energy conservation day": (12, 14),
    "good governance day": (12, 25),
    "vijay diwas": (12, 16),
}

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}

_MONTH_NAMES = "|".join(_MONTH_MAP.keys())
_DATE_IN_TITLE_RE = re.compile(
    rf'(?:({_MONTH_NAMES})\s+(\d{{1,2}})\s*,?\s*((?:19|20)\d{{2}})'
    rf'|(\d{{1,2}})\s+({_MONTH_NAMES})\s*,?\s*((?:19|20)\d{{2}}))',
    re.IGNORECASE,
)


def extract_date_from_title(title: str) -> str:
    """
    Extract an approximate date from a policy title when no real date is available.
    Never returns a date in the future.

    Strategy (in order):
    1. Budget/fiscal documents → Feb 1 of that year
    2. Explicit date in title ("March 3, 2026") → exact date
    3. Known annual events (Republic Day, etc.) → fixed date
    4. Year in title ("Act, 2025") → June 1 approximation
    """
    text = title.strip()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    current_year = datetime.now(timezone.utc).year

    def _cap(candidate: str) -> str:
        return candidate if candidate <= today else today

    # 1. Budget-related documents → Feb 1
    m = re.search(r'[Bb]udget\s+(?:Document[s]?\s*[,.]?\s*)?(\d{4})', text)
    if not m:
        text_lower = text.lower()
        if 'budget' in text_lower or 'fiscal' in text_lower or 'outcome framework' in text_lower:
            m = re.search(r'(\d{4})\s*[-–]\s*\d{2,4}', text)
    if m:
        return _cap(f"{m.group(1)}-02-01")

    # 2. Explicit date in title: "March 3, 2026" or "3 March 2026"
    dm = _DATE_IN_TITLE_RE.search(text)
    if dm:
        if dm.group(1):  # "March 3, 2026" form
            month = _MONTH_MAP.get(dm.group(1).lower())
            day = int(dm.group(2))
            year = int(dm.group(3))
        else:  # "3 March 2026" form
            day = int(dm.group(4))
            month = _MONTH_MAP.get(dm.group(5).lower())
            year = int(dm.group(6))
        if month and 1 <= day <= 31 and 1990 <= year <= current_year:
            return _cap(f"{year}-{month:02d}-{day:02d}")

    # 3. Known annual events with fixed dates
    text_lower = text.lower()
    year_match = re.search(r'(20\d{2})', text)
    if year_match:
        year_str = year_match.group(1)
        year_int = int(year_str)
        if 1990 <= year_int <= current_year:
            for keyword, (month, day) in _KNOWN_EVENTS.items():
                if keyword in text_lower:
                    return _cap(f"{year_str}-{month:02d}-{day:02d}")

    # 4. Year in title as last resort → June 1 approximation
    m = re.search(r'[\s,(\[]\s*((?:19|20)\d{2})\s*[-)\].,]?\s*$', text)
    if not m:
        m = re.search(r'[\s,(\[]\s*((?:19|20)\d{2})\s*[-–]\s*\d{2,4}', text)
    if not m:
        matches = re.findall(r'(?:19|20)\d{2}', text)
        if matches:
            year = max(int(y) for y in matches)
            if 1990 <= year <= current_year:
                return _cap(f"{year}-06-01")
        return ""

    year = int(m.group(1))
    if 1990 <= year <= current_year:
        return _cap(f"{year}-06-01")
    return ""


# Titles that are navigation junk, page headers, or too generic to be policies
_JUNK_TITLE_PATTERNS = [
    r'^Recent (Extra Ordinary |Weekly )?Gazettes',
    r'^Gazettes on Demand',
    r'^(Parliament|Session\s*Track|Legislature Track|Bills Parliament)$',
    r'^(Discussion Papers|About the .+ Fellowship|Careers|Press Releases?)$',
    r'^(Home|Login|Register|Contact Us|Sitemap|Disclaimer|FAQ)$',
    r'^(Skip to |Jump to )',
    r'^Money Market Operations',
    r'^Statement\s*\n',
]
_JUNK_RE = re.compile('|'.join(_JUNK_TITLE_PATTERNS), re.IGNORECASE)


def is_valid_title(title: str) -> bool:
    """Reject navigation junk, page headers, and garbled scraper output."""
    if not title or len(title) < 5:
        return False
    if _JUNK_RE.search(title):
        return False
    # Reject garbled scrapes (very long with barely any spaces)
    if len(title) > 80 and title.count(' ') < len(title) / 20:
        return False
    return True


def load_historical_seed() -> list[dict]:
    """Load curated historical policy data (UPA I onwards)."""
    if not HISTORICAL_SEED.exists():
        return []
    try:
        with open(HISTORICAL_SEED) as f:
            raw_items = json.load(f)
        items = []
        for raw in raw_items:
            title = raw.get("title", "").strip()
            if not title:
                continue
            source_id = raw.get("source_id", "historical")
            policy_id = generate_id(title, source_id)
            sectors = raw.get("sectors", [])
            items.append({
                "id": policy_id,
                "title": title,
                "description": raw.get("description", ""),
                "link": raw.get("link", ""),
                "date": raw.get("date", ""),
                "source_id": source_id,
                "source_name": raw.get("source_name", "Historical Record"),
                "source_short": raw.get("source_short", "Archive"),
                "sectors": sectors,
                "sector_slugs": [get_sector_slug(s) for s in sectors],
                "type": raw.get("type", "policy"),
                "level": raw.get("level", "central"),
                "state": raw.get("state", ""),
            })
        print(f"  Loaded {len(items)} historical seed policies")
        return items
    except Exception as e:
        print(f"  Warning: could not load historical seed: {e}")
        return []


def load_existing_policies() -> dict:
    """Load already-fetched policies to avoid duplicates."""
    existing = {}
    data_file = DATA_DIR / "policies.json"
    if data_file.exists():
        try:
            with open(data_file) as f:
                items = json.load(f)
                for item in items:
                    existing[item.get("id", "")] = item
        except (json.JSONDecodeError, KeyError):
            pass
    return existing


def merge_policies(existing: dict, new_items: list[dict]) -> list[dict]:
    """Merge new items with existing, deduplicating by ID, source+title, and title across sources."""
    for item in new_items:
        existing[item["id"]] = item

    # First pass: deduplicate by source+title (keep the one with the best date)
    seen: dict[tuple, dict] = {}
    for item in existing.values():
        key = (item.get("source_id", ""), item.get("title", ""))
        if key in seen:
            old = seen[key]
            if item.get("date", "") > old.get("date", ""):
                seen[key] = item
        else:
            seen[key] = item

    # Second pass: deduplicate by title alone across sources
    # When the same article appears from multiple PIB regional offices or
    # similar sources, keep the one from the most authoritative source.
    SOURCE_PRIORITY = {"pib": 0, "egazette": 1, "india_code": 2}
    by_title: dict[str, dict] = {}
    for item in seen.values():
        title = item.get("title", "").strip()
        if title in by_title:
            old = by_title[title]
            old_prio = SOURCE_PRIORITY.get(old.get("source_id", ""), 99)
            new_prio = SOURCE_PRIORITY.get(item.get("source_id", ""), 99)
            # Keep: higher priority source, or better date, or central over state
            if new_prio < old_prio:
                by_title[title] = item
            elif new_prio == old_prio and item.get("level", "") == "central" and old.get("level", "") != "central":
                by_title[title] = item
        else:
            by_title[title] = item

    # Sort by date (newest first) and cap total
    all_items = sorted(
        by_title.values(),
        key=lambda x: x.get("date", "1970-01-01"),
        reverse=True
    )
    return all_items[:MAX_TOTAL_ITEMS]


def write_astro_content(policies: list[dict]):
    """Write individual JSON files for Astro content collection."""
    # Clean existing
    if POLICIES_DIR.exists():
        for f in POLICIES_DIR.glob("*.json"):
            f.unlink()
    POLICIES_DIR.mkdir(parents=True, exist_ok=True)

    for item in policies:
        filepath = POLICIES_DIR / f"{item['id']}.json"
        with open(filepath, "w") as f:
            json.dump(item, f, indent=2, ensure_ascii=False)

    print(f"  Wrote {len(policies)} content files to {POLICIES_DIR}")


def write_data_json(policies: list[dict]):
    """Write combined data file for the dashboard."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Full policies data
    with open(DATA_DIR / "policies.json", "w") as f:
        json.dump(policies, f, indent=2, ensure_ascii=False)

    # Sector summary
    sector_counts: dict[str, int] = {}
    for p in policies:
        for s in p.get("sectors", []):
            sector_counts[s] = sector_counts.get(s, 0) + 1
    with open(DATA_DIR / "sectors.json", "w") as f:
        json.dump(sector_counts, f, indent=2)

    # Source summary
    source_counts: dict[str, int] = {}
    for p in policies:
        src = p.get("source_id", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    with open(DATA_DIR / "sources.json", "w") as f:
        json.dump(source_counts, f, indent=2)

    # Metadata
    meta = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_policies": len(policies),
        "total_sources": len(source_counts),
        "total_sectors": len(sector_counts),
        "sector_counts": sector_counts,
        "source_counts": source_counts
    }
    with open(DATA_DIR / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"  Wrote data files to {DATA_DIR}")


def fetch_api_source(source_id: str, source_config: dict) -> list[dict]:
    """Fetch items from a JSON API source."""
    import requests
    url = source_config.get("url", "")
    if not url:
        return []

    try:
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "PolicyDhara/1.0 (+https://github.com/Varnasr/PolicyDhara)"
        })
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  API error for {url}: {e}")
        return []

    items = []
    # PolicyRadar format
    if "top_articles" in data:
        for article in data["top_articles"]:
            date_str = article.get("publication_date", "")
            if date_str:
                date_str = date_str[:10]  # "2026-03-03T09:28:10+00:00" → "2026-03-03"
            items.append({
                "title": article.get("title", ""),
                "description": article.get("summary", ""),
                "link": article.get("url", ""),
                "date": date_str,
            })
    # Generic list format
    elif isinstance(data, list):
        for item in data:
            items.append({
                "title": item.get("title", ""),
                "description": item.get("description", item.get("summary", "")),
                "link": item.get("url", item.get("link", "")),
                "date": item.get("date", item.get("published", ""))[:10] if item.get("date") or item.get("published") else "",
            })

    return items


def fetch_source(source_id: str, source_config: dict) -> list[dict]:
    """Fetch items from a single source and classify them."""
    source_type = source_config.get("type", "")
    source_name = source_config.get("name", source_id)
    source_sectors = source_config.get("covers_sectors", "all")
    items = []

    print(f"\n--- Fetching: {source_name} ({source_type}) ---")

    try:
        if source_type == "rss":
            raw_items = fetch_rss_source(source_config)
        elif source_type == "scrape":
            raw_items = fetch_scrape_source(source_id, source_config)
        elif source_type == "api":
            raw_items = fetch_api_source(source_id, source_config)
        else:
            print(f"  Unknown source type: {source_type}")
            return []

        for raw in raw_items[:MAX_ITEMS_PER_SOURCE]:
            title = html.unescape(raw.get("title", "")).strip()
            title = re.sub(r'\s+', ' ', title)  # collapse whitespace
            if not is_valid_title(title):
                continue

            description = html.unescape(raw.get("description", "")).strip()
            link = raw.get("link", "")
            date = raw.get("date", "").strip()

            # If no date from source, try to extract from title
            if not date:
                date = extract_date_from_title(title)

            # Last resort: use today's date
            if not date:
                date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            policy_id = generate_id(title, source_id)
            sectors = classify_policy(title, description, source_sectors)

            items.append({
                "id": policy_id,
                "title": title,
                "description": description[:500] if description else "",
                "link": link,
                "date": date,
                "source_id": source_id,
                "source_name": source_name,
                "source_short": source_config.get("short_name", source_name),
                "sectors": sectors,
                "sector_slugs": [get_sector_slug(s) for s in sectors],
                "type": categorize_item_type(title, description),
                "level": source_config.get("level", "central"),
                "state": source_config.get("state", ""),
            })

        print(f"  Fetched {len(items)} items")

    except Exception as e:
        print(f"  ERROR fetching {source_name}: {e}")
        traceback.print_exc()

    return items


def categorize_item_type(title: str, description: str) -> str:
    """Categorize the type of policy item."""
    text = f"{title} {description}".lower()
    if any(w in text for w in ["bill", "legislation", "act ", "amendment"]):
        return "legislation"
    if any(w in text for w in ["notification", "gazette", "order", "circular"]):
        return "notification"
    if any(w in text for w in ["scheme", "yojana", "mission", "programme", "program"]):
        return "scheme"
    if any(w in text for w in ["budget", "fiscal", "economic survey"]):
        return "budget"
    if any(w in text for w in ["report", "paper", "study", "research", "analysis"]):
        return "research"
    if any(w in text for w in ["press release", "statement", "announces"]):
        return "announcement"
    return "policy"


def main():
    print("=" * 60)
    print("INDIA POLICY TRACKER — Data Fetch")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # Load config
    with open(FEEDS_CONFIG) as f:
        config = json.load(f)

    sources = config.get("sources", {})
    print(f"Configured sources: {len(sources)}")

    # Load existing
    existing = load_existing_policies()
    print(f"Existing policies: {len(existing)}")

    # Load historical seed data (UPA I onwards)
    seed = load_historical_seed()

    # Fetch from all sources
    all_new = list(seed)
    errors = []
    skipped = 0
    pipeline_start = time.monotonic()

    for source_id, source_config in sources.items():
        # Check pipeline-level time limit
        elapsed = time.monotonic() - pipeline_start
        if elapsed > MAX_PIPELINE_SECONDS:
            remaining = len(sources) - (skipped + len(all_new) - len(seed) + len(errors))
            print(f"\n  Pipeline time limit reached ({int(elapsed)}s). Skipping remaining sources.")
            break

        try:
            # Set per-source timeout via SIGALRM
            old_handler = signal.signal(signal.SIGALRM, _source_timeout_handler)
            signal.alarm(MAX_SOURCE_SECONDS)
            try:
                items = fetch_source(source_id, source_config)
                all_new.extend(items)
            finally:
                signal.alarm(0)  # Cancel alarm
                signal.signal(signal.SIGALRM, old_handler)
            # Rate limit between sources
            time.sleep(0.5)
        except SourceTimeout:
            errors.append(f"{source_id}: timed out after {MAX_SOURCE_SECONDS}s")
            print(f"  TIMED OUT: {source_id} (>{MAX_SOURCE_SECONDS}s)")
        except Exception as e:
            errors.append(f"{source_id}: {e}")
            print(f"  FAILED: {source_id} — {e}")

    print(f"\n{'=' * 60}")
    print(f"Total new items fetched: {len(all_new)} ({len(seed)} seed + {len(all_new) - len(seed)} live)")

    # Merge and deduplicate
    merged = merge_policies(existing, all_new)
    print(f"Total after merge/dedup: {len(merged)}")

    # Write outputs
    write_data_json(merged)
    write_astro_content(merged)

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")

    print(f"\nDone! {len(merged)} policies across {len(sources)} sources.")
    print("=" * 60)


if __name__ == "__main__":
    main()
