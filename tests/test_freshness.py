"""The freshness check must notice what it exists to notice."""

import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_freshness", ROOT / "scripts" / "check_freshness.py")
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)


def by_name(rows, fragment):
    return next(r for r in rows if fragment in r["name"])


def test_financial_year_starts_in_april():
    assert cf.indian_fy_start(date(2026, 3, 31)) == 2025
    assert cf.indian_fy_start(date(2026, 4, 1)) == 2026
    assert cf.indian_fy_start(date(2026, 10, 27)) == 2026


def test_far_future_marks_every_dated_item_stale():
    rows = cf.checks(date(2030, 1, 1))
    assert by_name(rows, "Policy feed")["stale"]
    assert by_name(rows, "Source health")["stale"]
    assert by_name(rows, "Parliament sessions (last_updated)")["stale"]
    assert by_name(rows, "Evidence cases")["stale"]


def test_budget_year_goes_stale_when_a_new_financial_year_starts(monkeypatch):
    real = cf._load

    def with_budget_2026_27(name):
        if name == "budget_allocations.json":
            return {"fiscal_summary": [{"year": "2025-26"}, {"year": "2026-27"}]}
        return real(name)

    monkeypatch.setattr(cf, "_load", with_budget_2026_27)
    # The Budget held is 2026-27; by April 2027 the 2027-28 Budget should be in.
    assert not by_name(cf.checks(date(2027, 3, 31)), "Union Budget")["stale"]
    assert by_name(cf.checks(date(2027, 4, 1)), "Union Budget")["stale"]


def test_fresh_policy_feed_is_not_flagged():
    meta = cf._load("meta.json")["last_updated"]
    rows = cf.checks(cf._day(meta))
    assert not by_name(rows, "Policy feed")["stale"]
