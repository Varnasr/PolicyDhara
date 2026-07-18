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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from fetch_rss import fetch_rss_source
from fetch_scrape import fetch_scrape_source
from classifier import classify_policy, get_sector_slug, is_india_relevant, is_policy_relevant, is_media_source

PROJECT_ROOT = Path(__file__).parent.parent
FEEDS_CONFIG = PROJECT_ROOT / "feeds.json"
DATA_DIR = PROJECT_ROOT / "data"
POLICIES_DIR = PROJECT_ROOT / "src" / "content" / "policies"
MAX_ITEMS_PER_SOURCE = 50
MAX_TOTAL_ITEMS = 2000
# Generalist-news feeds out-produce official sources by an order of
# magnitude, so without a cap the tracker becomes a news reader. Media
# (level == "media") items may fill at most this share of the final
# dataset; government / research / historical items are prioritized.
MEDIA_CAP_FRACTION = 0.4
MAX_PIPELINE_SECONDS = 720  # 12 minutes total (leave 3 min for build/deploy)
HISTORICAL_SEED = PROJECT_ROOT / "data" / "historical_seed.json"


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


AMENDMENTS_FILE = DATA_DIR / "amendments.json"

# Fields to track for amendment detection
_AMENDMENT_FIELDS = ("title", "description", "type")


def _normalize_for_compare(text: str) -> str:
    """Normalize text for comparison (collapse whitespace, lowercase)."""
    return re.sub(r'\s+', ' ', text.strip().lower())


def _title_similarity(a: str, b: str) -> float:
    """Fuzzy title similarity (mirrors titleSimilarity in data.ts)."""
    stop = {"the", "a", "an", "of", "for", "and", "in", "on", "to", "with", "by", "from"}
    def words(t):
        return {w for w in re.sub(r'[^a-z0-9 ]', '', t.lower()).split() if len(w) > 3 and w not in stop}
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    overlap = len(wa & wb)
    return overlap / min(len(wa), len(wb))


def load_amendments() -> dict:
    """Load existing amendment history."""
    if AMENDMENTS_FILE.exists():
        try:
            with open(AMENDMENTS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_amendments(amendments: dict):
    """Persist amendment history to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(AMENDMENTS_FILE, "w") as f:
        json.dump(amendments, f, indent=2, ensure_ascii=False)


def detect_amendments(existing: dict, new_items: list[dict], amendments: dict) -> dict:
    """Detect changes when a policy ID reappears with different content.

    Also uses fuzzy title matching to find near-duplicate policies that
    represent amendments to each other (different IDs, similar titles).

    Two safeguards against unbounded growth (see the IRDAI-page-rotator
    regression that produced 10 495 events on one policy):
      1. Per-(policy, field) history is capped at MAX_AMENDMENTS_PER_FIELD.
      2. GC pass at the end drops amendments for policy IDs no longer in
         `existing` — otherwise dropped policies accumulate zombie history
         forever.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    MAX_AMENDMENTS_PER_FIELD = 20

    def append_event(pid: str, event: dict) -> None:
        history = amendments.setdefault(pid, [])
        history.append(event)
        # Trim per-field history so a single noisy field (rotating page
        # content, unstable classifier) can't dominate the log.
        by_field: dict[str, list] = {}
        for e in history:
            by_field.setdefault(e.get("field", ""), []).append(e)
        for field_events in by_field.values():
            while len(field_events) > MAX_AMENDMENTS_PER_FIELD:
                # Drop the oldest event for this field, in-place in `history`
                oldest = field_events.pop(0)
                history.remove(oldest)
        amendments[pid] = history

    # --- Exact ID match: same policy updated ---
    for item in new_items:
        pid = item["id"]
        if pid not in existing:
            continue
        old = existing[pid]
        for field in _AMENDMENT_FIELDS:
            old_val = old.get(field, "")
            new_val = item.get(field, "")
            if _normalize_for_compare(old_val) != _normalize_for_compare(new_val) and old_val and new_val:
                append_event(pid, {
                    "date": today,
                    "field": field,
                    "old_value": old_val,
                    "new_value": new_val,
                    "source_id": item.get("source_id", ""),
                })
        # Check sectors change
        old_sectors = sorted(old.get("sectors", []))
        new_sectors = sorted(item.get("sectors", []))
        if old_sectors != new_sectors and old_sectors and new_sectors:
            append_event(pid, {
                "date": today,
                "field": "sectors",
                "old_value": ", ".join(old_sectors),
                "new_value": ", ".join(new_sectors),
                "source_id": item.get("source_id", ""),
            })

    # --- Fuzzy title matching: near-duplicate policies across sources ---
    existing_list = list(existing.values())
    for item in new_items:
        if item["id"] in existing:
            continue  # already handled above
        for old in existing_list:
            if old["id"] == item["id"]:
                continue
            sim = _title_similarity(item.get("title", ""), old.get("title", ""))
            if sim >= 0.7:
                # High similarity — treat as an amendment/update to the older policy
                old_desc = old.get("description", "")
                new_desc = item.get("description", "")
                if old_desc and new_desc and _normalize_for_compare(old_desc) != _normalize_for_compare(new_desc):
                    append_event(old["id"], {
                        "date": today,
                        "field": "description",
                        "old_value": old_desc,
                        "new_value": new_desc,
                        "source_id": item.get("source_id", ""),
                    })
                break  # one match per new item

    # --- GC: drop amendments for policies no longer in existing ---
    # A policy can leave `existing` when it drops off the per-source cap
    # or when its ID changes after a dedup pass. Without this, the log
    # grows forever.
    stale_ids = [pid for pid in amendments if pid not in existing]
    for pid in stale_ids:
        del amendments[pid]

    return amendments


def merge_policies(existing: dict, new_items: list[dict]) -> list[dict]:
    """Merge new items with existing, deduplicating by ID, source+title, and title across sources.
    Also detects amendments when a policy reappears with changed text."""

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # --- Amendment detection (before overwriting) ---
    amendments = load_amendments()
    amendments = detect_amendments(existing, new_items, amendments)
    save_amendments(amendments)
    amended_count = sum(1 for v in amendments.values() if v)
    if amended_count:
        print(f"  Amendment tracking: {amended_count} policies with recorded changes")

    for item in new_items:
        pid = item["id"]
        if pid in existing:
            old = existing[pid]
            # Preserve the earlier (better) date if the new item has today's date
            # or a later date — original publication dates are more accurate
            old_date = old.get("date", "")
            new_date = item.get("date", "")
            if old_date and (not new_date or old_date < new_date):
                item["date"] = old_date
            # Preserve the original first_seen so we know when PolicyDhara
            # actually first ingested this item — never reset to today.
            old_first_seen = old.get("first_seen", "")
            if old_first_seen:
                item["first_seen"] = old_first_seen
        # Stamp first_seen on every item that doesn't have one (newly-ingested
        # items, or legacy records from before this field existed). This drives
        # the "Added This Week" / sector-momentum analytics — without it those
        # widgets fall back to p.date and silently misreport ingestion cadence.
        if not item.get("first_seen"):
            item["first_seen"] = today
        existing[pid] = item

    # Defensive backfill: any record already in `existing` but never seen in
    # this fetch cycle (e.g. dropped from the source feed) also needs
    # first_seen so analytics don't break for it.
    for pid, item in existing.items():
        if not item.get("first_seen"):
            item["first_seen"] = today

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

    # Normalize level for known media outlets before the cap and the write —
    # this catches items preserved from an older dataset that were stored with
    # the wrong level (e.g. legacy The Hindu / HT / NDTV RSS stamped "central").
    for item in by_title.values():
        if is_media_source(item.get("source_id", "")):
            item["level"] = "media"

    # Separate historical seed items (source_id == "historical") to ensure they survive the cap
    seed_items = [i for i in by_title.values() if i.get("source_id") == "historical"]
    live_items = [i for i in by_title.values() if i.get("source_id") != "historical"]

    # Cap live items to the total budget while holding news to its share.
    # Seed items are official/historical, so they count toward the non-media
    # base that news is allowed a fraction of.
    live_items = enforce_media_cap(live_items, reserved=len(seed_items))

    # Combine and sort all by date
    all_items = live_items + seed_items
    all_items.sort(key=lambda x: x.get("date", "1970-01-01"), reverse=True)
    return all_items


def enforce_media_cap(live_items: list[dict], reserved: int = 0) -> list[dict]:
    """Trim `live_items` to the item budget while keeping news (level ==
    "media") to at most MEDIA_CAP_FRACTION of the final dataset.

    Government / research items (level != "media") are prioritized: they fill
    slots first, and media items are admitted newest-first only up to the
    cap. `reserved` is the count of non-media items handled elsewhere
    (the historical seed) — they enlarge the base that news is a fraction of,
    but don't consume the returned budget.

    With f = MEDIA_CAP_FRACTION, requiring media / total <= f is equivalent
    to media <= f/(1-f) * non_media, where non_media = reserved + kept
    official items. So a dataset that is mostly official content admits
    proportionally more news, and a thin one admits very little.
    """
    budget = MAX_TOTAL_ITEMS - reserved
    media = [i for i in live_items if i.get("level") == "media"]
    official = [i for i in live_items if i.get("level") != "media"]
    media.sort(key=lambda x: x.get("date", "1970-01-01"), reverse=True)
    official.sort(key=lambda x: x.get("date", "1970-01-01"), reverse=True)

    # Non-media takes priority for the raw slot budget.
    official = official[:budget]
    remaining = budget - len(official)

    non_media_total = reserved + len(official)
    # Floor (not round) so the resulting share never rounds *above* the cap.
    ratio_cap = int(
        (MEDIA_CAP_FRACTION / (1 - MEDIA_CAP_FRACTION)) * non_media_total
    )
    media_slots = max(0, min(remaining, ratio_cap))
    return official + media[:media_slots]


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
    # Generalist media feeds (Livemint Politics, NDTV India, The Hindu
    # National, etc.) carry both Indian policy news and foreign news in the
    # same RSS. `india_only: false` in feeds.json marks these so the fetch
    # loop can apply a relevance filter; everything else (PIB, eGazette,
    # NITI, RBI, state PIBs, research institutes) is trusted unconditionally.
    is_india_only_source = source_config.get("india_only", True)
    items = []
    filtered_count = 0

    print(f"\n--- Fetching: {source_name} ({source_type}) ---")

    try:
        if source_type == "rss":
            # Try url first, then rss_url if available
            raw_items = fetch_rss_source(source_config)
            if not raw_items and source_config.get("rss_url"):
                print(f"  Trying rss_url fallback...")
                fallback_config = dict(source_config, url=source_config["rss_url"])
                raw_items = fetch_rss_source(fallback_config)
        elif source_type == "scrape":
            raw_items = fetch_scrape_source(source_id, source_config)
            # If scrape returned nothing and source has rss_url, try RSS
            if not raw_items and source_config.get("rss_url"):
                print(f"  Scrape empty, trying rss_url fallback...")
                fallback_config = dict(source_config, url=source_config["rss_url"])
                raw_items = fetch_rss_source(fallback_config)
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

            # India-relevance gate. Mixed-content media feeds get filtered;
            # official Indian-government sources are trusted unconditionally.
            # This is what stops NYC-mayor and US-trade stories from showing
            # up on a tracker that's supposed to be about Indian policy.
            if not is_india_only_source and not is_india_relevant(title, description):
                filtered_count += 1
                continue

            # Policy-relevance gate. Same idea, one level narrower: news
            # RSS feeds carry everything the outlet publishes (celebrity
            # divorces, cricket wickets, bike stunts). Items pass this
            # gate only if they hit at least one policy marker. Official
            # sources bypass this check (they're already policy by
            # definition — a PIB press release is policy work regardless
            # of whether the title contains "notified").
            if not is_india_only_source and not is_policy_relevant(title, description):
                filtered_count += 1
                continue

            # If no date from source, try to extract from title
            if not date:
                date = extract_date_from_title(title)

            # Leave date empty if the source didn't expose one and we couldn't
            # parse it from the title. Stamping today's date here pollutes the
            # dataset with fake "issued today" timestamps and makes every
            # enactment-based analytic (homepage "added this week", trend
            # charts, sector momentum) silently report ingestion cadence
            # instead. Items without a date still get first_seen (set in
            # merge_policies) so they don't disappear from the dataset.

            policy_id = generate_id(title, source_id)
            sectors = classify_policy(title, description, source_sectors)

            # Default level: "central" for government sources that don't
            # specify (most PIB ministries), "media" for journalism feeds,
            # "state" / "research" where the config makes it explicit.
            # Previously every source defaulted to "central" — that
            # mis-stamped media coverage as central-government enactment.
            default_level = "media" if not is_india_only_source else "central"
            level = source_config.get("level", default_level)
            # Authoritative override: known news/media outlets are always
            # "media", regardless of feed config or the india_only default.
            # This is what keeps The Hindu / HT / NDTV / Mint RSS out of the
            # policy-only ticker and charts (they were leaking in as "central").
            if is_media_source(source_id):
                level = "media"

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
                "level": level,
                "state": source_config.get("state", ""),
            })

        if filtered_count:
            print(f"  Fetched {len(items)} items (filtered {filtered_count} as not India-relevant)")
        else:
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
    pipeline_start = time.monotonic()

    # Fetch sources concurrently. The pipeline was previously sequential with
    # a per-source SIGALRM timeout, so with 400+ sources it hit the overall
    # time limit after reaching only ~40 of them — most working sources were
    # never tried (that, not broken scrapers, is why the dataset was tiny and
    # news-dominated: the news RSS feeds happened to sort early). A thread
    # pool reaches every source well inside the budget. Per-source timeouts
    # are enforced by the underlying requests/urllib calls (SIGALRM only works
    # on the main thread, so it can't gate worker threads). FETCH_WORKERS is
    # env-tunable so the CI workflow can throttle if a host rate-limits.
    fetch_workers = int(os.environ.get("FETCH_WORKERS", "12"))
    executor = ThreadPoolExecutor(max_workers=fetch_workers)
    future_to_sid = {
        executor.submit(fetch_source, sid, cfg): sid
        for sid, cfg in sources.items()
    }
    print(f"Fetching {len(future_to_sid)} sources with {fetch_workers} workers...")
    completed = 0
    try:
        for future in as_completed(future_to_sid):
            source_id = future_to_sid[future]
            try:
                all_new.extend(future.result())
            except Exception as e:
                errors.append(f"{source_id}: {e}")
                print(f"  FAILED: {source_id} — {e}")
            completed += 1
            # Overall budget guard: stop collecting and abandon stragglers.
            if time.monotonic() - pipeline_start > MAX_PIPELINE_SECONDS:
                pending = len(future_to_sid) - completed
                print(f"\n  Pipeline time limit reached ({int(time.monotonic() - pipeline_start)}s). "
                      f"Collected {completed}/{len(future_to_sid)} sources; abandoning {pending}.")
                break
    finally:
        # Don't block on stragglers past the deadline; cancel what hasn't started.
        executor.shutdown(wait=False, cancel_futures=True)

    print(f"\n{'=' * 60}")
    print(f"Total new items fetched: {len(all_new)} ({len(seed)} seed + {len(all_new) - len(seed)} live)")

    # Merge and deduplicate
    merged = merge_policies(existing, all_new)
    print(f"Total after merge/dedup: {len(merged)}")

    # Write outputs
    write_data_json(merged)
    write_astro_content(merged)

    # Fetch parliamentary committee reports (ParliamentWatch integration)
    try:
        from fetch_committee_reports import scrape_all_committees, write_reports
        print(f"\n{'=' * 60}")
        print("ParliamentWatch: Fetching committee reports...")
        committees, total = scrape_all_committees()
        write_reports(committees, total)
    except Exception as e:
        print(f"  Committee reports fetch failed: {e}")
        errors.append(f"committee_reports: {e}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")

    print(f"\nDone! {len(merged)} policies across {len(sources)} sources.")
    print("=" * 60)


if __name__ == "__main__":
    main()
