#!/usr/bin/env python3
"""Check data/evidence.json.

Every case on the Evidence pages is a claim about what a policy did, so the
file has to carry its own support: a source that was opened, a quotation for
each figure, and a date the figures were last checked. A case that lacks any
of these fails the build, because the page would still render without them.

Usage: python3 scripts/check_evidence.py [path]
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "data" / "evidence.json"

VERDICTS = {"worked", "did-not-work", "mixed"}
DESIGNS = {"rct", "quasi-experimental", "observational", "other"}
LEVELS = {"national", "state", "district"}
KINDS = {"journal", "working-paper", "government", "other"}
AREAS = {
    "Poverty and social protection",
    "Education",
    "Health",
    "Governance and participation",
    "Environment and climate",
    "Water, sanitation and infrastructure",
    "Justice and public safety",
    "Tax and public finance",
    "Digital government",
}

# Words the owner's house style bans. Applied to our own prose only; a
# quotation or a citation is printed as the source wrote it.
BANNED = [
    "delve", "certainly", "utilise", "utilize", "leverage", "robust",
    "streamline", "harness", "foster", "underscore", "enhance", "testament",
    "pivotal", "intricate", "crucial", "transformative", "groundbreaking",
    "tapestry", "landscape", "paradigm", "synergy", "holistic", "nuanced",
    "seamless", "meticulous", "notable", "notably", "multifaceted", "unlock",
    "empower", "elevate", "amplify", "facilitate", "spearhead", "myriad",
    "plethora", "genuine", "genuinely", "truly", "honestly", "arguably",
]
BANNED_RE = re.compile(r"\b(" + "|".join(BANNED) + r")\w*\b", re.I)
EM_DASH = re.compile("—|–|--")  # em dash, en dash, double hyphen
NEGATIVE_PARALLEL = re.compile(
    r"\bnot (only|just|merely)\b|\bnot [^.;,]{1,40}, but\b|\bnot [^.;,]{1,40} but\b", re.I
)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
NUMBER = re.compile(r"\d[\d,]*\.?\d*")


def _s(value):
    return isinstance(value, str) and value.strip() != ""


def _prose_problems(label, text):
    out = []
    if EM_DASH.search(text):
        out.append(f"{label}: contains an em dash, en dash or double hyphen")
    m = BANNED_RE.search(text)
    if m:
        out.append(f"{label}: banned word '{m.group(0)}'")
    if NEGATIVE_PARALLEL.search(text):
        out.append(f"{label}: 'not X but Y' construction")
    if EMOJI.search(text):
        out.append(f"{label}: emoji")
    if "NOT VERIFIED" in text:
        out.append(f"{label}: unverified marker left in text")
    return out


def _numbers(text):
    return {n.replace(",", "").rstrip(".") for n in NUMBER.findall(text)}


def validate_case(c, today=None):
    errs = []
    cid = c.get("id", "<no id>")
    p = f"[{cid}]"

    if not (_s(c.get("id")) and ID_RE.match(c["id"])):
        errs.append(f"{p} id must be lower-case words joined by hyphens")
    for f in ("title", "intervention", "verdict_basis", "design_detail", "sample", "period"):
        if not _s(c.get(f)):
            errs.append(f"{p} missing {f}")
    if c.get("area") not in AREAS:
        errs.append(f"{p} area '{c.get('area')}' is not in the list")
    if c.get("verdict") not in VERDICTS:
        errs.append(f"{p} verdict must be one of {sorted(VERDICTS)}")
    if c.get("design") not in DESIGNS:
        errs.append(f"{p} design must be one of {sorted(DESIGNS)}")

    g = c.get("geography")
    if not isinstance(g, dict) or g.get("level") not in LEVELS or not isinstance(g.get("states"), list):
        errs.append(f"{p} geography needs a level and a list of states")
    elif g["level"] != "national" and not g["states"]:
        errs.append(f"{p} a {g['level']}-level case must name its states")

    effects = c.get("effects")
    if not isinstance(effects, list) or not effects:
        errs.append(f"{p} needs at least one effect")
    else:
        for i, e in enumerate(effects):
            q = f"{p} effect {i + 1}"
            for f in ("outcome", "result", "quote", "page_or_section"):
                if not _s(e.get(f)):
                    errs.append(f"{q} missing {f}")
            if e.get("interval_or_se") is not None and not _s(e.get("interval_or_se")):
                errs.append(f"{q} interval_or_se must be text or null")
            if _s(e.get("quote")) and len(e["quote"].split()) > 40:
                errs.append(f"{q} quote is longer than 40 words")
            # The figure we print has to be visible in the passage we cite.
            if _s(e.get("result")) and _s(e.get("quote")):
                want = _numbers(e["result"])
                if want and not (want & _numbers(e["quote"])):
                    errs.append(f"{q} no number in result '{e['result']}' appears in its quotation")

    if not isinstance(c.get("caveats"), list) or not c.get("caveats"):
        errs.append(f"{p} needs at least one caveat")

    sources = c.get("sources")
    if not isinstance(sources, list) or not sources:
        errs.append(f"{p} needs at least one source")
    else:
        for i, s in enumerate(sources):
            q = f"{p} source {i + 1}"
            if not _s(s.get("citation")):
                errs.append(f"{q} missing citation")
            if not (_s(s.get("url")) and s["url"].startswith("https://")):
                errs.append(f"{q} url must start with https://")
            if s.get("kind") not in KINDS:
                errs.append(f"{q} kind must be one of {sorted(KINDS)}")

    v = c.get("verified_on")
    if not (_s(v) and ISO_DATE.match(v)):
        errs.append(f"{p} verified_on must be an ISO date")
    else:
        try:
            d = date.fromisoformat(v)
            if d > (today or date.today()):
                errs.append(f"{p} verified_on is in the future")
        except ValueError:
            errs.append(f"{p} verified_on is not a real date")

    # House style, on our own prose only.
    for f in ("title", "intervention", "verdict_basis", "design_detail", "sample", "period"):
        if _s(c.get(f)):
            errs += _prose_problems(f"{p} {f}", c[f])
    for i, e in enumerate(effects if isinstance(effects, list) else []):
        for f in ("outcome", "result", "interval_or_se", "page_or_section"):
            if _s(e.get(f)):
                errs += _prose_problems(f"{p} effect {i + 1} {f}", e[f])
    for i, t in enumerate(c.get("caveats") or []):
        if _s(t):
            errs += _prose_problems(f"{p} caveat {i + 1}", t)
    return errs


def validate(data, today=None):
    errs = []
    cases = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(cases, list) or not cases:
        return ["file must hold a non-empty 'cases' list"]
    seen = set()
    for c in cases:
        if c.get("id") in seen:
            errs.append(f"duplicate id {c.get('id')}")
        seen.add(c.get("id"))
        errs += validate_case(c, today)
    return errs


def main(argv):
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT
    data = json.loads(path.read_text(encoding="utf-8"))
    errs = validate(data)
    if errs:
        print(f"{len(errs)} problem(s) in {path.name}:")
        for e in errs:
            print("  " + e)
        return 1
    print(f"OK: {len(data['cases'])} evidence cases in {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
