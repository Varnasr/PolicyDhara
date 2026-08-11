#!/usr/bin/env python3
"""
RSS feed fetcher for Indian policy sources.
Uses stdlib xml.etree with robust handling for:
- UTF-8 BOM (PIB feeds)
- Leading whitespace/HTML before XML (CPR, WordPress feeds)
- Atom and RSS 2.0 formats
- Namespace-prefixed elements
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from dateutil import parser as dateparser

# Browser-like headers — many .gov.in sites block bot User-Agents
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

TIMEOUT = 10


def parse_date(text: str) -> str:
    """Parse date string into YYYY-MM-DD."""
    if not text:
        return ""
    try:
        dt = dateparser.parse(text, fuzzy=True)
        if dt:
            return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass
    return ""


def clean_html(text: str) -> str:
    """Strip HTML tags from text."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def sanitize_xml(raw: bytes) -> bytes:
    """
    Clean raw response bytes for XML parsing:
    - Strip UTF-8 BOM
    - Remove content before <?xml or <rss or <feed declaration
    - Handle encoding issues
    """
    # Strip UTF-8 BOM
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]

    # Find the start of actual XML content
    text = raw.decode('utf-8', errors='replace')

    # Find XML declaration or root element
    for marker in ['<?xml', '<rss', '<feed', '<channel']:
        idx = text.find(marker)
        if idx >= 0:
            text = text[idx:]
            break

    return text.encode('utf-8')


def _lxml_root(cleaned: bytes):
    """Parse with lxml in recover mode — tolerates undefined entities,
    invalid tokens, and other malformedness that stdlib ElementTree rejects.
    Returns a root whose API (iter/find/findtext/get/.text) matches ET, or
    None if even recovery fails. lxml ships with BeautifulSoup, already a dep.
    """
    try:
        import lxml.etree as LET
    except ImportError:
        return None
    try:
        # No huge_tree: keep libxml2's node/depth limits as a guard against
        # hostile or corrupt feeds from third-party hosts.
        parser = LET.XMLParser(recover=True, resolve_entities=False)
        root = LET.fromstring(cleaned, parser=parser)
        # An empty recovered tree means recovery produced nothing usable.
        return root if root is not None and len(root) else None
    except Exception:
        return None


def parse_rss_xml(xml_bytes: bytes) -> list[dict]:
    """Parse RSS/Atom XML into a list of items."""
    items = []

    cleaned = sanitize_xml(xml_bytes)

    root = None
    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError as e:
        # Strict stdlib parse failed (undefined entity, invalid token, stray
        # markup). Retry with lxml's recover mode before giving up — this
        # revives WordPress/journal feeds that emit slightly broken XML.
        root = _lxml_root(cleaned)
        if root is None:
            print(f"  XML parse error: {e}")
            return []

    # Handle RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue

        description = clean_html(
            item.findtext("description")
            or item.findtext("summary")
            or item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
            or ""
        )
        link = (item.findtext("link") or "").strip()
        pub_date = (
            item.findtext("pubDate")
            or item.findtext("date")
            or item.findtext("{http://purl.org/dc/elements/1.1/}date")
            or ""
        ).strip()

        items.append({
            "title": title,
            "description": description[:500],
            "link": link,
            "date": parse_date(pub_date),
        })

    # Handle Atom feeds if no RSS items found
    if not items:
        atom_ns = "http://www.w3.org/2005/Atom"
        for entry in root.iter(f"{{{atom_ns}}}entry"):
            title_el = entry.find(f"{{{atom_ns}}}title")
            title = (title_el.text if title_el is not None else "").strip()
            if not title:
                continue

            link = ""
            for link_el in entry.findall(f"{{{atom_ns}}}link"):
                href = link_el.get("href", "")
                rel = link_el.get("rel", "alternate")
                if rel == "alternate" and href:
                    link = href
                    break
                if href and not link:
                    link = href

            content_el = entry.find(f"{{{atom_ns}}}content")
            summary_el = entry.find(f"{{{atom_ns}}}summary")
            description = clean_html(
                (content_el.text if content_el is not None else "")
                or (summary_el.text if summary_el is not None else "")
            )

            updated_el = entry.find(f"{{{atom_ns}}}updated")
            published_el = entry.find(f"{{{atom_ns}}}published")
            date_text = (
                (published_el.text if published_el is not None else "")
                or (updated_el.text if updated_el is not None else "")
            )

            items.append({
                "title": title,
                "description": description[:500],
                "link": link,
                "date": parse_date(date_text),
            })

    # Also try plain entry elements without namespace
    if not items:
        for entry in root.iter("entry"):
            title_el = entry.find("title")
            title = (title_el.text if title_el is not None else "").strip()
            if not title:
                continue

            link = ""
            for link_el in entry.findall("link"):
                href = link_el.get("href", "")
                if href:
                    link = href
                    break

            summary_el = entry.find("summary") or entry.find("content")
            description = clean_html(summary_el.text if summary_el is not None else "")

            pub_el = entry.find("published") or entry.find("updated")
            date_text = pub_el.text if pub_el is not None else ""

            items.append({
                "title": title,
                "description": description[:500],
                "link": link,
                "date": parse_date(date_text),
            })

    return items


def fetch_rss_source(config: dict) -> list[dict]:
    """
    Fetch items from an RSS source.
    Tries main URL first, then backup URLs.
    """
    urls = [config["url"]]
    urls.extend(config.get("backup_urls", []))

    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()

            items = parse_rss_xml(resp.content)

            if items:
                print(f"  RSS OK: {len(items)} items from {url}")
                return items
            else:
                print(f"  RSS: no items parsed from {url}")

        except requests.RequestException as e:
            print(f"  RSS error for {url}: {e}")
            continue

    return []
