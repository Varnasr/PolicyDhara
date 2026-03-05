"""
Base fetch orchestration — routes source configs to the right fetcher.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from policydhara.models import Policy
from policydhara.classifier import PolicyClassifier
from policydhara.fetchers.rss import fetch_rss
from policydhara.fetchers.scraper import fetch_scrape

_classifier = PolicyClassifier()

MAX_ITEMS_PER_SOURCE = 50

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


def _is_valid_title(title: str) -> bool:
    """Reject navigation junk, page headers, and garbled scraper output."""
    if not title or len(title) < 5:
        return False
    if _JUNK_RE.search(title):
        return False
    # Reject garbled scrapes (very long with barely any spaces)
    if len(title) > 80 and title.count(' ') < len(title) / 20:
        return False
    return True


def _categorize_type(title: str, description: str) -> str:
    """Categorize the type of policy item from its text."""
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


def _extract_date_from_title(title: str) -> str:
    """Extract an approximate date from a policy title. Never returns a future date."""
    text = title.strip()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    current_year = datetime.now(timezone.utc).year

    def _cap(candidate: str) -> str:
        return candidate if candidate <= today else today

    # Budget-related documents → Feb 1
    m = re.search(r'[Bb]udget\s+(?:Document[s]?\s*[,.]?\s*)?(\d{4})', text)
    if not m:
        m = re.search(r'(\d{4})\s*[-–]\s*\d{2,4}\s*$', text) if 'budget' in text.lower() or 'fiscal' in text.lower() or 'outcome framework' in text.lower() else None
    if m:
        return _cap(f"{m.group(1)}-02-01")

    # Known annual events with fixed dates
    text_lower = text.lower()
    year_match = re.search(r'(20\d{2})', text)
    if year_match:
        year = year_match.group(1)
        if 'world wildlife day' in text_lower:
            return _cap(f"{year}-03-03")
        if 'republic day' in text_lower:
            return _cap(f"{year}-01-26")
        if 'independence day' in text_lower:
            return _cap(f"{year}-08-15")

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


def fetch_source(
    source_id: str,
    source_config: dict,
    classifier: PolicyClassifier | None = None,
) -> list[Policy]:
    """
    Fetch policy items from a single source, classify, and return as Policy objects.

    Args:
        source_id: Unique identifier for the source.
        source_config: Configuration dict with keys like type, url, name, etc.
        classifier: Optional custom classifier instance.

    Returns:
        List of Policy objects fetched from the source.
    """
    cls = classifier or _classifier
    source_type = source_config.get("type", "")
    source_name = source_config.get("name", source_id)
    source_sectors = source_config.get("covers_sectors", "all")

    raw_items: list[dict] = []

    if source_type == "rss":
        raw_items = fetch_rss(source_config)
    elif source_type in ("scrape", "api"):
        raw_items = fetch_scrape(source_id, source_config)
    else:
        return []

    policies: list[Policy] = []
    for raw in raw_items[:MAX_ITEMS_PER_SOURCE]:
        title = html.unescape(raw.get("title", "")).strip()
        title = re.sub(r'\s+', ' ', title)  # collapse whitespace
        if not _is_valid_title(title):
            continue

        description = html.unescape(raw.get("description", "")).strip()
        link = raw.get("link", "")
        date = raw.get("date", "").strip()

        if not date:
            date = _extract_date_from_title(title)
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        policy_id = Policy.generate_id(title, source_id)
        sectors = cls.classify(title, description, source_sectors)

        policies.append(Policy(
            id=policy_id,
            title=title,
            description=description[:500] if description else "",
            link=link,
            date=date,
            source_id=source_id,
            source_name=source_name,
            source_short=source_config.get("short_name", source_name),
            sectors=sectors,
            sector_slugs=[Policy.sector_slug(s) for s in sectors],
            type=_categorize_type(title, description),
            level=source_config.get("level", "central"),
            state=source_config.get("state", ""),
        ))

    return policies
