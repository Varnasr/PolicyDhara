"""
Base fetch orchestration — routes source configs to the right fetcher.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from policydhara.models import Policy
from policydhara.classifier import PolicyClassifier
from policydhara.fetchers.rss import fetch_rss
from policydhara.fetchers.scraper import fetch_scrape

_classifier = PolicyClassifier()

MAX_ITEMS_PER_SOURCE = 50


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
    """Extract an approximate date from a policy title when no real date is available."""
    text = title.strip()

    m = re.search(r'[Bb]udget\s+(\d{4})', text)
    if m:
        return f"{m.group(1)}-02-01"

    m = re.search(r'[\s,(\[]\s*((?:19|20)\d{2})\s*[-)\].,]?\s*$', text)
    if not m:
        m = re.search(r'[\s,(\[]\s*((?:19|20)\d{2})\s*[-–]\s*\d{2,4}', text)
    if not m:
        matches = re.findall(r'(?:19|20)\d{2}', text)
        if matches:
            year = max(int(y) for y in matches)
            if 1990 <= year <= datetime.now(timezone.utc).year + 1:
                return f"{year}-06-01"
        return ""

    year = int(m.group(1))
    if 1990 <= year <= datetime.now(timezone.utc).year + 1:
        return f"{year}-06-01"
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
        title = raw.get("title", "").strip()
        if not title:
            continue

        description = raw.get("description", "").strip()
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
