"""The IRDAI listing scraper reads the table the site serves."""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "scripts"))
    spec.loader.exec_module(mod)
    return mod


HTML = """
<table><tr><th>Archive</th><th>Short Description</th><th>Sub Title</th><th>Last Updated</th></tr>
<tr><td></td><td>Non-Archived</td>
<td>परिपत्र - बीमा नियम / Repeal of the Guidelines on dividends.pdf</td>
<td>circular</td><td>05-10-2026</td>
<td><a href="https://irdai.gov.in/document-detail?documentId=1">view</a></td></tr>
<tr><td></td><td>Non-Archived</td><td>No link here</td><td>x</td><td>06-10-2026</td></tr>
</table>
"""


def test_irdai_listing_is_read_day_first_with_english_title(monkeypatch):
    scrape = _load("fetch_scrape")
    monkeypatch.setattr(scrape, "safe_get", lambda url, headers=None: SimpleNamespace(content=HTML.encode()))
    items = scrape.scrape_irdai({"url": "x", "_source_id": "irdai_circulars"})
    assert len(items) == 1                      # the row with no link is skipped
    item = items[0]
    assert item["date"] == "2026-10-05"        # 5 October, not 10 May
    assert item["title"] == "Repeal of the Guidelines on dividends"
    assert item["description"].startswith("Circular:")
    assert item["link"].endswith("documentId=1")
