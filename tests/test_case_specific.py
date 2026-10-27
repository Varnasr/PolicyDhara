"""Orders about one named person or firm are not policy and are not kept."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("fetch_all", ROOT / "scripts" / "fetch_all.py")
fetch_all = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_all)

DROPPED = [
    "Release Order – Sumit Wadhwa (PAN: AAOPW8621R), Pal Singh (PAN: BDKPS9758P)",
    "Prohibitory Order No.1579/2026 issued against R Senthil Kumar under Recovery Certificate Nos. 7902 of 2024",
    "SEBI Order for Compliance - General Remittance Order dated 26.10.2026 in Recovery Certificate No. 8511 of 2025",
    "Order in the matter of Avadhut Sathe Trading Academy Private Limited",
    "Adjudication Order in respect of Madhukar Dubey and its proprietorship firm",
    "Press Release - Order in the matter of Canara HSBC Life Insurance 10.09.2026",
    "Consumer Education Workshop at North Delhi (Delhi) by Vodafone Idea Limited",
    "Consumer Awareness Program at Udupi (Karnataka) by Coordinated Action of Consumer Organisations",
]

KEPT = [
    "Securities and Exchange Board of India (Alternative Investment Funds) (Third Amendment) Regulations, 2026",
    "Master Circular for Mutual Funds",
    "Securities and Exchange Board of India (Prohibition of Insider Trading) Regulations, 2015",
    "Draft Water Metro Guidelines 2026 - public comments invited",
    "Reserve Bank of India (Commercial Banks) Second Amendment Directions, 2026",
    "Circular - Submission of Transparency Audit for the Year 2025-26",
]


def test_orders_about_named_people_and_firms_are_dropped():
    for title in DROPPED:
        assert fetch_all.is_case_specific(title), title


def test_policy_documents_are_kept():
    for title in KEPT:
        assert not fetch_all.is_case_specific(title), title


def test_the_stored_archive_is_purged_in_merge(monkeypatch):
    monkeypatch.setattr(fetch_all, "load_amendments", lambda: {})
    monkeypatch.setattr(fetch_all, "save_amendments", lambda a: None)
    existing = {
        "a": {"id": "a", "title": DROPPED[0], "level": "central", "kind": "instrument", "date": "2026-10-01", "source_id": "sebi"},
        "b": {"id": "b", "title": KEPT[1], "level": "central", "kind": "instrument", "date": "2026-10-02", "source_id": "sebi"},
    }
    merged = fetch_all.merge_policies(existing, [])
    assert [m["id"] for m in merged] == ["b"]
