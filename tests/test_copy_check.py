"""Fault injection for scripts/check_copy.py: each rule must catch its own failure."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_copy", ROOT / "scripts" / "check_copy.py")
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)


def hits(rule, text):
    return len(cc.RULES[rule].findall(text))


def test_em_dash_caught():
    assert hits("dash", "The scheme — launched in 2005 — pays women.")


def test_numeric_range_en_dash_allowed():
    assert hits("dash", "Years 2004–2014 and pages 3–5.") == 0


def test_word_en_dash_caught():
    assert hits("dash", "Centre – state relations")


def test_banned_word_caught_with_suffix():
    assert hits("banned-word", "It leverages data and fosters trust.") == 2


def test_technical_words_not_flagged():
    assert hits("banned-word", "A significant fall in the comprehensive survey.") == 0


def test_negative_parallel_caught():
    assert hits("not-x-but-y", "It is not only a tracker but also an archive.")
    assert hits("not-x-but-y", "This is not a list, but a map.")


def test_plain_negation_allowed():
    assert hits("not-x-but-y", "The data is not updated on Sundays.") == 0


def test_emoji_caught_but_interface_glyph_allowed():
    assert hits("emoji", "Done \U0001F680")
    assert hits("emoji", "✎ Blog") == 0


def test_comment_text_is_not_read():
    lits = cc._literals("// the — in a comment\nconst a = 'a plain sentence of reader text';")
    assert lits == ["a plain sentence of reader text"]


def test_ratchet_refuses_a_rise(tmp_path, monkeypatch):
    base = tmp_path / "b.json"
    base.write_text('{"x.md": {"dash": 1}}')
    monkeypatch.setattr(cc, "BASELINE", base)
    monkeypatch.setattr(cc, "scan", lambda: ({"x.md": {"dash": 2}}, []))
    assert cc.main(["check_copy.py"]) == 1
    assert cc.main(["check_copy.py", "--update"]) == 1
