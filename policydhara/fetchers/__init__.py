"""Fetcher modules for PolicyDhara — RSS, web scrapers, and API clients."""

from policydhara.fetchers.rss import fetch_rss, parse_rss_xml
from policydhara.fetchers.scraper import fetch_scrape, safe_get
from policydhara.fetchers.base import fetch_source

__all__ = ["fetch_rss", "parse_rss_xml", "fetch_scrape", "safe_get", "fetch_source"]
