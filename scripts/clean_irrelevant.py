#!/usr/bin/env python3
"""
One-shot cleanup: scan src/content/policies/*.json AND data/policies.json
and remove items that:
  (a) came from a generalist-media source (`india_only: false` in feeds.json)
  (b) and don't pass the India-relevance filter

The Astro site reads `data/policies.json` directly (see src/lib/data.ts), so
that aggregated file is the source of truth at render time. The per-item
files under src/content/policies are also pruned for consistency. Items
from official-government sources are never touched.

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
DATA_POLICIES = PROJECT_ROOT / "data" / "policies.json"
FEEDS_CONFIG = PROJECT_ROOT / "feeds.json"


def load_mixed_sources() -> set[str]:
    """Return the set of source_ids whose `india_only` flag is False."""
    with open(FEEDS_CONFIG) as f:
        feeds = json.load(f)
    return {
        sid for sid, cfg in feeds["sources"].items()
        if cfg.get("india_only", True) is False
    }


def _should_drop(item: dict, mixed: set[str]) -> bool:
    source_id = item.get("source_id", "")
    if source_id not in mixed:
        return False
    return not is_india_relevant(
        item.get("title", ""),
        item.get("description", ""),
    )


def clean_per_item_files(mixed: set[str], dry_run: bool) -> list[tuple[str, str]]:
    """Delete per-policy JSON files. Returns list of (source_id, title) dropped."""
    deleted: list[tuple[str, str]] = []
    if not POLICIES_DIR.exists():
        return deleted

    for fp in sorted(POLICIES_DIR.glob("*.json")):
        try:
            with open(fp) as f:
                item = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  skip (unreadable): {fp.name}: {e}")
            continue
        if not _should_drop(item, mixed):
            continue
        deleted.append((item.get("source_id", ""), item.get("title", "")))
        if not dry_run:
            fp.unlink()
    return deleted


def clean_aggregated_file(mixed: set[str], dry_run: bool) -> list[tuple[str, str]]:
    """Rewrite data/policies.json without the irrelevant items. This is the
    file Astro actually reads at build time — pruning per-item files alone
    is insufficient because lib/data.ts ignores them."""
    deleted: list[tuple[str, str]] = []
    if not DATA_POLICIES.exists():
        return deleted

    with open(DATA_POLICIES) as f:
        items = json.load(f)

    if not isinstance(items, list):
        print(f"  unexpected shape in {DATA_POLICIES}; skipping")
        return deleted

    kept: list[dict] = []
    for item in items:
        if _should_drop(item, mixed):
            deleted.append((item.get("source_id", ""), item.get("title", "")))
            continue
        kept.append(item)

    if dry_run:
        return deleted

    with open(DATA_POLICIES, "w") as f:
        json.dump(kept, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be deleted without touching files.")
    args = parser.parse_args()

    mixed = load_mixed_sources()
    print(f"Mixed-content sources: {len(mixed)}")

    deleted_files = clean_per_item_files(mixed, args.dry_run)
    deleted_aggregated = clean_aggregated_file(mixed, args.dry_run)

    print()
    print(f"src/content/policies — items dropped: {len(deleted_files)}")
    print(f"data/policies.json    — items dropped: {len(deleted_aggregated)}")

    # Show a handful from whichever source had drops.
    sample = deleted_aggregated or deleted_files
    if sample[:20]:
        print()
        print("Examples (up to 20):")
        for src, t in sample[:20]:
            print(f"  [{src}] {t[:90]}")
    if args.dry_run:
        print()
        print("(dry-run — no files modified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
