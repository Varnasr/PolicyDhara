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

# Known annual events — keyword → (month, day)
# These appear frequently in PIB press releases and gazette notifications.
_KNOWN_EVENTS: dict[str, tuple[int, int]] = {
    "republic day": (1, 26),
    "army day": (1, 15),
    "national voters day": (1, 25),
    "national girl child day": (1, 24),
    "martyrs day": (1, 30),       # also Oct 21 (police), but Jan 30 is main
    "world cancer day": (2, 4),
    "international women": (3, 8),  # International Women's Day
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
    "national unity day": (10, 31),  # Rashtriya Ekta Diwas
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

# Months for parsing "March 3, 2026" or "3 March 2026"
_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}

# Regex for explicit dates in title: "March 3, 2026" or "3 March 2026"
_MONTH_NAMES = "|".join(_MONTH_MAP.keys())
_DATE_IN_TITLE_RE = re.compile(
    rf'(?:({_MONTH_NAMES})\s+(\d{{1,2}})\s*,?\s*((?:19|20)\d{{2}})'  # March 3, 2026
    rf'|(\d{{1,2}})\s+({_MONTH_NAMES})\s*,?\s*((?:19|20)\d{{2}}))',  # 3 March 2026
    re.IGNORECASE,
)


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
    """
    Extract an approximate date from a policy title.
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
