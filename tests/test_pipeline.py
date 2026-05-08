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
