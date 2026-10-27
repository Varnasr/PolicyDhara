"""The health probe separates 'returns items' from 'returns usable items'."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_source_health as h  # noqa: E402


def test_items_with_no_dates_are_undated_not_working():
    assert h.classify_bucket(200, 50000, 33, "", 0) == "UNDATED"


def test_dated_items_work_and_old_callers_are_unchanged():
    assert h.classify_bucket(200, 50000, 33, "", 5) == "WORKS"
    assert h.classify_bucket(200, 50000, 33) == "WORKS"


def test_a_usable_item_needs_a_date_and_a_real_title():
    assert h._is_dated({"date": "2026-10-01", "title": "Draft rules on electricity storage"})
    assert not h._is_dated({"date": "", "title": "Draft rules on electricity storage"})
    assert not h._is_dated({"date": "2026-10-01", "title": "Download"})
