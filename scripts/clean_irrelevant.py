#!/usr/bin/env python3
"""
One-shot cleanup: scan src/content/policies/*.json and delete items that:
  (a) came from a generalist-media source (`india_only: false` in feeds.json)
  (b) and don't pass the India-relevance filter

Existing items predate the pipeline-level filter, so this script applies the
same rule retroactively. Items from official-government sources are never
touched.

Run:  python3 scripts/clean_irrelevant.py [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

# Allow `from classifier import ...`
sys.path.insert(0, str(Path(__file__).parent))
from classifier import is_india_relevant  # noqa: E402

PROJECT_ROOT = Path(__file__).parent.parent
POLICIES_DIR = PROJECT_ROOT / "src" / "content" / "policies"
FEEDS_CONFIG = PROJECT_ROOT / "feeds.json"


def load_mixed_sources() -> set[str]:
    """Return the set of source_ids whose `india_only` flag is False."""
    with open(FEEDS_CONFIG) as f:
        feeds = json.load(f)
    return {
        sid for sid, cfg in feeds["sources"].items()
        if cfg.get("india_only", True) is False
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be deleted without touching files.")
    args = parser.parse_args()

    mixed = load_mixed_sources()
    print(f"Mixed-content sources: {len(mixed)}")

    if not POLICIES_DIR.exists():
        print(f"No policies dir at {POLICIES_DIR}")
        return 0

    total = 0
    candidates = 0  # from mixed sources
    deleted = 0     # passed filter == false
    deleted_titles: list[tuple[str, str]] = []

    for fp in sorted(POLICIES_DIR.glob("*.json")):
        total += 1
        try:
            with open(fp) as f:
                item = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  skip (unreadable): {fp.name}: {e}")
            continue

        source_id = item.get("source_id", "")
        if source_id not in mixed:
            continue
        candidates += 1

        title = item.get("title", "")
        description = item.get("description", "")
        if is_india_relevant(title, description):
            continue

        deleted += 1
        deleted_titles.append((source_id, title))
        if args.dry_run:
            continue
        fp.unlink()

    print()
    print(f"Scanned: {total} items")
    print(f"From mixed sources: {candidates}")
    print(f"Filtered out (not India-relevant): {deleted}")
    if deleted_titles[:20]:
        print()
        print("Examples (up to 20):")
        for src, t in deleted_titles[:20]:
            print(f"  [{src}] {t[:90]}")
    if args.dry_run:
        print()
        print("(dry-run — no files modified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
