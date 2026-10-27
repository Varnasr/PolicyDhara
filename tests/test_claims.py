"""Numbers written in prose must agree with the data they describe.

The documents used to say 350, 380 and 420 sources for a tracker whose
feeds.json holds one number. A count in prose that nothing compares drifts,
so any count of sources in the documents below has to equal feeds.json.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ["README.md", "pyproject.toml", "package.json", "CITATION.cff", ".github/CONTRIBUTING.md"]
CLAIM = re.compile(r"(\d[\d,]*)\+?\s+(?:configured\s+|official\s+)?sources", re.I)


def test_source_counts_in_documents_match_feeds_json():
    feeds = json.loads((ROOT / "feeds.json").read_text(encoding="utf-8"))
    actual = len(feeds["sources"])
    for name in DOCS:
        path = ROOT / name
        if not path.exists():
            continue
        for m in CLAIM.finditer(path.read_text(encoding="utf-8")):
            claimed = int(m.group(1).replace(",", ""))
            assert claimed == actual, f"{name} says {claimed} sources, feeds.json has {actual}"


def test_the_pattern_catches_a_wrong_count():
    assert CLAIM.search("fetches from ~380 configured sources")
    assert CLAIM.search("380+ sources")
    assert not CLAIM.search("fetches from hundreds of sources")
