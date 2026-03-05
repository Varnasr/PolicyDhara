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
HISTORICAL_SEED = PROJECT_ROOT / "data" / "historical_seed.json"


def generate_id(title: str, source: str) -> str:
    """Generate a deterministic unique ID for a policy item.
    Uses source + title only (not date) so the same policy always gets
    the same ID even if its date is corrected later.
    """
    raw = f"{source}:{title}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def extract_date_from_title(title: str) -> str:
    """
    Extract an approximate date from a policy title when no real date is available.
    E.g. "The Securities Markets Code, 2025" → "2025-06-01"
         "Union Budget 2026-27" → "2026-02-01"
    Returns empty string if no year found.
    Never returns a date in the future.
    """
    import re
    text = title.strip()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    current_year = datetime.now(timezone.utc).year

    def _cap_to_today(candidate: str) -> str:
        return candidate if candidate <= today else today

    # Match budget-related documents → use Feb 1 of that year
    m = re.search(r'[Bb]udget\s+(?:Document[s]?\s*[,.]?\s*)?(\d{4})', text)
    if not m:
        m = re.search(r'(\d{4})\s*[-–]\s*\d{2,4}\s*$', text) if 'budget' in text.lower() or 'fiscal' in text.lower() or 'outcome framework' in text.lower() else None
    if m:
        return _cap_to_today(f"{m.group(1)}-02-01")

    # Known annual events with fixed dates
    text_lower = text.lower()
    year_match = re.search(r'(20\d{2})', text)
    if year_match:
        year = year_match.group(1)
        if 'world wildlife day' in text_lower:
            return _cap_to_today(f"{year}-03-03")
        if 'republic day' in text_lower:
            return _cap_to_today(f"{year}-01-26")
        if 'independence day' in text_lower:
            return _cap_to_today(f"{year}-08-15")

    # Match explicit year patterns: "Bill, 2025" or "Code, 2024" or "Act 2023" or "(2025)"
    m = re.search(r'[\s,(\[]\s*((?:19|20)\d{2})\s*[-)\].,]?\s*$', text)
    if not m:
        m = re.search(r'[\s,(\[]\s*((?:19|20)\d{2})\s*[-–]\s*\d{2,4}', text)
    if not m:
        # Try anywhere in the title as last resort
        matches = re.findall(r'(?:19|20)\d{2}', text)
        if matches:
            year = max(int(y) for y in matches)
            if 1990 <= year <= current_year:
                return _cap_to_today(f"{year}-06-01")
        return ""

    year = int(m.group(1))
    if 1990 <= year <= current_year:
        return _cap_to_today(f"{year}-06-01")
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
            # API sources require specific handling per source
            # For now, treat like scrape with URL fetch
            raw_items = fetch_scrape_source(source_id, source_config)
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

    for source_id, source_config in sources.items():
        try:
            items = fetch_source(source_id, source_config)
            all_new.extend(items)
            # Rate limit between sources
            time.sleep(1)
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
