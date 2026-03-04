"""
Web scraper for Indian policy sources without RSS/API.
Includes source-specific parsers for PIB, India Code, eGazette, RBI,
Parliament, NITI Aayog, World Bank API, and a generic ministry scraper.
"""

from __future__ import annotations

import re
import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

TIMEOUT = 30


def safe_get(url: str, headers: dict | None = None) -> requests.Response | None:
    """HTTP GET with retries and browser-like headers."""
    hdrs = headers or HEADERS
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=hdrs, timeout=TIMEOUT, verify=True, allow_redirects=True)
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt == 2:
                return None
    return None


def _parse_date_text(text: str) -> str:
    if not text:
        return ""
    try:
        dt = dateparser.parse(text, fuzzy=True)
        if dt:
            return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass
    return ""


def _parse_unix_timestamp(ts) -> str:
    try:
        val = int(ts) if not isinstance(ts, int) else ts
        dt = datetime.fromtimestamp(val, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        return ""


# ── Source-specific parsers ──────────────────────────────────────────


def scrape_pib(config: dict) -> list[dict]:
    url = config.get("url", "https://pib.gov.in/indexd.aspx?reg=3&lang=1")
    resp = safe_get(url)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    items = []
    seen = set()
    for a in soup.select("a[href*='PressRele'], a[href*='PRID']"):
        title = a.get_text(strip=True)
        if not title or len(title) < 10:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = f"https://pib.gov.in{href}"
        prid = re.search(r'PRID=(\d+)', href)
        key = prid.group(1) if prid else title
        if key in seen:
            continue
        seen.add(key)
        items.append({"title": title[:200], "description": f"Government of India press release: {title[:300]}", "link": href, "date": ""})
    return items


def scrape_india_code(config: dict) -> list[dict]:
    items = []
    current_year = datetime.now(timezone.utc).year
    for year in [current_year, current_year - 1]:
        url = f"https://www.indiacode.nic.in/handle/123456789/1362/browse?type=actyear&value={year}"
        resp = safe_get(url)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for tr in soup.select("table tr"):
            cells = tr.select("td")
            if not cells or len(cells) < 3:
                continue
            date_text = cells[0].get_text(strip=True)
            title = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            link_el = tr.select_one("a[href*='/handle/']")
            link = ""
            if link_el:
                href = link_el.get("href", "")
                link = f"https://www.indiacode.nic.in{href}" if not href.startswith("http") else href
            if title and len(title) > 5 and "View" not in title:
                items.append({"title": title, "description": f"Central Act ({year}): {title}", "link": link, "date": _parse_date_text(date_text)})
    return items


def scrape_egazette(config: dict) -> list[dict]:
    url = config.get("url", "https://egazette.gov.in/")
    resp = safe_get(url)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    items = []
    for row in soup.select("table tr, .gazette-item, .list-item, .notification-item"):
        cells = row.select("td")
        links = row.select("a")
        if cells and len(cells) >= 2:
            title = cells[0].get_text(strip=True) or (cells[1].get_text(strip=True) if len(cells) > 1 else "")
            link = ""
            for a in links:
                href = a.get("href", "")
                if href and (".pdf" in href or "view" in href.lower()):
                    link = href if href.startswith("http") else f"https://egazette.gov.in{href}"
                    break
            date_text = cells[-1].get_text(strip=True) if cells else ""
            if title and len(title) > 5:
                items.append({"title": title[:200], "description": f"Gazette notification: {title[:300]}", "link": link, "date": _parse_date_text(date_text)})
    return items


def scrape_niti_aayog(config: dict) -> list[dict]:
    items = []
    urls = config.get("urls", {})
    if not urls:
        urls = {"reports": config.get("url", "https://www.niti.gov.in/documents/reports")}
    for category, url in urls.items():
        resp = safe_get(url)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for row in soup.select(".views-row, .node-article, article, .publication-item, .view-content .item-list li"):
            title_el = row.select_one("h2 a, h3 a, .title a, .field-title a, a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = f"https://www.niti.gov.in{link}"
            date_el = row.select_one(".date, .field-date, time, .created, .datetime")
            date = _parse_date_text(date_el.get_text(strip=True) if date_el else "")
            desc_el = row.select_one(".summary, .field-body, .teaser, p")
            desc = desc_el.get_text(strip=True) if desc_el else f"NITI Aayog {category}: {title}"
            if title and len(title) > 5:
                items.append({"title": title, "description": desc[:500], "link": link, "date": date})
    return items


def scrape_parliament(config: dict) -> list[dict]:
    items = []
    urls = config.get("urls", {})
    if not urls:
        urls = {"bills": config.get("url", "")}
    for category, url in urls.items():
        if not url:
            continue
        resp = safe_get(url)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for row in soup.select("table tbody tr, .bill-item, .list-group-item, article"):
            cells = row.select("td")
            links = row.select("a")
            title, link, date = "", "", ""
            if cells and len(cells) >= 2:
                title = cells[1].get_text(strip=True) if len(cells) > 1 else cells[0].get_text(strip=True)
                for a in links:
                    href = a.get("href", "")
                    if href:
                        link = href if href.startswith("http") else f"https://sansad.in{href}"
                        if not title:
                            title = a.get_text(strip=True)
                        break
                for cell in cells:
                    text = cell.get_text(strip=True)
                    if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text):
                        date = _parse_date_text(text)
                        break
            else:
                title_el = row.select_one("a, h3, h4, .title")
                if title_el:
                    title = title_el.get_text(strip=True)
                    link = title_el.get("href", "")
                    if link and not link.startswith("http"):
                        link = f"https://sansad.in{link}"
            if title and len(title) > 3:
                items.append({"title": title, "description": f"Parliament {category}: {title}", "link": link, "date": date or ""})
    return items


def scrape_rbi(config: dict) -> list[dict]:
    url = config.get("scrape_url", "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx")
    resp = safe_get(url)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    items = []
    for row in soup.select("table tr, .tablebg tr, .tabledata tr"):
        cells = row.select("td")
        links = row.select("a")
        if len(cells) >= 2 and links:
            date_text = cells[0].get_text(strip=True)
            title_el = links[0]
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if href and not href.startswith("http"):
                href = f"https://www.rbi.org.in/Scripts/{href}"
            if title and len(title) > 5:
                items.append({"title": title[:200], "description": f"RBI: {title[:300]}", "link": href, "date": _parse_date_text(date_text)})
    return items


def scrape_data_gov_api(config: dict) -> list[dict]:
    base_url = config.get("base_url", "https://data.gov.in/backend/dmspublic/v1/resources")
    params = {"format": "json", "limit": "50"}
    api_headers = {**HEADERS, "Accept": "application/json"}
    try:
        resp = requests.get(base_url, params=params, headers=api_headers, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
        items = []
        rows = data.get("data", {}).get("rows", [])
        if not rows:
            rows = data if isinstance(data, list) else data.get("records", data.get("results", []))
        for record in rows[:50]:
            def get_field(r, key):
                val = r.get(key, "")
                return val[0] if isinstance(val, list) and val else val
            title = get_field(record, "catalog_title") or get_field(record, "title") or get_field(record, "name")
            ministry = get_field(record, "cdos_state_ministry")
            node_alias = get_field(record, "node_alias")
            published = get_field(record, "published_date")
            created = get_field(record, "created")
            link = f"https://data.gov.in{node_alias}" if node_alias else "https://data.gov.in"
            date = _parse_unix_timestamp(published or created) if (published or created) else ""
            desc = f"{ministry}: {title}" if ministry else f"Open Government Data: {title}"
            if title:
                items.append({"title": str(title)[:200], "description": desc[:500], "link": link, "date": date})
        return items
    except Exception:
        return []


def scrape_world_bank_api(config: dict) -> list[dict]:
    url = config.get("url", "https://search.worldbank.org/api/v3/wds?format=json&qterm=india&docty=Policy+Research+Working+Paper&rows=30")
    api_headers = {**HEADERS, "Accept": "application/json"}
    try:
        resp = requests.get(url, headers=api_headers, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
        items = []
        documents = data.get("documents", {})
        for doc_id, doc in documents.items():
            if doc_id == "facets":
                continue
            title = doc.get("display_title", doc.get("title", ""))
            abstract = doc.get("abstract", "")
            doc_url = doc.get("url", doc.get("pdfurl", ""))
            date = doc.get("docdt", doc.get("disclosure_date", ""))
            if title:
                items.append({"title": str(title)[:200], "description": str(abstract)[:500] if abstract else f"World Bank: {title}", "link": doc_url or "https://documents.worldbank.org", "date": _parse_date_text(str(date))})
        return items
    except Exception:
        return []


def scrape_ministry(config: dict) -> list[dict]:
    """Generic ministry/government website scraper."""
    url = config.get("url", "")
    if not url:
        return []
    resp = safe_get(url)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    items = []
    for row in soup.select(".views-row, article, .list-item, table tbody tr, .news-item, .card, .panel"):
        title_el = row.select_one("a, h2, h3, h4, .title")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        link = ""
        if title_el.name == "a":
            link = title_el.get("href", "")
        else:
            a = row.select_one("a")
            if a:
                link = a.get("href", "")
        if link and not link.startswith("http"):
            parsed = urlparse(url)
            link = f"{parsed.scheme}://{parsed.netloc}{link}"
        date_el = row.select_one(".date, time, .created, .field-date")
        date = _parse_date_text(date_el.get_text(strip=True) if date_el else "")
        desc_el = row.select_one(".summary, .teaser, p, .description")
        desc = desc_el.get_text(strip=True) if desc_el else ""
        if title and len(title) > 5:
            items.append({"title": title[:200], "description": desc[:500], "link": link, "date": date})
    return items


# ── Dispatcher ───────────────────────────────────────────────────────

_SPECIALIZED_SCRAPERS = {
    "pib": scrape_pib,
    "india_code": scrape_india_code,
    "egazette": scrape_egazette,
    "niti_aayog": scrape_niti_aayog,
    "parliament_lok_sabha": scrape_parliament,
    "parliament_rajya_sabha": scrape_parliament,
    "data_gov_in": scrape_data_gov_api,
    "rbi": scrape_rbi,
    "world_bank_india": scrape_world_bank_api,
}


def fetch_scrape(source_id: str, config: dict) -> list[dict]:
    """Route to the appropriate scraper for a source."""
    scraper = _SPECIALIZED_SCRAPERS.get(source_id, scrape_ministry)
    return scraper(config)
