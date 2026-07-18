#!/usr/bin/env python3
"""Backfill historical central legislation from India Code (indiacode.nic.in).

The live pipeline only captures each source's recent window, so older
government eras (UPA I/II especially) look nearly empty — an artefact of
collection, not of policy volume. India Code's DSpace repository can be
browsed by enactment year, which gives an authoritative, dated list of every
Central Act. This script enumerates acts per year and merges them into
data/historical_policies.json (which the site loads via getAllPolicies), so
the era timeline reflects real legislation instead of a coverage gap.

Run:  python3 scripts/fetch_india_code_history.py [--from 2004] [--to 2014] [--dry-run]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_scrape import safe_get  # noqa: E402
from classifier import classify_policy, get_sector_slug  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

PROJECT_ROOT = Path(__file__).parent.parent
HIST_FILE = PROJECT_ROOT / "data" / "historical_policies.json"
BROWSE = ("https://www.indiacode.nic.in/handle/123456789/1362/browse"
          "?type=actyear&order=ASC&rpp=100&value={year}")
BASE = "https://www.indiacode.nic.in"

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
_DATE_RE = re.compile(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})")

# Titles that are not substantive public policy — private/local bills, pure
# appropriation/repeal housekeeping — get skipped to keep the archive useful.
_SKIP = re.compile(
    r"private lim|\bprivate\b|appropriation act|repealing and amending|"
    r"\bwakf\b.*private|personal|estate of",
    re.I,
)


def parse_date(text: str) -> str:
    m = _DATE_RE.search(text or "")
    if not m:
        return ""
    day, mon, year = int(m.group(1)), _MONTHS.get(m.group(2).title()), int(m.group(3))
    if not mon:
        return ""
    return f"{year:04d}-{mon:02d}-{day:02d}"


def fetch_year(year: int) -> list[dict]:
    """Return act dicts for a single enactment year."""
    resp = safe_get(BROWSE.format(year=year))
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    acts = []
    seen = set()
    for tr in soup.select("table tr"):
        cells = tr.select("td")
        if len(cells) < 3:
            continue
        date = parse_date(cells[0].get_text(" ", strip=True))
        # Title is the longest cell / the one with a handle link.
        link_el = tr.select_one("a[href*='handle/123456789']")
        title = ""
        for c in cells:
            t = c.get_text(" ", strip=True)
            if len(t) > len(title) and not _DATE_RE.search(t) and not t.isdigit():
                title = t
        if link_el and len(link_el.get_text(strip=True)) > len(title):
            title = link_el.get_text(strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        if not title or len(title) < 12 or _SKIP.search(title):
            continue
        if title.lower() in seen:
            continue
        seen.add(title.lower())
        href = link_el.get("href", "") if link_el else ""
        link = href if href.startswith("http") else f"{BASE}{href}"
        if not date:
            date = f"{year}-06-01"  # year known, exact day unavailable
        acts.append({"title": title, "date": date, "link": link})
    return acts


def to_item(act: dict) -> dict:
    title, date, link = act["title"], act["date"], act["link"]
    sectors = classify_policy(title, "")
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]
    return {
        "id": f"indiacode-{date[:4]}-{slug}",
        "title": title,
        "description": f"Central Act enacted {date}. Full text on India Code (indiacode.nic.in).",
        "link": link,
        "date": date,
        "source_id": "india_code_history",
        "source_name": "India Code (Historical)",
        "source_short": "India Code",
        "sectors": sectors,
        "sector_slugs": [get_sector_slug(s) for s in sectors],
        "type": "act",
        "kind": "instrument",
        "authority": "legal",
        "level": "central",
        "curated": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="y_from", type=int, default=2004)
    ap.add_argument("--to", dest="y_to", type=int, default=2014)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    existing = json.loads(HIST_FILE.read_text()) if HIST_FILE.exists() else []
    by_id = {p.get("id"): p for p in existing}
    have_titles = {p.get("title", "").strip().lower() for p in existing}

    added = 0
    for year in range(args.y_from, args.y_to + 1):
        acts = fetch_year(year)
        year_added = 0
        for act in acts:
            if act["title"].strip().lower() in have_titles:
                continue
            item = to_item(act)
            if item["id"] in by_id:
                continue
            by_id[item["id"]] = item
            have_titles.add(item["title"].strip().lower())
            year_added += 1
        added += year_added
        print(f"  {year}: {len(acts)} acts on India Code, +{year_added} new")

    merged = list(by_id.values())
    merged.sort(key=lambda p: p.get("date", ""), reverse=True)
    print(f"\nHistorical records: {len(existing)} -> {len(merged)} (+{added} from India Code)")

    if args.dry_run:
        print("(dry-run — not written)")
        return 0
    HIST_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {HIST_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
