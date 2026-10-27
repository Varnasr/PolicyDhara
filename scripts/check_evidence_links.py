#!/usr/bin/env python3
"""Check that every source link in data/evidence.json still resolves.

A paper's address changes when a journal moves platforms or a working paper
is published. This runs weekly in its own workflow, off pull requests: it
talks to many third-party hosts, and a job cancelled by its timeout cancels
the whole run it belongs to.

Only 404 and 410 fail the run. A 401, 403 or 429 means the publisher blocks
robots, which says nothing about whether the page is gone, and a timeout is
reported and does not fail either.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (compatible; PolicyDharaLinkCheck/1.0; +https://policydhara.impactmojo.in)"
GONE = {404, 410}
BLOCKED = {401, 403, 405, 406, 429, 451, 999}


def probe(item):
    case, url = item
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25, stream=True, allow_redirects=True)
        code = r.status_code
        r.close()
    except requests.RequestException as e:
        return case, url, "error", type(e).__name__
    if code in GONE:
        return case, url, "broken", code
    if code in BLOCKED:
        return case, url, "blocked", code
    if code >= 400:
        return case, url, "error", code
    return case, url, "ok", code


def main():
    cases = json.loads((ROOT / "data" / "evidence.json").read_text(encoding="utf-8"))["cases"]
    items = sorted({(c["id"], s["url"]) for c in cases for s in c["sources"]})
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe, items))
    tally = {}
    for case, url, status, detail in results:
        tally[status] = tally.get(status, 0) + 1
        if status != "ok":
            print(f"{status.upper():8} {detail}  {case}  {url}")
    print(f"{len(results)} links: " + ", ".join(f"{v} {k}" for k, v in sorted(tally.items())))
    return 1 if tally.get("broken") else 0


if __name__ == "__main__":
    sys.exit(main())
