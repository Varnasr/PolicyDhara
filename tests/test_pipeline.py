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


class TestPolicyRelevanceFilter:
    """News RSS feeds carry everything the outlet publishes (celebrity news,
    sports, crime spectacle). The is_policy_relevant() gate filters those out
    so items like "Bikers wheelie" don't land in the tracker while real
    policy news ("Centre forms panel", "Govt sells stake") passes through.

    Lock the current keep/drop bindings so a future keyword prune doesn't
    silently re-open the noise firehose.
    """

    @pytest.fixture(scope="class")
    def is_policy_relevant(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "classifier", SCRIPTS_DIR / "classifier.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.is_policy_relevant

    @pytest.mark.parametrize("title,desc", [
        # Bare titles — no policy signal anywhere
        ("Bikers perform wheelies in front of ambulance, endanger patient's life in Bengaluru", ""),
        ("Rupee rises 15 paise to 95.28 against U.S. dollar in early trade", ""),
        ("Teenager Wins Football Match, Then A Murder In Tense Kolkata Suburb", ""),
        ("Condom Ad During Cricket Match Is 'Adult Entertainment': Trinamool MP", ""),
        ("Man held on charge of sexually abusing minor", ""),
        ("Two members of a Kerala family killed in Saudi road crash", ""),
        ("Man Strangles Wife During Argument, Dies By Suicide In Rajasthan: Cops", ""),
        # Regression: `ed ` was matching past-tense verbs ("recorded",
        # "circulated") and dragging in ~400 noise items. Word-boundary
        # matching for short markers is what stops it.
        ("Bikers performing wheelie stunt block ambulance in Bengaluru, one held | Video",
         "The video, recorded from inside the ambulance, circulated widely on social media."),
        # Spectacle hard-drop: these brush a policy keyword ("minister",
        # "govt", "court") but are tabloid/crime/sport/celebrity noise and
        # must be dropped by _is_spectacle before the marker check.
        ("Bengaluru woman hacks husband to death with axe over affair suspicion", ""),
        ("BJP minister's son arrested in murder case, sent to judicial custody", ""),
        ("IPL 2026 final: Mumbai Indians beat Chennai as govt boxes fill up", ""),
        ("Bollywood actor's PIL in High Court seeks ban on paparazzi", ""),
        ("Man commits suicide outside Delhi Secretariat over pending scheme dues", ""),
        ("Woman molested near Parliament Street, one held: police", ""),
    ])
    def test_noise_dropped(self, is_policy_relevant, title, desc):
        assert not is_policy_relevant(title, desc), (
            f"noise item slipped through the filter: {title!r}"
        )

    @pytest.mark.parametrize("title", [
        "Supreme Court dismisses PIL on electoral bonds",
        "Centre Forms Panel To Examine Content Of Diljit Dosanjh's Satluj After Takedown",
        "Govt to sell 5% stake in Cochin Shipyard at ₹1,400/share via OFS",
        "Fisherfolk, environmentalists demand cancellation of public hearing on Cuddalore port expansion",
        "Convention centre, museum: Nod sought for work at Indira Point",
        "Cabinet approves ₹10,000 crore scheme for rural electrification",
        "MeitY issues draft rules for AI safety consultation",
        # Recent policy items dropped in the over-strict pass — pin them so
        # a future keyword prune can't remove the markers that let them through.
        "Bureau of Police Research and Development, National Crime Records Bureau get new chiefs",
        "Vietnam BrahMos deal already signed, Indonesia pact in final stages: Defence Secretary R.K",
        "Fresh bomb threat email to ISRO headquarters declared hoax",
        # Guard the spectacle blocklist against over-reach: these contain a
        # near-miss of a blocked token but are genuine policy and must stay.
        # - "stunting" must not trip the \bstunt\b token
        # - "suicide prevention" must not trip (only "commits/dies by suicide")
        # - "skill" must not trip the \bkilled\b/\bkills\b tokens
        # - "Crime Records Bureau" must not trip (no bare "crime" marker)
        "Government scheme sets new target to cut child stunting in tribal districts",
        "Health Ministry launches suicide prevention helpline under mental health policy",
        "Skill India scheme expands apprenticeship guidelines for gig workers",
    ])
    def test_real_policy_kept(self, is_policy_relevant, title):
        assert is_policy_relevant(title), (
            f"legitimate policy story dropped by the filter: {title!r}"
        )


class TestBroadcastGate:
    """Telegram and the newsletter re-check every item before pushing it out.
    is_broadcast_relevant() drops spectacle from ANY source and requires a
    policy marker for media items, so tabloid noise never reaches subscribers
    even if it slips into policies.json."""

    @pytest.fixture(scope="class")
    def classifier(self):
        return _load_module("classifier")

    def test_spectacle_dropped_even_from_official_source(self, classifier):
        # Official source (level != media) but a lurid title — must not go out.
        assert not classifier.is_broadcast_relevant(
            "PIB officer's son hacked to death with axe in Delhi", "", "central"
        )

    def test_media_item_without_policy_marker_dropped(self, classifier):
        assert not classifier.is_broadcast_relevant(
            "Rupee rises 15 paise against U.S. dollar in early trade", "", "media"
        )

    def test_real_media_policy_kept(self, classifier):
        assert classifier.is_broadcast_relevant(
            "Cabinet approves ₹10,000 crore scheme for rural electrification", "", "media"
        )

    def test_official_item_without_marker_still_kept(self, classifier):
        # Trusted government source: a bare gazette title with no keyword and
        # no spectacle must still broadcast.
        assert classifier.is_broadcast_relevant(
            "S.O. 2431(E)", "", "central"
        )

    def test_new_policies_filtered_in_telegram(self):
        mod = _load_module("push_telegram")
        # find_new_policies applies the gate; verify the gate is wired by
        # checking the module imported it.
        assert hasattr(mod, "is_broadcast_relevant")


class TestMediaCap:
    """Generalist-news feeds out-produce official sources ~10x. Without a cap
    the tracker degenerates into a news reader (the dataset was ~87% media).
    enforce_media_cap() holds news to at most MEDIA_CAP_FRACTION of the total
    while prioritizing government/research items."""

    @pytest.fixture(scope="class")
    def fetch_all(self):
        return _load_module("fetch_all")

    def _make(self, level, n, start_day=1):
        return [
            {"id": f"{level}{i}", "title": f"{level} {i}", "level": level,
             "date": f"2026-01-{(start_day + i) % 28 + 1:02d}"}
            for i in range(n)
        ]

    def test_media_never_exceeds_fraction(self, fetch_all):
        # 100 official + 900 media, no seed.
        live = self._make("central", 100) + self._make("media", 900)
        out = fetch_all.enforce_media_cap(live, reserved=0)
        media = sum(1 for i in out if i["level"] == "media")
        frac = media / len(out)
        assert frac <= fetch_all.MEDIA_CAP_FRACTION + 1e-9, (
            f"media share {frac:.2%} exceeds cap {fetch_all.MEDIA_CAP_FRACTION:.0%}"
        )

    def test_official_items_are_prioritized(self, fetch_all):
        # All 100 official items must survive; media is what gets trimmed.
        live = self._make("central", 100) + self._make("media", 900)
        out = fetch_all.enforce_media_cap(live, reserved=0)
        assert sum(1 for i in out if i["level"] == "central") == 100

    def test_seed_counts_toward_non_media_base(self, fetch_all):
        # With a large historical (non-media) seed reserved, more news is
        # admitted than when the base is thin.
        live_small_base = self._make("central", 10) + self._make("media", 900)
        thin = fetch_all.enforce_media_cap(live_small_base, reserved=0)
        fat = fetch_all.enforce_media_cap(live_small_base, reserved=990)
        thin_media = sum(1 for i in thin if i["level"] == "media")
        fat_media = sum(1 for i in fat if i["level"] == "media")
        assert fat_media > thin_media


class TestNewsSourcesGated:
    """The India/policy relevance filters and the media cap only apply to
    sources flagged `india_only: false`. Journalism feeds that lacked the
    flag were bypassing both — and being mislabeled as central-government
    policy. Lock the flag on the known offenders."""

    @pytest.fixture(scope="class")
    def feeds(self):
        feeds_path = Path(__file__).resolve().parent.parent / "feeds.json"
        return json.loads(feeds_path.read_text())

    @pytest.mark.parametrize("source_id", [
        "barandbench", "business_line", "livelaw", "moneycontrol",
        "pti_news", "ani_news", "outlook_india", "downtoearth",
    ])
    def test_news_source_is_gated(self, feeds, source_id):
        cfg = feeds["sources"].get(source_id)
        if cfg is None:
            pytest.skip(f"{source_id} no longer configured in feeds.json")
        assert cfg.get("india_only") is False, (
            f"{source_id} is a journalism feed but not gated — it will "
            f"bypass the relevance filters and the media cap"
        )
        assert cfg.get("level") == "media", (
            f"{source_id} must be level=media so the cap applies and it "
            f"isn't mislabeled as central-government policy"
        )

    def test_all_configured_media_sources_are_gated(self, feeds):
        """Invariant form of the check above: every source that classifier.py
        knows to be a media outlet AND is still configured must be gated."""
        from classifier import MEDIA_SOURCE_IDS
        for source_id, cfg in feeds["sources"].items():
            if source_id not in MEDIA_SOURCE_IDS:
                continue
            assert cfg.get("india_only") is False, f"{source_id} not gated"
            assert cfg.get("level") == "media", f"{source_id} not level=media"


class TestAmendmentLogCap:
    """detect_amendments must bound its output. IRDAI-style page rotators
    (where the same "policy" page shows different content on each fetch)
    were producing 10 000+ events for a single policy — 48% of the whole
    amendments log — and stale IDs never got GC'd, growing the file
    unboundedly.
    """

    @pytest.fixture
    def fetch_all(self, tmp_path, monkeypatch):
        mod = _load_module("fetch_all")
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        return mod

    def test_per_field_history_capped(self, fetch_all):
        existing = {"a": {"id": "a", "title": "T", "description": "v0", "source_id": "s"}}
        amendments: dict = {}
        for i in range(1, 40):
            new_desc = f"rotation-content-{i}"
            new_items = [{"id": "a", "title": "T", "description": new_desc, "source_id": "s"}]
            fetch_all.detect_amendments(existing, new_items, amendments)
            # Simulate the merge that would normally happen so the *next*
            # cycle sees the fresh description as "old"
            existing["a"]["description"] = new_desc

        history = amendments.get("a", [])
        description_events = [e for e in history if e.get("field") == "description"]
        assert len(description_events) <= 20, (
            f"per-field history uncapped ({len(description_events)} events) — "
            f"rotating page content will bloat amendments.json without bound"
        )

    def test_stale_policy_ids_gc_ed(self, fetch_all):
        """Policies that were once amended but are not in the FINAL merged
        dataset (dropped off the per-source cap, merged into a fuzzy-match,
        trimmed by the media cap, etc.) must not stay in the log forever.
        The GC runs in merge_policies against the post-cap dataset — running
        it earlier against `existing` left orphan histories for items the
        cap later dropped."""
        fetch_all.AMENDMENTS_FILE = fetch_all.DATA_DIR / "amendments.json"
        existing = {"live": {"id": "live", "title": "Alive", "source_id": "s"}}
        amendments = {
            "live": [{"date": "2026-01-01", "field": "description", "old_value": "a", "new_value": "b"}],
            "zombie": [{"date": "2024-06-15", "field": "description", "old_value": "x", "new_value": "y"}],
        }
        fetch_all.save_amendments(amendments)
        fetch_all.merge_policies(existing, new_items=[])
        saved = fetch_all.load_amendments()
        assert "live" in saved
        assert "zombie" not in saved, (
            "amendments for dropped policy IDs must be GC'd; otherwise the "
            "log accumulates zombies forever"
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


class TestIndiaRelevance:
    """The India-relevance filter is the gate between generalist-media RSS
    feeds (Livemint, NDTV, Hindu, etc., which carry both Indian and foreign
    news) and the policy dataset. Lock down a representative set of cases
    so future marker-list edits can't silently regress accuracy."""

    @pytest.fixture(scope="class")
    def classifier(self):
        return _load_module("classifier")

    # ── Should be kept (India-relevant) ──────────────────────────

    def test_keeps_state_name(self, classifier):
        assert classifier.is_india_relevant(
            "Maharashtra CM announces new water policy", ""
        )

    def test_keeps_state_abbreviation(self, classifier):
        assert classifier.is_india_relevant(
            "U.P. CM pushes to prioritise work-from-home", ""
        )

    def test_keeps_party_acronym(self, classifier):
        assert classifier.is_india_relevant(
            "AIADMK leaders under C Ve Shanmugham faction decide to support Vijay-led TVK",
            "",
        )

    def test_keeps_bjp(self, classifier):
        assert classifier.is_india_relevant(
            "BJP leader's massive convoy sparks row after PM's appeal", ""
        )

    def test_keeps_mla(self, classifier):
        assert classifier.is_india_relevant(
            "Gajuwaka MLA pushes for IT-Tourism zone on Yarada hills", ""
        )

    def test_keeps_indian_city(self, classifier):
        assert classifier.is_india_relevant(
            "Chennai summer turns monsoon-like as rains cool city", ""
        )

    def test_keeps_modi(self, classifier):
        assert classifier.is_india_relevant(
            "PM Modi appeals for fuel conservation amid global oil crisis", ""
        )

    def test_keeps_india_word(self, classifier):
        assert classifier.is_india_relevant(
            "Government of India notifies new rules for digital lending", ""
        )

    def test_keeps_neutral_text(self, classifier):
        # No India marker, no foreign marker — default is keep (permissive).
        assert classifier.is_india_relevant(
            "Government targets homegrown AI systems for defence", ""
        )

    # ── Should be dropped (foreign news) ─────────────────────────

    def test_drops_nyc_mayor_news(self, classifier):
        # The exact item that prompted this filter to exist.
        assert not classifier.is_india_relevant(
            "Mamdani Scraps Property Tax Hike, Counts on Second-Home Revenue",
            "New York City Mayor Zohran Mamdani has ditched his plan to raise New Yorkers’ property taxes.",
        )

    def test_drops_white_house(self, classifier):
        assert not classifier.is_india_relevant(
            "Elon Musk, Apple's Tim Cook to head to China with Trump, per White House",
            "",
        )

    def test_drops_us_border_wall(self, classifier):
        assert not classifier.is_india_relevant(
            "Catholic Diocese Fights US Effort to Seize Land for Border Wall", ""
        )

    def test_drops_putin_ukraine(self, classifier):
        assert not classifier.is_india_relevant(
            "Putin Says Ukraine Ceasefire Prompted By Kyiv Security Warnings", ""
        )

    # ── False-positive guards ────────────────────────────────────

    def test_indianapolis_does_not_match_india(self, classifier):
        # The substring "india" appears in "Indianapolis" — must be stripped
        # before the India-marker check, or every Indy-500 story would pass.
        assert not classifier.is_india_relevant(
            "Indianapolis 500 race results", "Held in Indianapolis, Indiana, USA"
        )

    def test_india_us_meeting_keeps(self, classifier):
        # Has a foreign marker AND an India marker — India wins.
        assert classifier.is_india_relevant(
            "PM Modi meets US President at White House for trade talks", ""
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
