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

TIMEOUT = 10


def safe_get(url: str, headers: dict = None) -> requests.Response | None:
    """Make a safe HTTP GET request with retries (max 2 attempts)."""
    hdrs = headers or HEADERS
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=hdrs, timeout=TIMEOUT, verify=True, allow_redirects=True)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            print(f"  Attempt {attempt + 1} failed for {url}: {e}")
            if attempt == 1:
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


def discover_rss_url(soup: BeautifulSoup, base_url: str) -> str | None:
    """Look for RSS/Atom auto-discovery links in the HTML <head>.

    Returns the absolute RSS URL if found, None otherwise.
    """
    for link_tag in soup.select('link[rel="alternate"]'):
        link_type = (link_tag.get("type") or "").lower()
        if link_type in ("application/rss+xml", "application/atom+xml"):
            href = (link_tag.get("href") or "").strip()
            if href:
                if not href.startswith("http"):
                    parsed = urlparse(base_url)
                    if href.startswith("/"):
                        href = f"{parsed.scheme}://{parsed.netloc}{href}"
                    else:
                        href = f"{parsed.scheme}://{parsed.netloc}/{href}"
                return href
    return None


# CSS selectors covering a wide range of site structures
_MINISTRY_ROW_SELECTORS = ", ".join([
    # Drupal-based government sites
    ".views-row", "article", ".list-item", "table tbody tr",
    ".news-item", ".card", ".panel",
    # News sites
    ".story-card", ".article-list li", ".post-item", ".news-list li",
    ".story__card", ".article_content", ".entry",
    ".listing-page .story", "[data-story]", ".story-element",
    # Think tanks / research organisations
    ".publication-item", ".research-item", ".paper-item",
    ".blog-post", ".insight-item", ".report-item",
    # WordPress sites
    ".post", ".entry-title a", ".wp-block-post", ".hentry",
    # Government portals & scheme pages
    ".scheme-card", ".notification-item", ".press-release",
    ".circular-item", ".order-item",
    # Generic / fallback
    "main article", "section article", ".content-list li",
    ".results li", "#content .item",
])

# Title selectors tried in order; first match wins
_TITLE_SELECTORS = [
    "h1 a", "h2 a", "h3 a", "h4 a",
    ".title a", ".headline a",
    "a h2", "a h3",
]


def _extract_title_and_link(row, base_url: str) -> tuple[str, str]:
    """Extract the best (title, link) pair from a content row element."""
    parsed_base = urlparse(base_url)

    def _abs(href: str) -> str:
        if not href:
            return ""
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
        return f"{parsed_base.scheme}://{parsed_base.netloc}/{href}"

    # Try dedicated title selectors first
    for sel in _TITLE_SELECTORS:
        el = row.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text and len(text) > 3:
                # The element itself or its nearest <a> ancestor/descendant
                if el.name == "a":
                    return text, _abs(el.get("href", ""))
                parent_a = el.find_parent("a")
                if parent_a:
                    return text, _abs(parent_a.get("href", ""))
                child_a = el.select_one("a")
                if child_a:
                    return text, _abs(child_a.get("href", ""))
                return text, ""

    # Fallback: first significant <a> tag in the row
    for a in row.select("a"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        # Skip tiny / navigation-only anchors
        if text and len(text) > 5 and not href.startswith("#") and not href.startswith("javascript"):
            return text, _abs(href)

    # Last resort: any heading text
    for tag in ("h2", "h3", "h4", "h1", ".title", ".headline"):
        el = row.select_one(tag)
        if el:
            text = el.get_text(strip=True)
            if text and len(text) > 3:
                child_a = el.select_one("a") or row.select_one("a")
                link = _abs(child_a.get("href", "")) if child_a else ""
                return text, link

    return "", ""


def scrape_ministry(config: dict) -> list[dict]:
    """Generic ministry website scraper.

    Covers Drupal, WordPress, news sites, think-tank portals,
    government scheme pages, and generic HTML list layouts.
    """
    url = config.get("url", "")
    if not url:
        return []

    resp = safe_get(url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    items = []
    seen_links: set[str] = set()

    for row in soup.select(_MINISTRY_ROW_SELECTORS):
        title, link = _extract_title_and_link(row, url)
        if not title or len(title) <= 5:
            continue

        # Deduplicate by link
        if link and link in seen_links:
            continue
        if link:
            seen_links.add(link)

        # Date extraction — try several common selectors
        date = ""
        for date_sel in (".date", "time", ".created", ".field-date",
                         ".datetime", ".published-date", ".meta-date",
                         ".post-date", ".entry-date", "[datetime]",
                         ".timestamp", ".article-date"):
            date_el = row.select_one(date_sel)
            if date_el:
                date = parse_date_text(
                    date_el.get("datetime", "") or date_el.get_text(strip=True)
                )
                if date:
                    break

        # Description extraction
        desc = ""
        for desc_sel in (".summary", ".teaser", "p", ".description",
                         ".excerpt", ".abstract", ".field-body",
                         ".post-excerpt", ".entry-summary"):
            desc_el = row.select_one(desc_sel)
            if desc_el:
                desc = desc_el.get_text(strip=True)
                if desc:
                    break

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
    "pib_eci": scrape_pib,
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
    # Regulatory bodies
    "trai": scrape_ministry,
    "irdai": scrape_ministry,
    "cci": scrape_ministry,
    "cerc": scrape_ministry,
    "cpcb": scrape_ministry,
    "fssai": scrape_ministry,
    "dgft": scrape_ministry,
    "cbic": scrape_ministry,
    "cbdt": scrape_ministry,
    "dpiit": scrape_ministry,
    "ibbi": scrape_ministry,
    # Additional ministries
    "mohfw": scrape_ministry,
    "moe": scrape_ministry,
    "mord": scrape_ministry,
    "mohua": scrape_ministry,
    "mole": scrape_ministry,
    "mowr": scrape_ministry,
    "mnre": scrape_ministry,
    "mca": scrape_ministry,
    "mota": scrape_ministry,
    "mwcd": scrape_ministry,
    "msje": scrape_ministry,
    "doj": scrape_ministry,
    "mospi": scrape_ministry,
    "moagri": scrape_ministry,
    "dot": scrape_ministry,
    "morail": scrape_ministry,
    # Legal & judicial
    "sci_judgments": scrape_ministry,
    "law_commission": scrape_ministry,
    "csds_lokniti": scrape_ministry,
    # Sector-specific
    "nabard": scrape_ministry,
    "sidbi": scrape_ministry,
    "nha": scrape_ministry,
    "cii": scrape_ministry,
    "isro": scrape_ministry,
    "dst": scrape_ministry,
    "startup_india": scrape_ministry,
    "dge_employment": scrape_ministry,
    "nhb": scrape_ministry,
    "cag": scrape_ministry,
    "nfhs": scrape_ministry,
    "niti_sdg": scrape_ministry,
    "election_commission": scrape_ministry,
    "iim_bangalore": scrape_ministry,
    "cbga": scrape_ministry,
    "iwwage": scrape_ministry,
    "ncaer": scrape_ministry,
    "ilo_india": scrape_ministry,
    "fao_india": scrape_ministry,
    # Additional ministries & departments
    "moayush": scrape_ministry,
    "mocivil": scrape_ministry,
    "mocoal": scrape_ministry,
    "mocommerce": scrape_ministry,
    "moconsumer": scrape_ministry,
    "mocooperation": scrape_ministry,
    "moculture": scrape_ministry,
    "moearth": scrape_ministry,
    "mofa": scrape_ministry,
    "mofertilizer": scrape_ministry,
    "mofood": scrape_ministry,
    "mohousing": scrape_ministry,
    "moinfo": scrape_ministry,
    "momine": scrape_ministry,
    "momsme": scrape_ministry,
    "mopanchayat": scrape_ministry,
    "mopng": scrape_ministry,
    "mopower": scrape_ministry,
    "moroad": scrape_ministry,
    "moship": scrape_ministry,
    "mosteel": scrape_ministry,
    "motextile": scrape_ministry,
    "moyouth": scrape_ministry,
    "dea": scrape_ministry,
    "dfs": scrape_ministry,
    "doner": scrape_ministry,
    "dopt": scrape_ministry,
    "disinvestment": scrape_ministry,
    "atomic_energy": scrape_ministry,
    # Regulatory & statutory bodies
    "aicte": scrape_ministry,
    "bar_council": scrape_ministry,
    "cbse": scrape_ministry,
    "cert_in": scrape_ministry,
    "cic": scrape_ministry,
    "cvc": scrape_ministry,
    "dgca": scrape_ministry,
    "epfo": scrape_ministry,
    "esic": scrape_ministry,
    "lokpal": scrape_ministry,
    "naac": scrape_ministry,
    "nabh": scrape_ministry,
    "nclat": scrape_ministry,
    "nclt": scrape_ministry,
    "ncpcr": scrape_ministry,
    "ncsc": scrape_ministry,
    "ncst": scrape_ministry,
    "ncte": scrape_ministry,
    "ncw": scrape_ministry,
    "ncert": scrape_ministry,
    "ngt": scrape_ministry,
    "nhrc": scrape_ministry,
    "nic": scrape_ministry,
    "nmc": scrape_ministry,
    "npci": scrape_ministry,
    "pfrda": scrape_ministry,
    "rera": scrape_ministry,
    "sebi": scrape_ministry,
    "telecom_disputes": scrape_ministry,
    "ugc": scrape_ministry,
    "uidai": scrape_ministry,
    "itat": scrape_ministry,
    "ipc": scrape_ministry,
    # Research & policy institutions
    "accountability_india": scrape_ministry,
    "azim_premji": scrape_ministry,
    "brookings_india": scrape_ministry,
    "carnegie_india": scrape_ministry,
    "ceew": scrape_ministry,
    "centre_science_env": scrape_ministry,
    "chatham_house_india": scrape_ministry,
    "cppr": scrape_ministry,
    "cprindia": scrape_ministry,
    "cse_india": scrape_ministry,
    "csir": scrape_ministry,
    "csis_india": scrape_ministry,
    "cuts_international": scrape_ministry,
    "drdo": scrape_ministry,
    "gateway_house": scrape_ministry,
    "icar": scrape_ministry,
    "icmr": scrape_ministry,
    "icrier": scrape_ministry,
    "icssr": scrape_ministry,
    "idsa": scrape_ministry,
    "ifc_india": scrape_ministry,
    "igidr": scrape_ministry,
    "iihs": scrape_ministry,
    "india_foundation": scrape_ministry,
    "janaagraha": scrape_ministry,
    "jpal_south_asia": scrape_ministry,
    "nasscom": scrape_ministry,
    "nlsiu_blog": scrape_ministry,
    "observer_research": scrape_ministry,
    "oxfam_india": scrape_ministry,
    "praja": scrape_ministry,
    "ris": scrape_ministry,
    "south_asian_voices": scrape_ministry,
    "sprf": scrape_ministry,
    "takshashila": scrape_ministry,
    "teri": scrape_ministry,
    "vidhi_legal": scrape_ministry,
    "wipro_sustainability": scrape_ministry,
    # International organisations — India offices
    "adb_india": scrape_ministry,
    "imf_india": scrape_ministry,
    "oecd_india": scrape_ministry,
    "undesa": scrape_ministry,
    "unep_india": scrape_ministry,
    "unfpa_india": scrape_ministry,
    "unhcr_india": scrape_ministry,
    "unicef_india": scrape_ministry,
    "who_india": scrape_ministry,
    "wto_india": scrape_ministry,
    # Industry bodies
    "ficci": scrape_ministry,
    # Government schemes & portals
    "amrut": scrape_ministry,
    "ayushman_bharat": scrape_ministry,
    "cowin": scrape_ministry,
    "dbt_bharat": scrape_ministry,
    "digilocker": scrape_ministry,
    "digital_india": scrape_ministry,
    "e_shram": scrape_ministry,
    "gem_portal": scrape_ministry,
    "india_energy_dashboard": scrape_ministry,
    "jjm": scrape_ministry,
    "make_in_india": scrape_ministry,
    "mgnrega": scrape_ministry,
    "mudra_yojana": scrape_ministry,
    "national_horticulture": scrape_ministry,
    "national_scholarship": scrape_ministry,
    "one_nation_one_ration": scrape_ministry,
    "pmfby": scrape_ministry,
    "pmjdy": scrape_ministry,
    "pmkisan": scrape_ministry,
    "poshan_abhiyaan": scrape_ministry,
    "samagra_shiksha": scrape_ministry,
    "skill_india": scrape_ministry,
    "smart_cities": scrape_ministry,
    "soil_health": scrape_ministry,
    "stand_up_india": scrape_ministry,
    "swachh_bharat": scrape_ministry,
    "uday_portal": scrape_ministry,
    # Health data
    "cbhi": scrape_ministry,
    # Legal media & blogs
    "barandbench": scrape_ministry,
    "livelaw": scrape_ministry,
    "scobserver": scrape_ministry,
    # News & media outlets
    "al_jazeera_india": scrape_ministry,
    "ani_news": scrape_ministry,
    "article14": scrape_ministry,
    "asian_age": scrape_ministry,
    "bbc_india": scrape_ministry,
    "business_line": scrape_ministry,
    "business_standard": scrape_ministry,
    "caravanmag": scrape_ministry,
    "deccan_chronicle": scrape_ministry,
    "deccan_herald": scrape_ministry,
    "down_to_earth": scrape_ministry,
    "drishti_ias": scrape_ministry,
    "economic_times_infrastructure": scrape_ministry,
    "economic_times_policy": scrape_ministry,
    "epw": scrape_ministry,
    "et_energyworld": scrape_ministry,
    "et_government": scrape_ministry,
    "et_healthworld": scrape_ministry,
    "financial_express": scrape_ministry,
    "firstpost_india": scrape_ministry,
    "frontline_mag": scrape_ministry,
    "hindustan_times": scrape_ministry,
    "india_spend": scrape_ministry,
    "india_today": scrape_ministry,
    "indian_express_business": scrape_ministry,
    "indian_express_policy": scrape_ministry,
    "insights_ias": scrape_ministry,
    "livemint_policy": scrape_ministry,
    "mint_opinion": scrape_ministry,
    "moneycontrol": scrape_ministry,
    "ndtv_india": scrape_ministry,
    "news18_india": scrape_ministry,
    "newslaundry": scrape_ministry,
    "outlook_india": scrape_ministry,
    "print_diplomacy": scrape_ministry,
    "pti_news": scrape_ministry,
    "republic_world": scrape_ministry,
    "reuters_india": scrape_ministry,
    "scroll_in": scrape_ministry,
    "swarajya_mag": scrape_ministry,
    "telegraph_india": scrape_ministry,
    "the_hindu_business": scrape_ministry,
    "the_hindu_policy": scrape_ministry,
    "the_print": scrape_ministry,
    "the_quint": scrape_ministry,
    "the_wire": scrape_ministry,
    "tribune_india": scrape_ministry,
    "zee_news": scrape_ministry,
    # State government portals
    "mh_govt": scrape_ministry,
    "ka_govt": scrape_ministry,
    "tn_policy": scrape_ministry,
    "kl_policy": scrape_ministry,
    "dl_policy": scrape_ministry,
    "ap_govt": scrape_ministry,
    "arunachal_govt": scrape_ministry,
    "assam_govt": scrape_ministry,
    "bihar_govt": scrape_ministry,
    "chhattisgarh_govt": scrape_ministry,
    "goa_govt": scrape_ministry,
    "guj_govt": scrape_ministry,
    "haryana_govt": scrape_ministry,
    "hp_govt": scrape_ministry,
    "jharkhand_govt": scrape_ministry,
    "jk_govt": scrape_ministry,
    "ladakh_govt": scrape_ministry,
    "manipur_govt": scrape_ministry,
    "meghalaya_govt": scrape_ministry,
    "mizoram_govt": scrape_ministry,
    "mp_govt": scrape_ministry,
    "nagaland_govt": scrape_ministry,
    "odisha_govt": scrape_ministry,
    "punjab_govt": scrape_ministry,
    "raj_govt": scrape_ministry,
    "sikkim_govt": scrape_ministry,
    "tripura_govt": scrape_ministry,
    "ts_govt": scrape_ministry,
    "up_govt": scrape_ministry,
    "uttarakhand_govt": scrape_ministry,
    "wb_gazette": scrape_ministry,
}


def fetch_scrape_source(source_id: str, config: dict) -> list[dict]:
    """Route to the appropriate scraper for a source.

    If the scraper returns zero results, attempt RSS auto-discovery on the
    same page and parse the feed as a fallback.
    """
    # Any source whose id starts with `pib_` is a PIB ministry-filtered listing
    # and uses the same DOM/selectors as the firehose `pib` source — route to
    # scrape_pib by default so adding a new `pib_<ministry>` to feeds.json
    # doesn't need a corresponding entry in SOURCE_SCRAPERS.
    default = scrape_pib if source_id.startswith("pib_") else scrape_ministry
    scraper = SOURCE_SCRAPERS.get(source_id, default)
    results = scraper(config)

    if results:
        return results

    # ── RSS auto-discovery fallback ──────────────────────────────────
    url = config.get("url", "")
    if not url:
        return []

    resp = safe_get(url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    rss_url = discover_rss_url(soup, url)
    if not rss_url:
        return []

    print(f"  Discovered RSS feed for {source_id}: {rss_url}")
    rss_resp = safe_get(rss_url)
    if not rss_resp:
        return []

    try:
        from fetch_rss import parse_rss_xml
    except ImportError:
        from scripts.fetch_rss import parse_rss_xml

    return parse_rss_xml(rss_resp.content)
