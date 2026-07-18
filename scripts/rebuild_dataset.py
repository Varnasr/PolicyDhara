#!/usr/bin/env python3
"""Re-apply the current relevance filters, source gating, and media cap to
the already-fetched dataset in data/policies.json — offline, no network.

Use this after tightening the classifier or fixing `india_only` gating in
feeds.json. The next scheduled fetch would eventually converge on the new
rules, but until then the committed dataset (and the deployed site) keeps
serving the stale, news-heavy snapshot. This rebuilds it immediately.

Steps:
  1. Recompute each item's `level` from feeds.json — this fixes news sources
     that were mislabeled "central" only because they lacked
     `india_only: false` (e.g. Bar & Bench, BusinessLine).
  2. Drop media-source items that fail India-relevance or policy-relevance
     (spectacle, foreign news, non-policy).
  3. Enforce the media cap (news <= MEDIA_CAP_FRACTION of the total).
  4. Rewrite data/policies.json, per-item content files, and the summaries.

Run:  python3 scripts/rebuild_dataset.py [--dry-run]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from classifier import is_india_relevant, is_policy_relevant  # noqa: E402
import fetch_all  # noqa: E402

PROJECT_ROOT = Path(__file__).parent.parent
FEEDS_CONFIG = PROJECT_ROOT / "feeds.json"
DATA_POLICIES = PROJECT_ROOT / "data" / "policies.json"


def load_sources() -> dict:
    with open(FEEDS_CONFIG) as f:
        return json.load(f)["sources"]


def reclassify(items: list[dict], sources: dict) -> tuple[list[dict], int, int]:
    """Return (kept, relabeled, dropped) after re-gating and re-filtering."""
    kept: list[dict] = []
    relabeled = 0
    dropped = 0

    for item in items:
        sid = item.get("source_id", "")

        # Historical seed and items from sources no longer in the config are
        # left as-is (the seed is curated; unknown sources were trusted).
        if sid == "historical":
            kept.append(item)
            continue
        cfg = sources.get(sid)
        if cfg is None:
            kept.append(item)
            continue

        india_only = cfg.get("india_only", True)

        # Recompute level exactly as fetch_source does, so mislabeled news
        # (defaulted to "central") is corrected to "media".
        default_level = "media" if not india_only else "central"
        new_level = cfg.get("level", default_level)
        if item.get("level") != new_level:
            item["level"] = new_level
            relabeled += 1

        # Apply the relevance gates only to mixed-content media feeds;
        # official sources are trusted unconditionally.
        if not india_only:
            title = item.get("title", "")
            desc = item.get("description", "")
            if not is_india_relevant(title, desc) or not is_policy_relevant(title, desc):
                dropped += 1
                continue

        kept.append(item)

    return kept, relabeled, dropped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Report the outcome without writing files.")
    args = parser.parse_args()

    sources = load_sources()
    with open(DATA_POLICIES) as f:
        items = json.load(f)
    print(f"Loaded {len(items)} items from {DATA_POLICIES.name}")
    print(f"  before: {dict(Counter(i.get('level', '?') for i in items))}")

    kept, relabeled, dropped = reclassify(items, sources)
    print(f"Relabeled level on {relabeled} items; "
          f"dropped {dropped} media items as non-policy / off-topic")

    # Split seed vs live and enforce the media cap (mirrors merge_policies).
    seed = [i for i in kept if i.get("source_id") == "historical"]
    live = [i for i in kept if i.get("source_id") != "historical"]
    live = fetch_all.enforce_media_cap(live, reserved=len(seed))
    final = live + seed
    final.sort(key=lambda x: x.get("date", "1970-01-01"), reverse=True)

    media_ct = sum(1 for i in final if i.get("level") == "media")
    print(f"  after:  {dict(Counter(i.get('level', '?') for i in final))}")
    print(f"Final: {len(final)} items, {media_ct} media "
          f"({media_ct / max(1, len(final)):.0%})")

    if args.dry_run:
        print("(dry-run — no files written)")
        return 0

    fetch_all.write_data_json(final)
    fetch_all.write_astro_content(final)
    print("Rebuilt data/policies.json, summaries, and per-item content files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
