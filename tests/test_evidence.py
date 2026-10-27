"""Fault injection for scripts/check_evidence.py.

Each test breaks one thing a reader could not see on the rendered page and
confirms the check refuses it. The last test runs the check on the real file.
"""

import copy
import importlib.util
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_evidence", ROOT / "scripts" / "check_evidence.py")
ce = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ce)

GOOD = {
    "id": "example-case",
    "title": "An example intervention",
    "area": "Education",
    "geography": {"level": "state", "states": ["Bihar"]},
    "period": "2010 to 2012",
    "intervention": "A state ran a programme in 100 schools.",
    "verdict": "worked",
    "verdict_basis": "Test scores rose by 0.2 standard deviations, which is significant.",
    "design": "rct",
    "design_detail": "Schools were assigned at random.",
    "sample": "100 schools",
    "effects": [
        {
            "outcome": "Test scores",
            "result": "0.2 standard deviations",
            "interval_or_se": "SE 0.05",
            "quote": "Scores rose by 0.2 standard deviations.",
            "page_or_section": "Table 2",
        }
    ],
    "caveats": ["Only one state was studied."],
    "sources": [
        {"citation": "A. Author (2015), Title, Journal 1(1)", "url": "https://example.org/p", "kind": "journal"}
    ],
    "verified_on": "2026-10-27",
}
TODAY = date(2026, 10, 28)


def errs(case):
    return ce.validate({"cases": [case]}, today=TODAY)


def mutate(fn):
    c = copy.deepcopy(GOOD)
    fn(c)
    return errs(c)


def test_good_case_passes():
    assert errs(GOOD) == []


def test_missing_source_fails():
    assert mutate(lambda c: c.update(sources=[]))


def test_http_source_fails():
    assert mutate(lambda c: c["sources"][0].update(url="http://example.org"))


def test_unknown_verdict_fails():
    assert mutate(lambda c: c.update(verdict="success"))


def test_quote_must_contain_the_figure():
    assert mutate(lambda c: c["effects"][0].update(result="0.9 standard deviations"))


def test_unverified_marker_fails():
    assert mutate(lambda c: c.update(sample="NOT VERIFIED"))


def test_em_dash_in_prose_fails():
    assert mutate(lambda c: c.update(intervention="A state ran a programme — in 100 schools."))


def test_banned_word_fails():
    assert mutate(lambda c: c["caveats"].append("The result is robust."))


def test_negative_parallel_fails():
    assert mutate(lambda c: c.update(verdict_basis="It was not only cheap but also fast."))


def test_banned_word_in_quote_is_allowed():
    c = copy.deepcopy(GOOD)
    c["effects"][0]["quote"] = "Robust scores rose by 0.2 standard deviations."
    assert errs(c) == []


def test_state_level_case_needs_states():
    assert mutate(lambda c: c["geography"].update(states=[]))


def test_future_verification_date_fails():
    assert mutate(lambda c: c.update(verified_on="2027-01-01"))


def test_duplicate_id_fails():
    assert ce.validate({"cases": [GOOD, GOOD]}, today=TODAY)


def test_real_file_passes():
    data = json.loads((ROOT / "data" / "evidence.json").read_text(encoding="utf-8"))
    assert ce.validate(data) == []
