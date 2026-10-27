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


TABLE = """
<table><tr><th>Sr. No.</th><th>Date</th><th>Subject</th></tr>
<tr><td>1</td><td>08 Jul, 2026</td><td>Notification under section 1 of the Code <a href="/n.pdf">pdf</a></td></tr>
<tr><td>2</td><td>05/10/2026</td><td>Appointment of a member of the Board of the Authority</td></tr>
<tr><td>3</td><td>soon</td><td>A row whose date cannot be read at all</td></tr>
<tr><td>4</td><td>01 Jan, 2026</td><td>Short</td></tr>
</table>
"""


def test_dated_table_reads_header_columns_and_skips_unreadable_rows(monkeypatch):
    scrape = _load("fetch_scrape")
    monkeypatch.setattr(scrape, "safe_get", lambda url, headers=None: SimpleNamespace(content=TABLE.encode()))
    items = scrape.scrape_dated_table({"url": "https://example.gov.in/list"})
    assert [i["date"] for i in items] == ["2026-07-08", "2026-10-05"]   # day first: 5 October
    assert items[0]["link"] == "https://example.gov.in/n.pdf"


LINKS = """
<ul>
<li><a href="/w/press-1">Press release on the new pension scheme launch</a> 08-07-2026</li>
<li><a href="/w/tender-1">Tender document for appointment of an agency</a> 16 Oct 2026</li>
<li><a href="/w/a">First item that is long enough</a> <a href="/w/b">Second long item in one block</a> 01-01-2026</li>
<li><a href="/w/future">Notice dated in the far future of this year</a> 01-01-2999</li>
<li><a href="/w/nodate">An item with no date beside it at all</a></li>
</ul>
"""


def test_dated_links_keep_only_unambiguous_dated_documents(monkeypatch):
    scrape = _load("fetch_scrape")
    monkeypatch.setattr(scrape, "safe_get", lambda url, headers=None: SimpleNamespace(content=LINKS.encode()))
    items = scrape.scrape_dated_links({"url": "https://example.gov.in/"})
    assert [i["date"] for i in items] == ["2026-07-08"]   # tender, shared block, future and undated all skipped
    assert items[0]["link"] == "https://example.gov.in/w/press-1"


SEBI = """
<table><tr><th>Date</th><th>Title</th></tr>
<tr><td>Jul 21, 2026</td><td>Operationalisation of freezing of holdings of promoters</td>
<td><a href="https://www.sebi.gov.in/legal/circulars/jul-2026/x.html">x</a></td></tr>
<tr><td>Jul 17, 2026</td><td>Title with no link at all in this row</td></tr>
<tr><td>soon</td><td>Row with a date that cannot be read at all</td><td><a href="/y">y</a></td></tr>
</table>
"""


def test_sebi_listing_posts_with_the_listing_page_as_referer(monkeypatch):
    scrape = _load("fetch_scrape")
    seen = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        seen.update(data=data, headers=headers)
        return SimpleNamespace(content=SEBI.encode(), raise_for_status=lambda: None)

    monkeypatch.setattr(scrape.requests, "post", fake_post)
    items = scrape.scrape_sebi_listing({"sebi_ssid": "7"})
    assert "ssid=7" in seen["headers"]["Referer"]       # without it SEBI answers 'Unauthorized'
    assert seen["data"]["ssid"] == "7"
    assert [i["date"] for i in items] == ["2026-07-21"]
    assert items[0]["description"].startswith("Circular:")
