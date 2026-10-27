#!/usr/bin/env python3
"""Check the copy we write against the owner's writing rules.

Reads what a reader of the site sees in our own voice: the text of pages and
posts in src/, the string literals in src/lib, and the prose documents at the
repository root. It does not read policy records (titles and descriptions come
from the government and media sources we ingest), data files or code comments.

Rules: no em dash, no en dash outside a numeric range, none of the banned
words, no "not X but Y" or "not only", no emoji.

It is a ratchet. Known violations are recorded per file and rule in
scripts/copy-baseline.json. A count that rises fails. A count that falls fails
until --update lowers the baseline, and --update refuses to raise one. Fix a
violation by deciding what the sentence says and writing it again. A dash is a
symptom, not a character to swap.

Usage:
  python3 scripts/check_copy.py            # check against the baseline
  python3 scripts/check_copy.py --update   # lower the baseline
  python3 scripts/check_copy.py --list     # print every violation
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "scripts" / "copy-baseline.json"

PAGE_GLOBS = ["src/**/*.astro", "src/**/*.md", "src/**/*.mdx"]
LIB_GLOBS = ["src/lib/*.ts", "src/pages/**/*.ts"]
DOC_FILES = ["README.md", "ROADMAP.md", "linkedin-article.md", ".github/CONTRIBUTING.md"]

BANNED = [
    "delve", "certainly", "utilise", "utilize", "leverage", "robust", "streamline",
    "harness", "foster", "underscore", "enhance", "testament", "pivotal", "intricate",
    "intricacies", "crucial", "transformative", "groundbreaking", "tapestry",
    "landscape", "paradigm", "synergy", "holistic", "nuanced", "seamless",
    "meticulous", "notable", "notably", "multifaceted", "unlock", "empower",
    "elevate", "amplify", "facilitate", "spearhead", "myriad", "plethora",
    "genuine", "genuinely", "truly", "honestly", "arguably", "vibrant", "embark",
    "navigate",
]
BANNED_RE = re.compile(r"\b(" + "|".join(BANNED) + r")(s|ed|es|ing|d)?\b", re.I)
EM_DASH_RE = re.compile("—|(?<!\\d)–|–(?!\\d)|(?<=\\w) -- (?=\\w)")
NEG_RE = re.compile(
    r"\bnot (only|just|merely)\b|\bnot [a-z' ]{1,30}, but\b|\bnot [a-z' ]{1,25} but\b", re.I
)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF]")

RULES = {
    "dash": EM_DASH_RE,
    "banned-word": BANNED_RE,
    "not-x-but-y": NEG_RE,
    "emoji": EMOJI_RE,
}


def _strip_astro(text):
    """Keep the prose of an .astro or markdown page: text nodes and the
    attributes a reader sees. Drop frontmatter code, scripts, styles and
    comments. Template expressions are dropped; their string literals are
    picked up by the literal pass."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"(?s)<!--.*?-->", " ", text)
    text = re.sub(r"(?s)\{/\*.*?\*/\}", " ", text)
    return text


def _text_and_attrs(text):
    out = []
    for m in re.finditer(r'\b(?:title|description|alt|aria-label|placeholder|content)="([^"{}]{12,})"', text):
        out.append(m.group(1))
    body = re.sub(r"<[^>]+>", "\n", text)
    body = re.sub(r"\{[^{}]*\}", " ", body)
    out.extend(line.strip() for line in body.splitlines() if len(line.strip()) > 3)
    return out


def _literals(text):
    """String literals of at least 20 characters, with comments removed."""
    text = re.sub(r"(?s)/\*.*?\*/", " ", text)
    text = re.sub(r"(?m)(^|[^:\"'])//.*$", r"\1", text)
    out = []
    for m in re.finditer(r"'((?:[^'\\\n]|\\.){20,})'|\"((?:[^\"\\\n]|\\.){20,})\"|`((?:[^`\\]|\\.){20,})`", text):
        s = next(g for g in m.groups() if g)
        if re.match(r"^[\w./:#@?&=%+~-]+$", s):  # a path or url
            continue
        out.append(s)
    return out


def collect():
    """Yield (file, text) pairs of reader-facing prose."""
    seen = set()
    for pattern in PAGE_GLOBS:
        for p in sorted(ROOT.glob(pattern)):
            if p in seen:
                continue
            seen.add(p)
            raw = p.read_text(encoding="utf-8", errors="ignore")
            rel = str(p.relative_to(ROOT))
            if p.suffix == ".astro":
                fm = ""
                if raw.startswith("---"):
                    end = raw.find("\n---", 3)
                    fm = raw[3:end] if end != -1 else ""
                parts = _text_and_attrs(_strip_astro(raw)) + _literals(fm)
                # Literals inside template expressions, e.g. {cond ? 'text' : 'more'}.
                parts += _literals(re.sub(r"(?s)^---.*?\n---", "", raw))
            else:
                parts = [ln for ln in re.sub(r"(?s)^---.*?\n---", "", raw).splitlines() if ln.strip()]
            yield rel, "\n".join(dict.fromkeys(parts))
    for pattern in LIB_GLOBS:
        for p in sorted(ROOT.glob(pattern)):
            rel = str(p.relative_to(ROOT))
            if rel in seen:
                continue
            seen.add(rel)
            yield rel, "\n".join(_literals(p.read_text(encoding="utf-8", errors="ignore")))
    for name in DOC_FILES:
        p = ROOT / name
        if p.exists():
            yield name, p.read_text(encoding="utf-8", errors="ignore")


def scan():
    counts, found = {}, []
    for rel, text in collect():
        for rule, rx in RULES.items():
            hits = list(rx.finditer(text))
            if hits:
                counts.setdefault(rel, {})[rule] = len(hits)
                for m in hits:
                    a = max(0, m.start() - 50)
                    found.append((rel, rule, text[a:m.end() + 50].replace("\n", " ")))
    return counts, found


def main(argv):
    counts, found = scan()
    if "--list" in argv:
        for rel, rule, ctx in found:
            print(f"{rel} [{rule}] ...{ctx}...")
        print(f"{len(found)} violations in {len(counts)} files")
        return 0
    base = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    if "--update" in argv:
        raised = [
            (f, r, n, base.get(f, {}).get(r, 0))
            for f, rules in counts.items() for r, n in rules.items()
            if n > base.get(f, {}).get(r, 0) and base
        ]
        if raised:
            for f, r, n, b in raised:
                print(f"refusing to raise {f} [{r}] from {b} to {n}")
            return 1
        BASELINE.write_text(json.dumps(counts, indent=2, sort_keys=True) + "\n")
        print(f"baseline written: {sum(sum(r.values()) for r in counts.values())} violations in {len(counts)} files")
        return 0
    problems = []
    for f in sorted(set(base) | set(counts)):
        for r in sorted(set(base.get(f, {})) | set(counts.get(f, {}))):
            b, n = base.get(f, {}).get(r, 0), counts.get(f, {}).get(r, 0)
            if n > b:
                problems.append(f"{f} [{r}] rose from {b} to {n}")
            elif n < b:
                problems.append(f"{f} [{r}] fell from {b} to {n}: run --update to lower the baseline")
    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK: {sum(sum(r.values()) for r in counts.values())} known violations, none new")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
