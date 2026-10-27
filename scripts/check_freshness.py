#!/usr/bin/env python3
"""Report which parts of the site have gone stale.

The policy feed refreshes itself every six hours. Several datasets do not:
they are curated by hand (Parliament sessions, Budget figures, impact notes,
state governments) or probed weekly (source health). A stale figure renders
as confidently as a fresh one, so this script names the age of each and the
age at which it should be looked at again.

Usage:
  python3 scripts/check_freshness.py              # print a table
  python3 scripts/check_freshness.py --markdown   # print an issue body
  python3 scripts/check_freshness.py --strict     # exit 1 when anything is stale
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _day(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def indian_fy_start(today):
    """Start year of the Indian financial year (April to March) that contains today."""
    return today.year if today.month >= 4 else today.year - 1


def checks(today):
    rows = []

    def add(name, as_of, max_days, why):
        age = (today - as_of).days if as_of else None
        rows.append({
            "name": name,
            "as_of": as_of.isoformat() if as_of else "unknown",
            "age_days": age,
            "max_days": max_days,
            "stale": age is None or age > max_days,
            "why": why,
        })

    add("Policy feed (data/meta.json)", _day(_load("meta.json")["last_updated"]), 2,
        "refreshes every six hours; older than two days means the update workflow is failing")

    health = _load("source_health.json")
    probed = max((_day(v["last_probed"]) for v in health.values() if v.get("last_probed")), default=None)
    add("Source health probe", probed, 10,
        "probed weekly; its results page tells readers which sources work")

    add("Committee reports", _day(_load("committee_reports.json")["metadata"]["last_updated"]), 14,
        "scraped from sansad.in")

    ps = _load("parliament_sessions.json")
    add("Parliament sessions (last_updated)", _day(ps["metadata"]["last_updated"]), 120,
        "curated by hand; each new session needs its dates, sittings and productivity added")
    newest_end = max(_day(s["end"]) for s in ps["sessions"] if s.get("end"))
    add("Parliament sessions (newest session end)", newest_end, 150,
        "Parliament normally sits three times a year, so a gap of five months means a session is missing")

    bud = _load("budget_allocations.json")
    latest_fy = max(int(r["year"][:4]) for r in bud["fiscal_summary"])
    expected = indian_fy_start(today)
    rows.append({
        "name": "Union Budget (latest year held)",
        "as_of": f"{latest_fy}-{str(latest_fy + 1)[2:]}",
        "age_days": None,
        "max_days": None,
        "stale": latest_fy < expected,
        "why": f"the Budget for {expected}-{str(expected + 1)[2:]} is presented in February of that year",
    })

    for fname, label in [("policy_impacts.json", "Policy impact notes"),
                         ("state_governments.json", "State governments")]:
        add(label, _day(_load(fname)["metadata"]["last_updated"]), 365,
            "curated by hand; ruling parties and programme status change after elections")

    ev = _load("evidence.json")["cases"]
    oldest = min(_day(c["verified_on"]) for c in ev)
    add(f"Evidence cases ({len(ev)}, oldest check)", oldest, 365,
        "figures were matched to their sources on this date; recheck for corrections and retractions")
    return rows


def main(argv):
    rows = checks(date.today())
    stale = [r for r in rows if r["stale"]]
    if "--markdown" in argv:
        print(f"Checked on {date.today().isoformat()}. {len(stale)} of {len(rows)} items are past their limit.\n")
        print("| Item | As of | Age (days) | Limit (days) | Status | Why it matters |")
        print("|---|---|---|---|---|---|")
        for r in rows:
            age = "" if r["age_days"] is None else r["age_days"]
            lim = "" if r["max_days"] is None else r["max_days"]
            print(f"| {r['name']} | {r['as_of']} | {age} | {lim} | {'STALE' if r['stale'] else 'ok'} | {r['why']} |")
    else:
        for r in rows:
            age = "n/a" if r["age_days"] is None else f"{r['age_days']}d"
            print(f"{'STALE' if r['stale'] else 'ok   '}  {r['name']:<48} as of {r['as_of']:<11} age {age}")
        print(f"{len(stale)} stale of {len(rows)}")
    return 1 if (stale and "--strict" in argv) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
