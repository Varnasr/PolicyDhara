#!/usr/bin/env python3
"""
Best-effort fetcher for Lok Sabha starred/unstarred questions from the
sansad.in REST API (same api_ls base the committee-reports fetcher uses).

The answered-questions endpoint was reverse-engineered from the Digital
Sansad frontend bundle: GET https://sansad.in/api_ls/question/qetAllQuestions
("qet" is sansad's own spelling). Its exact query-parameter contract is not
documented and the API is unreachable from some networks, so this script:

  1. tries a series of known parameter variants until one returns JSON rows,
  2. logs which variant worked (so CI output tells us the real contract),
  3. writes data/questions.json on success,
  4. exits 0 with a note on failure — never breaks the pipeline.

Run: python3 scripts/fetch_sansad_questions.py [--probe]
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
QUESTIONS_JSON = DATA_DIR / "questions.json"

API_BASE = "https://sansad.in/api_ls/question"
CURRENT_LOK_SABHA = int(os.environ.get("LOK_SABHA_NUMBER", "18"))
TIMEOUT = 30
MAX_QUESTIONS = 500

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "PolicyDhara/1.0 (+https://github.com/Varnasr/PolicyDhara)",
    "Referer": "https://sansad.in/ls/questions/questions-and-answers",
}

# Parameter variants to try, in order. The frontend bundle shows the API is
# GET and unauthenticated; the param names below cover the conventions seen
# across sansad's other endpoints (committee: loksabha/house; misc: lkNo).
PARAM_VARIANTS = [
    {"loksabha": CURRENT_LOK_SABHA, "pageNo": 1, "pageSize": MAX_QUESTIONS, "locale": "en"},
    {"lokSabhaNo": CURRENT_LOK_SABHA, "pageNo": 1, "pageSize": MAX_QUESTIONS, "locale": "en"},
    {"lkNo": CURRENT_LOK_SABHA, "locale": "en", "page": 1, "size": MAX_QUESTIONS},
    {"loksabhaNo": CURRENT_LOK_SABHA, "sessionNumber": "", "pageNo": 1, "pageSize": MAX_QUESTIONS, "locale": "en"},
    {"loksabha": CURRENT_LOK_SABHA, "sessionNo": "", "qType": "", "pageNo": 1, "pageSize": MAX_QUESTIONS, "locale": "en"},
]

ENDPOINTS = [
    f"{API_BASE}/qetAllQuestions",
    f"{API_BASE}/member/qetFilteredQuestionsAns",
]


def _rows_from(payload):
    """Extract a list of question rows from whatever envelope the API uses."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "records", "questions", "content", "result", "rows"):
            v = payload.get(key)
            if isinstance(v, list) and v:
                return v
            if isinstance(v, dict):
                inner = _rows_from(v)
                if inner:
                    return inner
    return []


def fetch_questions(probe=False):
    """Try endpoint × param variants until one yields rows."""
    for url in ENDPOINTS:
        for params in PARAM_VARIANTS:
            try:
                resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
                note = f"{url} {params} -> HTTP {resp.status_code}"
                if resp.status_code != 200:
                    if probe:
                        print(f"  probe: {note}")
                    continue
                payload = resp.json()
                rows = _rows_from(payload)
                if rows:
                    print(f"  WORKING VARIANT: {note} ({len(rows)} rows)")
                    return rows
                if probe:
                    print(f"  probe: {note} (200 but no rows)")
            except Exception as e:  # noqa: BLE001 — best-effort by design
                if probe:
                    print(f"  probe: {url} {params} -> {type(e).__name__}: {e}")
    return []


def normalize(rows):
    """Map API rows to the tracker's question schema (defensively — field
    names come from an undocumented API)."""
    out = []
    for r in rows[:MAX_QUESTIONS]:
        if not isinstance(r, dict):
            continue
        title = (r.get("subject") or r.get("questionSubject")
                 or r.get("title") or "").strip()
        if not title:
            continue
        qtype = (r.get("questionType") or r.get("type") or "")
        if isinstance(qtype, list):
            qtype = qtype[0] if qtype else ""
        out.append({
            "question_no": str(r.get("questionNo") or r.get("qno") or ""),
            "title": title,
            "type": str(qtype).upper(),          # STARRED / UNSTARRED
            "ministry": r.get("ministry") or r.get("ministryName") or "",
            "member": r.get("member") or r.get("memberName") or "",
            "date": r.get("date") or r.get("answerDate") or "",
            "session": r.get("lokSabhaSession") or r.get("sessionNo") or "",
            "pdf_url": (r.get("questionPdfUrl") or r.get("pdfUrl") or "") or "",
        })
    return out


def main() -> int:
    probe = "--probe" in sys.argv
    print("Sansad Q&A: fetching starred/unstarred questions...")
    rows = fetch_questions(probe=probe)
    if not rows:
        print("  Sansad questions API unreachable or contract changed — skipping "
              "(site falls back to PIB-detected question replies).")
        return 0

    questions = normalize(rows)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(QUESTIONS_JSON, "w") as f:
        json.dump({
            "metadata": {
                "source": "https://sansad.in",
                "lok_sabha": CURRENT_LOK_SABHA,
                "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "total": len(questions),
            },
            "questions": questions,
        }, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {len(questions)} questions to {QUESTIONS_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
