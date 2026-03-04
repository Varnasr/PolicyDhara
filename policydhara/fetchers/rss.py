"""
RSS/Atom feed fetcher with robust handling for Indian government feeds.
Handles UTF-8 BOM, malformed XML, and both RSS 2.0 and Atom formats.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import requests
from dateutil import parser as dateparser

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

TIMEOUT = 30


def _parse_date(text: str) -> str:
    if not text:
        return ""
    try:
        dt = dateparser.parse(text, fuzzy=True)
        if dt:
            return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass
    return ""


def _clean_html(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', clean).strip()


def _sanitize_xml(raw: bytes) -> bytes:
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    text = raw.decode('utf-8', errors='replace')
    for marker in ['<?xml', '<rss', '<feed', '<channel']:
        idx = text.find(marker)
        if idx >= 0:
            text = text[idx:]
            break
    return text.encode('utf-8')


def parse_rss_xml(xml_bytes: bytes) -> list[dict]:
    """Parse RSS/Atom XML bytes into a list of item dicts."""
    cleaned = _sanitize_xml(xml_bytes)

    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError:
        return []

    items: list[dict] = []

    # RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        description = _clean_html(
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
            "date": _parse_date(pub_date),
        })

    # Atom
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
            description = _clean_html(
                (content_el.text if content_el is not None else "")
                or (summary_el.text if summary_el is not None else "")
            )
            published_el = entry.find(f"{{{atom_ns}}}published")
            updated_el = entry.find(f"{{{atom_ns}}}updated")
            date_text = (
                (published_el.text if published_el is not None else "")
                or (updated_el.text if updated_el is not None else "")
            )
            items.append({
                "title": title,
                "description": description[:500],
                "link": link,
                "date": _parse_date(date_text),
            })

    # Plain entry elements (no namespace)
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
            description = _clean_html(summary_el.text if summary_el is not None else "")
            pub_el = entry.find("published") or entry.find("updated")
            date_text = pub_el.text if pub_el is not None else ""
            items.append({
                "title": title,
                "description": description[:500],
                "link": link,
                "date": _parse_date(date_text),
            })

    return items


def fetch_rss(config: dict) -> list[dict]:
    """
    Fetch items from an RSS source. Tries main URL, then backups.

    Args:
        config: Source config dict with 'url' and optional 'backup_urls'.

    Returns:
        List of raw item dicts with title, description, link, date.
    """
    urls = [config["url"]]
    urls.extend(config.get("backup_urls", []))

    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            items = parse_rss_xml(resp.content)
            if items:
                return items
        except requests.RequestException:
            continue

    return []
