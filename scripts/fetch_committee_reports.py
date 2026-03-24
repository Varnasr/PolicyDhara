#!/usr/bin/env python3
"""
Fetch parliamentary committee reports from sansad.in REST API.
Inspired by https://github.com/pranaykotas/parliamentwatch

Scrapes report metadata for all 16 Departmentally Related Standing Committees
(DRSCs) across Lok Sabha sessions and writes to data/committee_reports.json.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_JSON = DATA_DIR / "committee_reports.json"

REPORTS_API = "https://sansad.in/api_ls/committee/lsRSAllReports"
CURRENT_LOK_SABHA = int(os.environ.get("LOK_SABHA_NUMBER", "18"))

# All 16 Departmentally Related Standing Committees with sansad.in API codes
DRSC_COMMITTEES = {
    "agriculture": {
        "name": "Agriculture, Animal Husbandry and Food Processing",
        "api_code": 5,
        "sector": "Agriculture",
    },
    "chemicals": {
        "name": "Chemicals & Fertilizers",
        "api_code": 45,
        "sector": "Science & Innovation",
    },
    "coal": {
        "name": "Coal, Mines and Steel",
        "api_code": 46,
        "sector": "Energy",
    },
    "defence": {
        "name": "Defence",
        "api_code": 7,
        "sector": "Defence & Security",
    },
    "energy": {
        "name": "Energy",
        "api_code": 9,
        "sector": "Energy",
    },
    "external_affairs": {
        "name": "External Affairs",
        "api_code": 11,
        "sector": "Governance & Reform",
    },
    "finance": {
        "name": "Finance",
        "api_code": 12,
        "sector": "Finance & Economy",
    },
    "consumer_affairs": {
        "name": "Consumer Affairs, Food and Public Distribution",
        "api_code": 13,
        "sector": "Social Protection",
    },
    "communications": {
        "name": "Communications and Information Technology",
        "api_code": 18,
        "sector": "Digital & Technology",
    },
    "labour": {
        "name": "Labour, Textiles and Skill Development",
        "api_code": 19,
        "sector": "Labour & Employment",
    },
    "petroleum": {
        "name": "Petroleum & Natural Gas",
        "api_code": 23,
        "sector": "Energy",
    },
    "railways": {
        "name": "Railways",
        "api_code": 28,
        "sector": "Transport & Infrastructure",
    },
    "rural_development": {
        "name": "Rural Development and Panchayati Raj",
        "api_code": 32,
        "sector": "Rural Development",
    },
    "social_justice": {
        "name": "Social Justice & Empowerment",
        "api_code": 47,
        "sector": "Social Protection",
    },
    "housing": {
        "name": "Housing and Urban Affairs",
        "api_code": 41,
        "sector": "Housing",
    },
    "water_resources": {
        "name": "Water Resources",
        "api_code": 44,
        "sector": "Water & Sanitation",
    },
}


def sanitize_url(url):
    """Fix backslashes in URLs returned by sansad.in API."""
    if url:
        return url.replace("\\", "/")
    return url


def fetch_committee_reports(committee_key, lok_sabha=None, house="L"):
    """
    Fetch report listings for a single committee from the sansad.in API.

    Returns list of report dicts with standardized keys.
    """
    if lok_sabha is None:
        lok_sabha = CURRENT_LOK_SABHA

    committee = DRSC_COMMITTEES[committee_key]
    house_label = "LS" if house == "L" else "RS"
    print(f"  Fetching {committee['name']} ({house_label} {lok_sabha})...")

    params = {
        "house": house,
        "committeeCode": committee["api_code"],
        "lsNo": lok_sabha,
        "page": 1,
        "size": 200,
        "sortOn": "reportNo",
        "sortBy": "desc",
    }

    try:
        resp = requests.get(REPORTS_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  Error fetching {committee['name']}: {e}")
        return []

    records = data.get("records", [])
    total = data.get("_metadata", {}).get("totalElements", len(records))

    reports = []
    for record in records:
        report = {
            "committee_key": committee_key,
            "committee_name": record.get("CommitteeName", committee["name"]).strip(),
            "sector": committee["sector"],
            "report_number": record.get("reportNo"),
            "title": record.get("SubjectOfTheReport", ""),
            "presented_in_ls": record.get("PresentedInLS"),
            "laid_in_rs": record.get("LaidInRS"),
            "presented_to_speaker": record.get("PresentedToSpeaker"),
            "pdf_url": sanitize_url(record.get("url")),
            "pdf_url_hindi": sanitize_url(record.get("urlH")),
            "lok_sabha": record.get("Loksabha", lok_sabha),
            "house": house,
        }
        reports.append(report)

    print(f"  Found {len(reports)}/{total} reports for {committee['name']}")
    return reports


def scrape_all_committees(lok_sabha=None):
    """
    Fetch reports for all 16 DRSCs from sansad.in.

    Returns dict mapping committee_key -> list of reports.
    """
    if lok_sabha is None:
        lok_sabha = CURRENT_LOK_SABHA

    # Load existing data to merge
    existing = {}
    if REPORTS_JSON.exists():
        try:
            with open(REPORTS_JSON) as f:
                existing_data = json.load(f)
                existing = existing_data.get("committees", {})
        except (json.JSONDecodeError, KeyError):
            existing = {}

    all_reports = {}
    total_fetched = 0

    for key in DRSC_COMMITTEES:
        # Build index of existing reports for deduplication
        existing_by_id = {
            (r.get("report_number"), r.get("lok_sabha")): r
            for r in existing.get(key, [])
        }

        # Fetch from both houses
        for house in ["L", "R"]:
            reports = fetch_committee_reports(key, lok_sabha, house)
            for r in reports:
                rid = (r.get("report_number"), r.get("lok_sabha"))
                if rid not in existing_by_id:
                    existing_by_id[rid] = r
                else:
                    # Merge date info from both houses
                    ex = existing_by_id[rid]
                    if not ex.get("presented_in_ls") and r.get("presented_in_ls"):
                        ex["presented_in_ls"] = r["presented_in_ls"]
                    if not ex.get("laid_in_rs") and r.get("laid_in_rs"):
                        ex["laid_in_rs"] = r["laid_in_rs"]

            # Respect API rate limit
            time.sleep(0.5)

        sorted_reports = sorted(
            existing_by_id.values(),
            key=lambda x: (x.get("lok_sabha") or 0, x.get("report_number") or 0),
            reverse=True,
        )
        all_reports[key] = sorted_reports
        total_fetched += len(sorted_reports)

    return all_reports, total_fetched


def write_reports(committees, total):
    """Write committee reports to JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Compute summary stats
    committee_stats = []
    for key, reports in committees.items():
        info = DRSC_COMMITTEES.get(key, {})
        committee_stats.append({
            "key": key,
            "name": info.get("name", key),
            "sector": info.get("sector", ""),
            "report_count": len(reports),
        })

    output = {
        "metadata": {
            "description": "Parliamentary committee reports scraped from sansad.in",
            "source": "https://sansad.in",
            "attribution": "Inspired by https://github.com/pranaykotas/parliamentwatch",
            "last_updated": datetime.utcnow().strftime("%Y-%m-%d"),
            "total_reports": total,
            "total_committees": len(committees),
            "lok_sabha": CURRENT_LOK_SABHA,
        },
        "committee_summary": sorted(committee_stats, key=lambda x: x["report_count"], reverse=True),
        "committees": committees,
    }

    with open(REPORTS_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {total} reports across {len(committees)} committees to {REPORTS_JSON}")


def main():
    print("=" * 60)
    print("ParliamentWatch: Fetching committee reports from sansad.in")
    print("=" * 60)

    lok_sabha = CURRENT_LOK_SABHA
    if len(sys.argv) > 1:
        try:
            lok_sabha = int(sys.argv[1])
        except ValueError:
            pass

    committees, total = scrape_all_committees(lok_sabha)
    write_reports(committees, total)

    print(f"\nDone. {total} reports across {len(committees)} committees.")


if __name__ == "__main__":
    main()
