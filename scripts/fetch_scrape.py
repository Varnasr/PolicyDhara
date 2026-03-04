#!/usr/bin/env python3
"""
Web scraper for Indian policy sources that don't offer RSS/API.
Handles India Code, eGazette, NITI Aayog, Parliament, PIB, RBI,
data.gov.in API, and ministry websites.

Each source has a dedicated parser function due to different HTML structures.
Uses browser-like headers to avoid 403 blocks from .gov.in sites.
"""

import re
import json
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

# Browser-like headers — critical for .gov.in sites
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

TIMEOUT = 30


def safe_get(url: str, headers: dict = None) -> requests.Response | None:
    """Make a safe HTTP GET request with retries."""
    hdrs = headers or HEADERS
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=hdrs, timeout=TIMEOUT, verify=True, allow_redirects=True)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            print(f"  Attempt {attempt + 1} failed for {url}: {e}")
            if attempt == 2:
                return None
    return None


def parse_date_text(text: str) -> str:
    """Try to parse a date string into YYYY-MM-DD format."""
    if not text:
        return ""
    try:
        dt = dateparser.parse(text, fuzzy=True)
        if dt:
            return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass
    return ""


def parse_unix_timestamp(ts) -> str:
    """Convert Unix timestamp to YYYY-MM-DD."""
    try:
        val = int(ts) if not isinstance(ts, int) else ts
        dt = datetime.fromtimestamp(val, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        return ""


# ── Source-specific parsers ──────────────────────────────────────────


def scrape_pib(config: dict) -> list[dict]:
    """Scrape press releases from PIB English page."""
    url = config.get("url", "https://pib.gov.in/indexd.aspx?reg=3&lang=1")
    resp = safe_get(url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    items = []

    # Find press release links on the homepage
    for a in soup.select("a[href*='PressRele'], a[href*='PRID']"):
        title = a.get_text(strip=True)
        if not title or len(title) < 10:
            continue

        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = f"https://pib.gov.in{href}"

        # Extract PRID for dedup
        prid_match = re.search(r'PRID=(\d+)', href)
        prid = prid_match.group(1) if prid_match else ""

        items.append({
            "title": title[:200],
            "description": f"Government of India press release: {title[:300]}",
            "link": href,
            "date": "",
        })

    # Deduplicate by PRID
    seen = set()
    deduped = []
    for item in items:
        prid = re.search(r'PRID=(\d+)', item.get("link", ""))
        key = prid.group(1) if prid else item["title"]
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped


def scrape_india_code(config: dict) -> list[dict]:
    """Scrape recent Acts from India Code DSpace repository by browsing recent years."""
    items = []
    current_year = datetime.now(timezone.utc).year

    # Browse recent 2 years of acts
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
                items.append({
                    "title": title,
                    "description": f"Central Act ({year}): {title}",
                    "link": link,
                    "date": parse_date_text(date_text),
                })

    return items


def scrape_egazette(config: dict) -> list[dict]:
    """Scrape recent gazette notifications from egazette.gov.in."""
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
            date = parse_date_text(date_text)

            if title and len(title) > 5:
                items.append({
                    "title": title[:200],
                    "description": f"Gazette notification: {title[:300]}",
                    "link": link,
                    "date": date,
                })

    return items


def scrape_niti_aayog(config: dict) -> list[dict]:
    """Scrape publications from NITI Aayog."""
    items = []
    urls = config.get("urls", {})
    if not urls:
        urls = {"reports": config.get("url", "https://www.niti.gov.in/documents/reports")}

    for category, url in urls.items():
        resp = safe_get(url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        # NITI Aayog uses Drupal views-row divs
        for row in soup.select(".views-row, .node-article, article, .publication-item, .view-content .item-list li"):
            title_el = row.select_one("h2 a, h3 a, .title a, .field-title a, a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = f"https://www.niti.gov.in{link}"

            date_el = row.select_one(".date, .field-date, time, .created, .datetime")
            date = parse_date_text(date_el.get_text(strip=True) if date_el else "")

            desc_el = row.select_one(".summary, .field-body, .teaser, p")
            desc = desc_el.get_text(strip=True) if desc_el else f"NITI Aayog {category}: {title}"

            if title and len(title) > 5:
                items.append({
                    "title": title,
                    "description": desc[:500],
                    "link": link,
                    "date": date,
                })

    return items


def scrape_parliament(config: dict) -> list[dict]:
    """Scrape bills and data from Digital Sansad (sansad.in)."""
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

            title = ""
            link = ""
            date = ""

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
                        date = parse_date_text(text)
                        break
            else:
                title_el = row.select_one("a, h3, h4, .title")
                if title_el:
                    title = title_el.get_text(strip=True)
                    link = title_el.get("href", "")
                    if link and not link.startswith("http"):
                        link = f"https://sansad.in{link}"

            if title and len(title) > 3:
                items.append({
                    "title": title,
                    "description": f"Parliament {category}: {title}",
                    "link": link,
                    "date": date or "",
                })

    return items


def scrape_rbi(config: dict) -> list[dict]:
    """Scrape press releases from RBI website."""
    url = config.get("scrape_url", "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx")
    resp = safe_get(url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    items = []

    # RBI press releases page uses table format
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
                items.append({
                    "title": title[:200],
                    "description": f"RBI: {title[:300]}",
                    "link": href,
                    "date": parse_date_text(date_text),
                })

    return items


def scrape_data_gov_api(config: dict) -> list[dict]:
    """Fetch recent datasets from data.gov.in OGD 2.0 API."""
    base_url = config.get("base_url", "https://data.gov.in/backend/dmspublic/v1/resources")
    params = {
        "format": "json",
        "limit": "50",
    }

    api_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        resp = requests.get(base_url, params=params, headers=api_headers, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"  data.gov.in API returned {resp.status_code}")
            return []

        data = resp.json()
        items = []

        rows = data.get("data", {}).get("rows", [])
        if not rows:
            rows = data if isinstance(data, list) else data.get("records", data.get("results", []))

        for record in rows[:50]:
            # OGD 2.0 API wraps values in arrays
            def get_field(r, key):
                val = r.get(key, "")
                if isinstance(val, list):
                    return val[0] if val else ""
                return val

            title = get_field(record, "catalog_title") or get_field(record, "title") or get_field(record, "name")
            ministry = get_field(record, "cdos_state_ministry")
            node_alias = get_field(record, "node_alias")
            published = get_field(record, "published_date")
            created = get_field(record, "created")

            # Build link from node_alias
            link = f"https://data.gov.in{node_alias}" if node_alias else "https://data.gov.in"

            # Parse Unix timestamp
            date = parse_unix_timestamp(published or created) if (published or created) else ""

            desc = f"Open Government Data: {title}"
            if ministry:
                desc = f"{ministry}: {title}"

            if title:
                items.append({
                    "title": str(title)[:200],
                    "description": desc[:500],
                    "link": link,
                    "date": date,
                })

        return items
    except Exception as e:
        print(f"  data.gov.in API error: {e}")
        return []


def scrape_ministry(config: dict) -> list[dict]:
    """Generic ministry website scraper."""
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
        date = parse_date_text(date_el.get_text(strip=True) if date_el else "")

        desc_el = row.select_one(".summary, .teaser, p, .description")
        desc = desc_el.get_text(strip=True) if desc_el else ""

        if title and len(title) > 5:
            items.append({
                "title": title[:200],
                "description": desc[:500],
                "link": link,
                "date": date,
            })

    return items


def scrape_world_bank_api(config: dict) -> list[dict]:
    """Fetch India policy research papers from World Bank Documents API v3."""
    url = config.get("url", "https://search.worldbank.org/api/v3/wds?format=json&qterm=india&docty=Policy+Research+Working+Paper&rows=30")

    api_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    try:
        resp = requests.get(url, headers=api_headers, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"  World Bank API returned {resp.status_code}")
            return []

        data = resp.json()
        items = []

        # v3 API returns documents in a 'documents' dict keyed by ID
        documents = data.get("documents", {})
        for doc_id, doc in documents.items():
            if doc_id in ("facets",):
                continue

            title = doc.get("display_title", doc.get("title", ""))
            abstract = doc.get("abstract", "")
            doc_url = doc.get("url", doc.get("pdfurl", ""))
            date = doc.get("docdt", doc.get("disclosure_date", ""))

            if title:
                items.append({
                    "title": str(title)[:200],
                    "description": str(abstract)[:500] if abstract else f"World Bank: {title}",
                    "link": doc_url or "https://documents.worldbank.org",
                    "date": parse_date_text(str(date)),
                })

        return items
    except Exception as e:
        print(f"  World Bank API error: {e}")
        return []


def scrape_orf(config: dict) -> list[dict]:
    """Scrape research publications from ORF website."""
    url = config.get("url", "https://www.orfonline.org/expert-speak")
    resp = safe_get(url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    items = []
    seen = set()

    # ORF uses links with /expert-speak/ in the href for articles
    for a in soup.select("a[href*='expert-speak/']"):
        href = a.get("href", "")
        title = a.get_text(strip=True)

        # Skip category links and empty titles
        if "expert-speak-category" in href or not title or len(title) < 15:
            continue
        if href in seen:
            continue
        seen.add(href)

        if not href.startswith("http"):
            href = f"https://www.orfonline.org{href}"

        items.append({
            "title": title[:200],
            "description": f"ORF Expert Speak: {title[:300]}",
            "link": href,
            "date": "",
        })

    return items


# ── Dispatcher ───────────────────────────────────────────────────────

SOURCE_SCRAPERS = {
    "pib": scrape_pib,
    "india_code": scrape_india_code,
    "egazette": scrape_egazette,
    "niti_aayog": scrape_niti_aayog,
    "parliament_lok_sabha": scrape_parliament,
    "parliament_rajya_sabha": scrape_parliament,
    "prs_bills": scrape_ministry,
    "prs_legislative": scrape_ministry,
    "data_gov_in": scrape_data_gov_api,
    "mof_budget": scrape_ministry,
    "rbi": scrape_rbi,
    "moefcc": scrape_ministry,
    "meity": scrape_ministry,
    "orf": scrape_orf,
    "undp_india": scrape_ministry,
    "world_bank_india": scrape_world_bank_api,
    "idfc_institute": scrape_ministry,
    "nipfp": scrape_ministry,
    # State PIB regional offices — same HTML structure as central PIB
    "state_pib_maharashtra": scrape_pib,
    "state_pib_tamil_nadu": scrape_pib,
    "state_pib_karnataka": scrape_pib,
    "state_pib_west_bengal": scrape_pib,
    "state_pib_uttar_pradesh": scrape_pib,
    "state_pib_gujarat": scrape_pib,
    "state_pib_kerala": scrape_pib,
    "state_pib_madhya_pradesh": scrape_pib,
    "state_pib_rajasthan": scrape_pib,
    "state_pib_telangana": scrape_pib,
    "state_pib_punjab": scrape_pib,
    "state_pib_assam": scrape_pib,
    "state_pib_bihar": scrape_pib,
}


def fetch_scrape_source(source_id: str, config: dict) -> list[dict]:
    """Route to the appropriate scraper for a source."""
    scraper = SOURCE_SCRAPERS.get(source_id, scrape_ministry)
    return scraper(config)
