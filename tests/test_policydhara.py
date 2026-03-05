"""Tests for the policydhara package."""

import json
import tempfile
from pathlib import Path

import pytest

from policydhara.models import Policy
from policydhara.classifier import PolicyClassifier
from policydhara.store import PolicyStore
from policydhara.fetchers.rss import parse_rss_xml
from policydhara.fetchers.base import _categorize_type, _extract_date_from_title, _is_valid_title


# ── Models ───────────────────────────────────────────────────────────


class TestPolicy:
    def test_generate_id_deterministic(self):
        id1 = Policy.generate_id("Test Policy", "source1")
        id2 = Policy.generate_id("Test Policy", "source1")
        assert id1 == id2
        assert len(id1) == 12

    def test_generate_id_different_inputs(self):
        id1 = Policy.generate_id("Test Policy", "source1")
        id2 = Policy.generate_id("Test Policy", "source2")
        assert id1 != id2

    def test_sector_slug(self):
        assert Policy.sector_slug("Climate & Environment") == "climate-environment"
        assert Policy.sector_slug("Digital & Technology") == "digital-technology"
        assert Policy.sector_slug("Education") == "education"

    def test_from_dict(self):
        data = {
            "id": "abc123",
            "title": "Test Policy",
            "sectors": ["Health", "Education"],
            "type": "legislation",
            "extra_field": "ignored",
        }
        p = Policy.from_dict(data)
        assert p.id == "abc123"
        assert p.title == "Test Policy"
        assert p.sectors == ["Health", "Education"]
        assert p.type == "legislation"

    def test_to_dict_roundtrip(self):
        p = Policy(id="test", title="My Policy", sectors=["Health"])
        d = p.to_dict()
        p2 = Policy.from_dict(d)
        assert p.id == p2.id
        assert p.title == p2.title

    def test_matches(self):
        p = Policy(id="1", title="National Education Policy 2020", description="Reform in higher education")
        assert p.matches("education")
        assert p.matches("EDUCATION")
        assert p.matches("reform")
        assert not p.matches("agriculture")

    def test_year(self):
        p = Policy(id="1", title="Test", date="2024-05-15")
        assert p.year == 2024
        p2 = Policy(id="2", title="Test", date="")
        assert p2.year is None

    def test_str(self):
        p = Policy(id="1", title="Test", date="2024-01-01", sectors=["Health"], source_short="PIB")
        s = str(p)
        assert "Test" in s
        assert "Health" in s
        assert "PIB" in s


# ── Classifier ───────────────────────────────────────────────────────


class TestClassifier:
    def setup_method(self):
        self.classifier = PolicyClassifier()

    def test_classify_education(self):
        sectors = self.classifier.classify("National Education Policy 2020", "Reform in school and university education")
        assert "Education" in sectors

    def test_classify_health(self):
        sectors = self.classifier.classify("Ayushman Bharat PMJAY Extension", "Healthcare coverage for BPL families")
        assert "Health" in sectors

    def test_classify_multiple_sectors(self):
        sectors = self.classifier.classify(
            "Digital Health Mission",
            "Using technology for healthcare delivery and telemedicine"
        )
        assert len(sectors) >= 2
        assert "Health" in sectors or "Digital & Technology" in sectors

    def test_classify_fallback_to_source(self):
        sectors = self.classifier.classify("zzzzz qqqq xyzzy", "", source_sectors=["Agriculture"])
        assert sectors == ["Agriculture"]

    def test_classify_default_fallback(self):
        sectors = self.classifier.classify("zzzzz qqqq xyzzy")
        assert sectors == ["Governance & Reform"]

    def test_max_sectors(self):
        sectors = self.classifier.classify(
            "Big policy on education health agriculture",
            "education health agriculture climate energy",
            max_sectors=2,
        )
        assert len(sectors) <= 2

    def test_scores(self):
        scores = self.classifier.scores("National Education Policy reform in schools")
        assert "Education" in scores
        assert scores["Education"] > 0

    def test_all_sectors(self):
        assert len(self.classifier.sectors) == 22
        assert "Education" in self.classifier.sectors
        assert "Health" in self.classifier.sectors


# ── Store ────────────────────────────────────────────────────────────


@pytest.fixture
def sample_policies():
    return [
        Policy(id="1", title="NEP 2020", description="Education reform", date="2020-07-29",
               source_id="pib", source_name="PIB", sectors=["Education"], type="policy", level="central"),
        Policy(id="2", title="Ayushman Bharat", description="Health insurance", date="2018-09-23",
               source_id="pib", source_name="PIB", sectors=["Health", "Social Protection"],
               type="scheme", level="central"),
        Policy(id="3", title="Maharashtra Water Policy", description="State water management",
               date="2019-03-15", source_id="mh_govt", source_name="Maharashtra Govt",
               sectors=["Water & Sanitation"], type="policy", level="state", state="Maharashtra"),
        Policy(id="4", title="GST Amendment 2023", description="Tax reform", date="2023-08-01",
               source_id="cbic", source_name="CBIC", sectors=["Finance & Economy"],
               type="legislation", level="central"),
        Policy(id="5", title="PM KISAN", description="Farmer income support", date="2019-02-01",
               source_id="pib", source_name="PIB", sectors=["Agriculture", "Social Protection"],
               type="scheme", level="central"),
    ]


@pytest.fixture
def store(sample_policies):
    return PolicyStore(sample_policies)


class TestStore:
    def test_len(self, store):
        assert len(store) == 5

    def test_iter(self, store):
        titles = [p.title for p in store]
        assert "NEP 2020" in titles

    def test_search(self, store):
        results = store.search("education")
        assert len(results) == 1
        assert results[0].title == "NEP 2020"

    def test_search_case_insensitive(self, store):
        results = store.search("AYUSHMAN")
        assert len(results) == 1

    def test_search_no_results(self, store):
        assert store.search("blockchain") == []

    def test_search_limit(self, store):
        results = store.search("P", limit=2)  # matches multiple
        assert len(results) <= 2

    def test_filter_by_sector(self, store):
        results = store.filter_by_sector("Health")
        assert len(results) == 1
        assert results[0].title == "Ayushman Bharat"

    def test_filter_by_sector_list(self, store):
        results = store.filter_by_sector(["Health", "Education"])
        assert len(results) == 2

    def test_filter_by_state(self, store):
        results = store.filter_by_state("Maharashtra")
        assert len(results) == 1

    def test_filter_by_type(self, store):
        results = store.filter_by_type("scheme")
        assert len(results) == 2

    def test_filter_by_source(self, store):
        results = store.filter_by_source("pib")
        assert len(results) == 3

    def test_filter_by_level(self, store):
        results = store.filter_by_level("state")
        assert len(results) == 1

    def test_filter_by_date_range(self, store):
        results = store.filter_by_date_range(start="2020-01-01", end="2024-12-31")
        assert len(results) == 2  # NEP 2020, GST 2023

    def test_query_combined(self, store):
        results = store.query(sector="Social Protection", policy_type="scheme")
        assert len(results) == 2  # Ayushman Bharat, PM KISAN

    def test_sector_counts(self, store):
        counts = store.sector_counts()
        assert counts["Social Protection"] == 2
        assert counts["Education"] == 1

    def test_source_counts(self, store):
        counts = store.source_counts()
        assert counts["pib"] == 3

    def test_type_counts(self, store):
        counts = store.type_counts()
        assert counts["scheme"] == 2
        assert counts["policy"] == 2
        assert counts["legislation"] == 1

    def test_get_ids(self, store):
        ids = store.get_ids()
        assert ids == {"1", "2", "3", "4", "5"}

    def test_to_json(self, store):
        json_str = store.to_json()
        data = json.loads(json_str)
        assert len(data) == 5

    def test_to_csv(self, store):
        csv_str = store.to_csv()
        lines = csv_str.strip().split("\n")
        assert len(lines) == 6  # header + 5 rows

    def test_load_from_file(self, sample_policies):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([p.to_dict() for p in sample_policies], f)
            f.flush()
            store = PolicyStore.load(f.name)
            assert len(store) == 5

    def test_from_dicts(self):
        data = [{"id": "1", "title": "Test"}]
        store = PolicyStore.from_dicts(data)
        assert len(store) == 1
        assert store[0].title == "Test"

    def test_export_to_file(self, store):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            store.to_json(f.name)
        loaded = PolicyStore.load(f.name)
        assert len(loaded) == len(store)


# ── Fetcher helpers ──────────────────────────────────────────────────


class TestCategorizeType:
    def test_legislation(self):
        assert _categorize_type("Digital Data Protection Bill 2023", "") == "legislation"

    def test_scheme(self):
        assert _categorize_type("PM Surya Ghar Yojana", "") == "scheme"

    def test_notification(self):
        assert _categorize_type("Gazette Notification No. 123", "") == "notification"

    def test_budget(self):
        assert _categorize_type("Union Budget 2025-26", "") == "budget"

    def test_research(self):
        assert _categorize_type("NITI Aayog Report on SDGs", "") == "research"

    def test_announcement(self):
        assert _categorize_type("PM announces new initiative", "") == "announcement"

    def test_default(self):
        assert _categorize_type("Something generic", "") == "policy"


class TestExtractDate:
    def test_budget_year(self):
        assert _extract_date_from_title("Union Budget 2025-26") == "2025-02-01"

    def test_budget_document(self):
        result = _extract_date_from_title("Key to Budget Document, 2026")
        assert result.endswith("-02-01")

    def test_outcome_framework(self):
        result = _extract_date_from_title("Outcome Framework 2025-26")
        assert result.endswith("-02-01")

    def test_act_year(self):
        assert _extract_date_from_title("The Securities Markets Code, 2025") == "2025-06-01"

    def test_no_year(self):
        assert _extract_date_from_title("Some policy without year") == ""

    def test_no_future_dates(self):
        result = _extract_date_from_title("World Wildlife Day 2026")
        assert result != ""
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert result <= today

    def test_past_year_ok(self):
        assert _extract_date_from_title("Some Act, 2020") == "2020-06-01"

    def test_wildlife_day(self):
        assert _extract_date_from_title("World Wildlife Day 2025") == "2025-03-03"

    def test_republic_day(self):
        assert _extract_date_from_title("Republic Day Celebrations 2025") == "2025-01-26"

    def test_independence_day(self):
        assert _extract_date_from_title("Independence Day Address 2024") == "2024-08-15"

    def test_yoga_day(self):
        assert _extract_date_from_title("International Yoga Day 2024") == "2024-06-21"

    def test_gandhi_jayanti(self):
        assert _extract_date_from_title("Gandhi Jayanti Celebrations 2024") == "2024-10-02"

    def test_constitution_day(self):
        assert _extract_date_from_title("Constitution Day 2024") == "2024-11-26"

    def test_explicit_date_month_first(self):
        assert _extract_date_from_title("Notification dated March 3, 2025") == "2025-03-03"

    def test_explicit_date_day_first(self):
        assert _extract_date_from_title("Notification dated 15 January 2025") == "2025-01-15"


class TestTitleValidation:
    def test_valid_title(self):
        assert _is_valid_title("National Education Policy 2020") is True

    def test_empty_title(self):
        assert _is_valid_title("") is False

    def test_short_title(self):
        assert _is_valid_title("Hi") is False

    def test_gazette_junk(self):
        assert _is_valid_title("Recent Extra Ordinary GazettesMinistrySubject") is False

    def test_nav_junk(self):
        assert _is_valid_title("Parliament") is False
        assert _is_valid_title("Session Track") is False

    def test_garbled_long_title(self):
        assert _is_valid_title("A" * 100) is False

    def test_long_valid_title(self):
        title = "This is a very long but perfectly valid policy title about something important " * 2
        assert _is_valid_title(title) is True


class TestRssParser:
    def test_parse_rss(self):
        xml = b"""<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>Test Policy</title>
              <link>https://example.com</link>
              <description>A test policy item</description>
              <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
            </item>
          </channel>
        </rss>"""
        items = parse_rss_xml(xml)
        assert len(items) == 1
        assert items[0]["title"] == "Test Policy"
        assert items[0]["date"] == "2024-01-01"

    def test_parse_atom(self):
        xml = b"""<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Atom Entry</title>
            <link href="https://example.com" rel="alternate"/>
            <summary>An Atom feed entry</summary>
            <published>2024-06-15T00:00:00Z</published>
          </entry>
        </feed>"""
        items = parse_rss_xml(xml)
        assert len(items) == 1
        assert items[0]["title"] == "Atom Entry"

    def test_parse_empty(self):
        assert parse_rss_xml(b"<rss><channel></channel></rss>") == []

    def test_parse_invalid(self):
        assert parse_rss_xml(b"not xml at all") == []

    def test_handles_bom(self):
        xml = b'\xef\xbb\xbf<?xml version="1.0"?><rss version="2.0"><channel><item><title>BOM Test</title></item></channel></rss>'
        items = parse_rss_xml(xml)
        assert len(items) == 1
        assert items[0]["title"] == "BOM Test"
