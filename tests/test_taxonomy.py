"""Tests for the source-authority-aware document taxonomy.

The regression this guards against: categorize_item_type() used to type items
by keyword alone and defaulted everything unmatched to "policy", so news
features, court-hearing reports, and university course adverts all surfaced
on the tracker labeled as policies. The taxonomy bounds an item's kind by who
published it — journalism can only be `news`, research only `analysis`, and
only official sources produce `instrument` / `process` documents.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from classifier import (  # noqa: E402
    categorize_item,
    get_source_authority,
    normalize_sector_names,
    KIND_INSTRUMENT,
    KIND_PROCESS,
    KIND_ANNOUNCEMENT,
    KIND_ANALYSIS,
    KIND_NEWS,
)

FEEDS = json.loads(
    (Path(__file__).resolve().parent.parent / "feeds.json").read_text()
)["sources"]


def cat(title, desc="", source_id="pib", cfg=None):
    if cfg is None:
        cfg = FEEDS.get(source_id, {})
    return categorize_item(title, desc, source_id, cfg)


# ── Authority bounds the kind ────────────────────────────────────────────


class TestAuthorityBounds:
    def test_media_item_is_never_policy(self):
        # Real regression: this NDTV headline was typed "policy".
        kind, doc_type = cat(
            "PM Modi's 'Vande Mataram' Message Set To Fly Into Space Today",
            source_id="ndtv_rss",
        )
        assert kind == KIND_NEWS
        assert doc_type == "news"

    def test_media_item_with_policy_keywords_is_still_news(self):
        kind, _ = cat(
            "Cabinet approves new National Education Policy amendment",
            source_id="the_hindu_policy",
        )
        assert kind == KIND_NEWS

    def test_think_tank_output_is_analysis(self):
        # Real regression: this course advert was typed "scheme".
        kind, _ = cat(
            "Certificate Programme on Public Health Fundamentals: Who is it "
            "for and What does it offer?",
            source_id="azim_premji",
        )
        assert kind == KIND_ANALYSIS

    def test_international_body_output_is_analysis(self):
        kind, doc_type = cat(
            "India Development Update report", source_id="world_bank_india",
            cfg={"short_name": "World Bank"},
        )
        assert kind == KIND_ANALYSIS
        assert doc_type == "report"

    def test_longform_source_typed_longform(self):
        kind, doc_type = cat(
            "The Political Economy of Land Reform in Bihar",
            source_id="india_forum",
        )
        assert kind == KIND_ANALYSIS
        assert doc_type == "longform"


class TestSourceAuthority:
    def test_explicit_config_authority_wins(self):
        assert get_source_authority("anything", {"authority": "regulator"}) == "regulator"

    def test_media_list_overrides(self):
        assert get_source_authority("ndtv_rss", {}) == "media"

    def test_courts_are_legal(self):
        assert get_source_authority("delhi_hc", FEEDS.get("delhi_hc", {})) == "legal"

    def test_default_is_government(self):
        assert get_source_authority("pib", FEEDS["pib"]) == "government"


# ── Official documents: instruments vs process vs announcement ───────────


class TestOfficialTyping:
    def test_act_with_year(self):
        kind, doc_type = cat("The Bharatiya Nyaya Sanhita Act, 2023 comes into force")
        assert (kind, doc_type) == (KIND_INSTRUMENT, "act")

    def test_direction_citing_an_act_is_not_an_act(self):
        # RBI directions cite their parent act; they are notifications.
        kind, doc_type = cat(
            "Directions under Section 35A read with Section 56 of the "
            "Banking Regulation Act, 1949", source_id="rbi",
        )
        assert (kind, doc_type) == (KIND_INSTRUMENT, "notification")

    def test_schedule_exclusion_is_not_an_act(self):
        _, doc_type = cat(
            "Exclusion of 'X Co-operative Bank Ltd.' from the Second Schedule "
            "to the Reserve Bank of India Act, 1934", source_id="rbi",
        )
        assert doc_type == "notification"

    def test_rules_with_year(self):
        kind, doc_type = cat("Digital Personal Data Protection Rules, 2025 notified")
        assert (kind, doc_type) == (KIND_INSTRUMENT, "rules")

    def test_scheme(self):
        kind, doc_type = cat("PM-KISAN Yojana: 18th instalment released")
        assert (kind, doc_type) == (KIND_INSTRUMENT, "scheme")

    def test_workshop_programme_is_not_a_scheme(self):
        # Real regression: TRAI consumer-education camps were typed "scheme".
        kind, doc_type = cat(
            "Consumer Education Workshop at Anand (Gujarat) by Reliance Jio "
            "under Consumer Awareness Program", source_id="trai",
        )
        assert (kind, doc_type) == (KIND_ANNOUNCEMENT, "release")

    def test_named_policy_in_title(self):
        kind, doc_type = cat("Foreign Trade Policy 2023 amended")
        assert (kind, doc_type) == (KIND_INSTRUMENT, "policy")

    def test_plain_press_release_is_announcement_not_policy(self):
        kind, doc_type = cat("PM inaugurates new terminal at Surat airport")
        assert (kind, doc_type) == (KIND_ANNOUNCEMENT, "release")

    def test_government_report_is_analysis(self):
        kind, doc_type = cat("India State of Forest Report 2025 released")
        assert (kind, doc_type) == (KIND_ANALYSIS, "report")

    def test_union_budget(self):
        kind, doc_type = cat("Union Budget 2026-27: Demands for Grants")
        assert (kind, doc_type) == (KIND_INSTRUMENT, "budget")


class TestProcessDocuments:
    def test_bill(self):
        kind, doc_type = cat("The Delimitation Bill, 2026", source_id="prs_bills")
        assert (kind, doc_type) == (KIND_PROCESS, "bill")

    def test_treasury_bill_is_not_a_bill(self):
        kind, doc_type = cat(
            "Auction of 91-Day, 182-Day and 364-Day Treasury Bills",
            source_id="rbi",
        )
        assert kind != KIND_PROCESS
        assert doc_type != "bill"

    def test_draft_rules_open_for_comment(self):
        kind, doc_type = cat("Draft Battery Waste Management Rules published for comments")
        assert (kind, doc_type) == (KIND_PROCESS, "draft")

    def test_consultation_paper(self):
        kind, doc_type = cat(
            "Consultation Paper on Regulating Converged Digital Technologies",
            source_id="trai",
        )
        assert (kind, doc_type) == (KIND_PROCESS, "draft")

    def test_starred_question_reply(self):
        kind, doc_type = cat(
            "Progress under Jal Jeevan Mission",
            "This information was given by the Minister of State for Jal "
            "Shakti in a written reply to a question in Lok Sabha today.",
        )
        assert (kind, doc_type) == (KIND_PROCESS, "question")

    def test_unstarred_question(self):
        kind, doc_type = cat(
            "Reply to Lok Sabha Unstarred Question No. 1234 on MGNREGA wages")
        assert (kind, doc_type) == (KIND_PROCESS, "question")

    def test_standing_committee_report(self):
        kind, doc_type = cat(
            "Standing Committee on Finance presents report on Digital "
            "Competition Bill")
        assert (kind, doc_type) == (KIND_PROCESS, "committee_report")

    def test_constituent_assembly_debate(self):
        kind, doc_type = cat("Constituent Assembly Debates: Volume VII")
        assert (kind, doc_type) == (KIND_PROCESS, "debate")


# ── Sector hygiene ───────────────────────────────────────────────────────


class TestSectorNormalization:
    def test_comma_string_hint_is_split_and_mapped(self):
        assert normalize_sector_names("economy, governance") == [
            "Finance & Economy", "Governance & Reform",
        ]

    def test_unknown_junk_is_dropped(self):
        assert normalize_sector_names("astrology") == []

    def test_canonical_names_pass_through(self):
        assert normalize_sector_names(["Health"]) == ["Health"]

    def test_slug_style_hint(self):
        assert normalize_sector_names("digital-technology") == ["Digital & Technology"]


# ── Dataset invariants (run against the committed data) ──────────────────


class TestDatasetInvariants:
    @pytest.fixture(scope="class")
    def items(self):
        path = Path(__file__).resolve().parent.parent / "data" / "policies.json"
        return json.loads(path.read_text())

    def test_every_item_has_kind(self, items):
        assert all("kind" in i for i in items)

    def test_no_media_item_claims_to_be_an_instrument(self, items):
        offenders = [
            i["title"] for i in items
            if i.get("authority") == "media" and i.get("kind") != "news"
        ]
        assert offenders == []

    def test_no_analysis_source_claims_instruments(self, items):
        offenders = [
            i["title"] for i in items
            if i.get("authority") in ("think_tank", "international")
            and i.get("kind") in ("instrument", "process")
        ]
        assert offenders == []
