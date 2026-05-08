"""Tests for the CI delivery pipeline: snapshot diff, priority filter, message formatting.

The CI workflow takes one pre-fetch snapshot, fetches new data, then runs three
consumers (digest, sector alerts, Telegram) that diff against that snapshot. A
regression where any consumer overwrites the snapshot mid-pipeline silently
breaks every downstream consumer, so the round-trip is locked in here.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    """Load both pipeline scripts pointed at a temp data dir."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    snapshot = data_dir / ".policy_ids_snapshot.json"
    policies = data_dir / "policies.json"

    newsletter = _load_module("send_newsletter")
    telegram = _load_module("push_telegram")

    for mod in (newsletter, telegram):
        monkeypatch.setattr(mod, "DATA_DIR", data_dir)
        monkeypatch.setattr(mod, "SNAPSHOT_FILE", snapshot)
        monkeypatch.setattr(mod, "POLICIES_FILE", policies)

    return {
        "newsletter": newsletter,
        "telegram": telegram,
        "snapshot": snapshot,
        "policies": policies,
    }


def _write_policies(path: Path, policies: list[dict]):
    path.write_text(json.dumps(policies))


# ── Snapshot diff ────────────────────────────────────────────────────


class TestSnapshotDiff:
    def test_new_policies_detected_after_snapshot(self, pipeline):
        _write_policies(pipeline["policies"], [{"id": "a"}, {"id": "b"}])
        pipeline["newsletter"].save_snapshot()

        _write_policies(
            pipeline["policies"],
            [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}],
        )
        new = pipeline["telegram"].find_new_policies()
        assert {p["id"] for p in new} == {"c", "d"}

    def test_missing_snapshot_returns_empty(self, pipeline):
        _write_policies(pipeline["policies"], [{"id": "a"}])
        assert pipeline["telegram"].find_new_policies() == []
        assert pipeline["newsletter"].find_new_policies() == []

    def test_newsletter_main_does_not_overwrite_snapshot(self, pipeline, monkeypatch):
        """Regression: send_newsletter.main() must not save the snapshot.

        If it does, the sector-alerts and Telegram steps that run after it
        will see zero new policies because the snapshot now matches the
        post-fetch state.
        """
        _write_policies(pipeline["policies"], [{"id": "a"}])
        pipeline["newsletter"].save_snapshot()
        snapshot_before = pipeline["snapshot"].read_bytes()

        _write_policies(pipeline["policies"], [{"id": "a"}, {"id": "b"}])
        monkeypatch.setattr(sys, "argv", ["send_newsletter.py"])
        monkeypatch.setattr(
            pipeline["newsletter"], "send_via_buttondown", lambda *a, **kw: None
        )
        pipeline["newsletter"].main()

        assert pipeline["snapshot"].read_bytes() == snapshot_before, (
            "send_newsletter.main() rewrote the pre-fetch snapshot — "
            "downstream consumers will see no new policies"
        )

    def test_snapshot_only_writes_then_exits(self, pipeline, monkeypatch):
        _write_policies(pipeline["policies"], [{"id": "a"}, {"id": "b"}])
        monkeypatch.setattr(sys, "argv", ["send_newsletter.py", "--snapshot-only"])
        pipeline["newsletter"].main()
        assert json.loads(pipeline["snapshot"].read_text()) == ["a", "b"]


# ── Telegram priority filter ─────────────────────────────────────────


class TestPriorityFilter:
    @pytest.mark.parametrize(
        "policy",
        [
            {"title": "Constitutional Amendment Bill", "type": "legislation"},
            {"title": "Union Budget 2026", "type": "budget"},
            {"title": "Some Act", "type": "legislation"},
            {"title": "Some Bill", "type": "legislation"},
            {
                "title": "Scheme launch",
                "description": "Pan-India rollout",
                "type": "scheme",
            },
            {"title": "Gazette Notification", "type": "notification"},
            {
                "title": "Multi-sector scheme",
                "type": "scheme",
                "sectors": ["Health", "Education"],
            },
        ],
    )
    def test_high_priority_matches(self, pipeline, policy):
        assert pipeline["telegram"].is_high_priority(policy)

    @pytest.mark.parametrize(
        "policy",
        [
            {"title": "Press release", "type": "announcement"},
            {"title": "Minor scheme", "type": "scheme", "sectors": ["Health"]},
            {"title": "Research note", "type": "research"},
        ],
    )
    def test_low_priority_skipped(self, pipeline, policy):
        assert not pipeline["telegram"].is_high_priority(policy)


# ── Telegram message formatting ──────────────────────────────────────


class TestFirstSeenStamping:
    """merge_policies must stamp first_seen on every record. Without it,
    the homepage 'Added This Week' widget and sector-momentum analytics
    fall back to p.date (issuance date) and silently misreport ingestion
    cadence — a bug that re-regressed once already.
    """

    @pytest.fixture
    def fetch_all(self, tmp_path, monkeypatch):
        mod = _load_module("fetch_all")
        # Redirect file-writing helpers away from the repo
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        monkeypatch.setattr(mod, "AMENDMENTS_FILE", tmp_path / "amendments.json")
        monkeypatch.setattr(mod, "load_amendments", lambda: {})
        monkeypatch.setattr(mod, "save_amendments", lambda *_: None)
        monkeypatch.setattr(mod, "detect_amendments", lambda existing, new, amendments: amendments)
        return mod

    def test_new_item_gets_first_seen(self, fetch_all):
        existing: dict = {}
        new_items = [{"id": "x", "title": "T", "source_id": "s", "date": "2026-05-01"}]
        fetch_all.merge_policies(existing, new_items)
        assert existing["x"].get("first_seen"), "first_seen must be set on new items"

    def test_existing_first_seen_preserved(self, fetch_all):
        existing = {
            "x": {
                "id": "x",
                "title": "T",
                "source_id": "s",
                "first_seen": "2024-01-15",
            }
        }
        new_items = [{"id": "x", "title": "T", "source_id": "s", "date": "2026-05-01"}]
        fetch_all.merge_policies(existing, new_items)
        assert existing["x"]["first_seen"] == "2024-01-15"

    def test_legacy_record_backfilled(self, fetch_all):
        """Records already in `existing` but absent from this fetch cycle
        must still get first_seen — they're the 2000 legacy items the
        previous fix forgot about."""
        existing = {
            "legacy": {"id": "legacy", "title": "Old", "source_id": "s"}
        }
        fetch_all.merge_policies(existing, new_items=[])
        assert existing["legacy"].get("first_seen"), (
            "legacy records missing first_seen must be backfilled, otherwise "
            "the 'Added This Week' widget reverts to issuance-date fallback"
        )


class TestNoTodayFallback:
    """fetch_source must NOT stamp today's date on items where the source
    didn't expose a publication date. Doing so contaminates `p.date` with
    fake "issued today" timestamps, which is what made the homepage
    "enacted this week" widget report ingestion cadence for years.
    """

    @pytest.fixture
    def fetch_all(self, tmp_path, monkeypatch):
        mod = _load_module("fetch_all")
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        monkeypatch.setattr(mod, "AMENDMENTS_FILE", tmp_path / "amendments.json")
        return mod

    def test_undated_source_item_keeps_empty_date(self, fetch_all, monkeypatch):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Stub the dispatch layer so fetch_source returns one undated item
        monkeypatch.setattr(
            fetch_all,
            "fetch_scrape_source",
            lambda sid, cfg: [{
                "title": "A long enough policy title to pass validation",
                "description": "desc",
                "link": "https://example.gov.in/x",
                "date": "",
            }],
        )
        monkeypatch.setattr(fetch_all, "extract_date_from_title", lambda t: "")
        monkeypatch.setattr(fetch_all, "is_valid_title", lambda t: True)
        monkeypatch.setattr(fetch_all, "classify_policy", lambda *a, **k: ["governance"])

        items = fetch_all.fetch_source("test", {"type": "scrape", "name": "Test", "short_name": "T"})
        assert items, "fetcher returned nothing"
        assert items[0]["date"] == "", (
            f"date must stay empty when source provides none — got {items[0]['date']!r}. "
            f"If this is today ({today}), the today-fallback regressed and "
            f"'enacted this week' will silently report ingestion cadence."
        )


class TestSourcesWired:
    """Lock the wiring for PIB ministry-filtered sources. Each source must
    point at a unique MinId on the PIB Allrel.aspx listing, and the scraper
    must route through scrape_pib (not the scrape_ministry default — the
    selectors differ).
    """

    @pytest.fixture(scope="class")
    def feeds(self):
        feeds_path = Path(__file__).resolve().parent.parent / "feeds.json"
        return json.loads(feeds_path.read_text())

    @pytest.fixture(scope="class")
    def fetch_scrape(self):
        from importlib.util import spec_from_file_location, module_from_spec

        spec = spec_from_file_location("fetch_scrape", SCRIPTS_DIR / "fetch_scrape.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_pib_eci_source_defined(self, feeds):
        src = feeds["sources"].get("pib_eci")
        assert src is not None
        assert "MinId=35" in src["url"]

    def test_pib_ministry_sources_have_unique_minids(self, feeds):
        import re

        seen_minids: dict[str, str] = {}
        for key, src in feeds["sources"].items():
            url = src.get("url", "")
            # Only check ministry-filtered listings
            if "Allrel.aspx" not in url:
                continue
            match = re.search(r"MinId=(\d+)", url)
            assert match, f"{key} on Allrel.aspx but missing MinId: {url}"
            minid = match.group(1)
            assert minid not in seen_minids, (
                f"MinId={minid} collision: {key} and {seen_minids[minid]} "
                f"would fetch the same content"
            )
            seen_minids[minid] = key

    def test_pib_prefixed_sources_route_to_scrape_pib(self, feeds, fetch_scrape):
        """Any pib_* source either has an explicit SOURCE_SCRAPERS entry
        or falls through to the pib_-prefix default — both must end up at
        scrape_pib, never scrape_ministry."""

        def resolve_scraper(source_id: str):
            if source_id in fetch_scrape.SOURCE_SCRAPERS:
                return fetch_scrape.SOURCE_SCRAPERS[source_id]
            if source_id.startswith("pib_"):
                return fetch_scrape.scrape_pib
            return fetch_scrape.scrape_ministry

        for key in feeds["sources"]:
            if not key.startswith("pib_"):
                continue
            assert resolve_scraper(key) is fetch_scrape.scrape_pib, (
                f"{key} resolves to scrape_ministry — PRID-based links won't be picked up"
            )


class TestMessageFormatting:
    def test_html_escapes_special_chars(self, pipeline):
        msg = pipeline["telegram"].format_message(
            {
                "id": "x",
                "title": "Tax & Tariff <Update>",
                "description": "Affects A & B",
                "type": "notification",
                "date": "2026-05-08",
            }
        )
        assert "Tax &amp; Tariff &lt;Update&gt;" in msg
        assert "Affects A &amp; B" in msg

    def test_long_description_truncated(self, pipeline):
        msg = pipeline["telegram"].format_message(
            {
                "id": "x",
                "title": "Title",
                "description": "x" * 500,
                "type": "policy",
                "date": "2026-05-08",
            }
        )
        body_xs = msg.count("x")
        assert body_xs <= 280
        assert "…" in msg

    def test_links_use_source_when_present(self, pipeline):
        msg = pipeline["telegram"].format_message(
            {
                "id": "abc",
                "title": "T",
                "type": "policy",
                "date": "2026-05-08",
                "link": "https://example.gov.in/notice",
            }
        )
        assert 'href="https://example.gov.in/notice"' in msg
        assert "/policies/abc/" in msg
