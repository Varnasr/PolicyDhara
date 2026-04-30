#!/usr/bin/env python3
"""
One-time migration to clean up policies whose `date` field is actually the
fetch date, not the publication date.

Background: until commit X, the fetcher fell back to today's date when no
publication date could be parsed. This polluted ~94% of the dataset, making
"this week" stats meaningless.

Strategy:
  1. Find dates with anomalously high concentration (>20% of dataset on one day).
     A real publication date almost never has more than a handful of policies.
  2. For policies on those anomalous dates, clear `date` (set to "") and
     populate `first_seen` with the previously-stored fake date instead.
  3. Policies with normally-distributed publication dates are left alone.

Run this once:
    python3 scripts/migrate_dates.py            # dry-run (default)
    python3 scripts/migrate_dates.py --apply    # write changes back to disk
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
POLICIES_FILE = DATA_DIR / "policies.json"

# A date is "suspect" if it accounts for more than this fraction of all policies
SUSPECT_DENSITY_THRESHOLD = 0.10  # 10%


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Write changes back to policies.json (default: dry-run)")
    parser.add_argument("--threshold", type=float, default=SUSPECT_DENSITY_THRESHOLD,
                        help=f"Density threshold (default: {SUSPECT_DENSITY_THRESHOLD})")
    args = parser.parse_args()

    if not POLICIES_FILE.exists():
        print(f"Error: {POLICIES_FILE} not found", file=sys.stderr)
        return 1

    with open(POLICIES_FILE) as f:
        policies = json.load(f)

    total = len(policies)
    print(f"Loaded {total} policies from {POLICIES_FILE}")

    date_counts = Counter(p.get("date", "") for p in policies if p.get("date"))
    suspect_dates = {
        date for date, count in date_counts.items()
        if count / total >= args.threshold
    }

    if not suspect_dates:
        print(f"No suspect dates above {args.threshold:.0%} density. Nothing to migrate.")
        return 0

    print(f"\nSuspect dates (>={args.threshold:.0%} of dataset):")
    for d in sorted(suspect_dates):
        cnt = date_counts[d]
        print(f"  {d}: {cnt} policies ({100 * cnt / total:.1f}%)")

    cleared = 0
    backfilled = 0
    for p in policies:
        d = p.get("date", "")
        if d in suspect_dates:
            # Clear `date` (we don't actually know when it was published)
            # but record what we used to think it was as first_seen
            if not p.get("first_seen"):
                p["first_seen"] = d
                backfilled += 1
            p["date"] = ""
            cleared += 1

    print(f"\nWould clear `date` on {cleared} policies ({100 * cleared / total:.1f}%)")
    print(f"Would backfill `first_seen` on {backfilled} policies that didn't have one")

    if args.apply:
        with open(POLICIES_FILE, "w") as f:
            json.dump(policies, f, indent=2, ensure_ascii=False)
        print(f"\nWrote changes to {POLICIES_FILE}")
    else:
        print("\nDRY-RUN. Re-run with --apply to write changes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
