---
layout: ../../layouts/Base.astro
title: "When your dashboard is lying back at you"
description: "How PolicyDhara found and fixed three silent bugs in its own metrics."
pubDate: 2026-07-07
---

# When your dashboard is lying back at you

*July 2026. A note on how PolicyDhara found and fixed three silent bugs in its own metrics, and what we changed. The figures in this post are from July 2026 and are not updated.*

---

A civic-tech tracker that quietly reports the wrong number does more harm than one that reports nothing. A wrong number carries the authority of measurement without the substance. Someone reads it, cites it and makes a decision on it, and the error spreads from there.

This note covers the three false numbers PolicyDhara's dashboard showed us this year, how they got past us, and what changed.

## Lie 1: "Added this week: 1,888"

The homepage had a hero stat that read "N policies added this week". It looked reasonable in most weeks and extraordinary in others. When one of us looked closely, the extraordinary weeks were suspicious: hundreds of policies were stamped 2026-05-06, 2026-05-07 and 2026-05-08. The Government of India does not issue that many policies in three days.

The root cause was a two-year-old five-line fallback in the fetch script:

```python
# Last resort: use today's date
if not date:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
```

Roughly half of Indian government sources do not expose a publication date. For those, the fetcher stamped today's date and moved on. Every six hours, another cycle of undated items was labelled with the current day. Over months, ninety-four percent of the dataset ended up clustered on the three days CI had run most recently.

![94% of the dataset was stamped with today's date onto just three dates, the days CI happened to run; only 6% carried a real publication date.](/blog/date-clustering.svg)

A commit in April had tried to fix this. It removed the fallback in the Python package's fetcher (`policydhara/fetchers/base.py`) and migrated the data. But CI ran a different fetcher, `scripts/fetch_all.py`, that still had the fallback, and within a few cycles the fake dates were back.

The same regression hit the `first_seen` field, which was added so that analytics could distinguish when we ingested a policy from when it was enacted. The package populated it and the script never did. Zero of 2,000 records had it.

The fix in each case was three lines added and one removed. The hard part was noticing.

## Lie 2: "Trending this week"

Once we fixed the date pollution, the homepage widget went from "1,888 added this week" to "9 enacted this week." That number is honest, and it is sobering. Only about six percent of PolicyDhara's dataset has a verified publication date. The rest of the sources publish press releases, notifications and press notes without a machine-readable date anywhere in the page.

We could keep showing a big number that measured our own fetch cadence, or show a small number that admits the coverage gap. We chose the small number. The widget now says "Enacted this week: 9" with a note underneath: "Only 6% of items in the dataset expose a publication date; the rest are excluded from this metric."

A small number you can trust is worth more than a big one you cannot.

## Lie 3: "10,495 amendments to one policy"

PolicyDhara detects amendments. When a policy reappears with different content, the fetcher logs a diff of what changed: title, description or sectors. Over 21,000 events had accumulated across 2,669 policy IDs.

There were two problems, both structural.

The largest single "policy" was an IRDAI vigilance page, with 10,495 recorded amendments, forty-eight percent of the whole log. It had not been amended that many times. The source page has a rotating content module that shows different text on each visit, and the fetcher logged each visit's text as an amendment to the previous visit's text.

Separately, 2,578 of the 2,669 policy IDs in the amendment log no longer existed in `policies.json`. They had been dropped by the per-source cap or deduplicated into other IDs, but their amendment history stayed, because nothing ever garbage-collected it.

The amendments file was 9.5 MB. After we capped per-(policy, field) history at 20 events and ran one GC pass over the orphaned IDs, it was 0.2 MB. The remaining 356 events are the real amendments.

## What the three have in common

All three failed silently, with no error, no warning and no failing test. The data pipeline kept running, the site kept deploying, and the dashboard kept showing something that looked like signal but was mostly a residue of how the plumbing worked.

Every civic-tech dashboard should assume its plumbing is wrong about something. Debugging then runs in reverse: start with a number that looks off and follow it upstream until you find the layer that made it up. In our case, all three times, that layer was a helpful default that created data when it should have admitted we did not have any.

PolicyDhara now does the following:

- **Never today-stamps.** Undated items keep an empty date, so the count of "enacted this week" is what it actually is.
- **Separates ingestion from enactment.** `first_seen` (when we saw it) and `date` (when it was issued) are populated by different logic and never fall back to each other in analytics.
- **Caps amendment history.** The cap applies per field and per policy, so a page with rotating content can no longer flood the log.
- **Filters news noise.** Generalist RSS feeds bring in celebrity, sports and crime items alongside real policy, and a policy-relevance gate now drops those before ingestion.
- **Watches its own sources.** A weekly probe of every URL opens an issue automatically when a source has been silent for three weeks, so dead sources show up where we can see them.
- **Runs the test suite before auto-merging.** A pytest gate blocks the data auto-merge if anything in the pipeline fails.

None of these changes is ambitious, and all of them are things the platform should have done from the start. Some of the most valuable work shows nothing on the surface: the number on the dashboard goes down, and we can trust it more.

The tracker is at [policydhara.impactmojo.in](https://policydhara.impactmojo.in) and the code is at [github.com/Varnasr/PolicyDhara](https://github.com/Varnasr/PolicyDhara). If you spot another false number, tell us. Those reports are the contribution we like most.

---

*PolicyDhara is an [ImpactMojo](https://impactmojo.com) initiative. Built with Astro, Python, and GitHub Actions.*
