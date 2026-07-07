# When your dashboard is lying back at you

*July 2026 — a note on how PolicyDhara found (and fixed) three silent bugs in its own metrics, and what we did about it.*

---

A civic-tech tracker that quietly reports the wrong number is worse than one that doesn't report at all. A wrong number carries the authority of measurement without the substance. Someone reads it, cites it, decides on it — and the wrongness compounds.

This is a note about the three lies PolicyDhara's dashboard was telling us this year, why they slipped through, and what changed.

## Lie 1: "Added this week: 1,888"

The homepage had a hero stat that read "N policies added this week" — a number that felt roughly reasonable most weeks, and roughly extraordinary others. When one of us looked closely, the extraordinary weeks were suspicious: hundreds of policies stamped 2026-05-06, 2026-05-07, 2026-05-08. The Government of India is prolific but not that prolific.

The root cause was a two-year-old five-line fallback in the fetch script:

```python
# Last resort: use today's date
if not date:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
```

When a source didn't expose a publication date — and roughly half of Indian government sources don't — the fetcher stamped today's date and moved on. Every six hours, another cycle of undated items got labeled with the current day. Over months, ninety-four percent of the dataset ended up clustered on the three days CI happened to run most recently.

A commit in April *had* tried to fix this. It removed the fallback in the Python package's fetcher (`policydhara/fetchers/base.py`) and migrated the data. But CI ran a *different* fetcher — `scripts/fetch_all.py` — that still had the fallback. Within a few cycles the fake dates were back.

The same regression pattern hit the `first_seen` field, which was added specifically so analytics could distinguish *when we ingested a policy* from *when it was enacted*. The package populated it. The script never did. Zero of 2,000 records had it.

The fix in each case was small — three lines added, one line removed. What mattered was noticing.

## Lie 2: "Trending this week"

Once we fixed the date pollution, the homepage widget went from "1,888 added this week" to "9 enacted this week." That number is honest but sobering. Only about six percent of PolicyDhara's dataset has a verified publication date. The rest of the sources publish press releases, notifications, and press notes without a machine-readable date anywhere in the DOM.

We had a choice: keep showing a big number that was really a measure of our own fetch cadence, or show a small number that's honest about the coverage gap. We chose the second. The widget now says "Enacted this week: 9" with a note underneath — "Only 6% of items in the dataset expose a publication date; the rest are excluded from this metric."

Sobering, but usable. A small number you can trust beats a big one you can't.

## Lie 3: "10,495 amendments to one policy"

PolicyDhara detects amendments: when a policy reappears with different content, the fetcher logs a diff — title changed, description changed, sectors changed. Over 21,000 events had accumulated across 2,669 policy IDs.

Two problems, both structural:

The largest single "policy" — an IRDAI vigilance page — had 10,495 recorded amendments, forty-eight percent of the whole log. Not because it had actually been amended 10,495 times, but because the source page has a rotating content module that shows different text on each visit. The fetcher dutifully logged each visit's text as an "amendment" to the previous visit's text.

Meanwhile, 2,578 of the 2,669 policy IDs in the amendment log didn't exist in `policies.json` anymore. They'd been dropped by the per-source cap or deduplicated into other IDs. Their amendment history stayed. Nothing was ever garbage-collected.

The amendments file was 9.5 MB. After capping per-(policy, field) history at 20 events and running one GC pass over zombie IDs, it was 0.2 MB. The remaining 356 events are the real amendments.

## What this means

Three lies. Same shape. All silent — no error, no warning, no failing test. The data pipeline kept running, the site kept deploying, and the dashboard kept telling us something that felt like signal but was mostly a residue of how the plumbing worked.

The general lesson is unglamorous: every civic-tech dashboard should assume its plumbing is lying about something, and the debugging happens in reverse — start with a number that feels off and follow it upstream until you find the layer that made it up. In our case that was, three times running, a helpful default that quietly created data instead of admitting we didn't have it.

Concretely, PolicyDhara now:

- **Never today-stamps.** Undated items keep an empty date. The count of "enacted this week" is what it actually is.
- **Separates ingestion from enactment.** `first_seen` (when we saw it) and `date` (when it was issued) are populated by different logic and never fall back to each other in analytics.
- **Caps amendment history.** Per-field, per-policy — no more page-rotator explosions.
- **Watches its own sources.** A weekly probe of every URL in `feeds.json` opens an auto-issue when a source has gone three weeks silent, so dead sources become visible rather than invisible.
- **Runs the test suite before auto-merging.** A pytest gate now blocks the data auto-merge if anything in the pipeline is red.

None of these are ambitious. All of them are what the platform should have been doing already. Sometimes the most valuable work is the un-showable kind: the number on the dashboard goes down, and the meaning behind it goes up.

The tracker is at [varnasr.github.io/PolicyDhara](https://varnasr.github.io/PolicyDhara) and the code is at [github.com/Varnasr/PolicyDhara](https://github.com/Varnasr/PolicyDhara). If you spot another lie, tell us — that's exactly the kind of contribution we like most.

---

*PolicyDhara is an [ImpactMojo](https://impactmojo.com) initiative. Built with Astro, Python, and GitHub Actions.*
