---
layout: ../../layouts/Base.astro
title: "The policy tracker that was mostly news"
description: "PolicyDhara was 87% news. Fixing it meant discovering the filter was never the real problem."
pubDate: 2026-07-18
---

# The policy tracker that was mostly news

*July 2026 — how a complaint about "too much news" turned into a fetch-architecture bug, and what the dataset looks like now.*

---

The feedback was one sentence: *"There are serious problems with the filter — mostly it is news."*

It was right. A tracker whose homepage is supposed to surface gazette notifications, cabinet decisions, and bills was instead a wall of crime blotter, cricket scores, and celebrity items. When we counted, **87% of the dataset was generalist-media content** — and only about 12% was genuine government or research policy. For a thing called *PolicyDhara* — "policy stream" — that is close to a definition of failure.

The obvious culprit was the filter, so that's where we started. And there was real work to do there: the news-relevance gate was, by its own code comment, "intentionally lenient." We added a spectacle blocklist that drops the clear noise — violent-crime blotter, road accidents, sports, celebrity, astrology — and pruned the keywords that were letting it through (a bare "arrest" or "probe" is not policy). Two feeds that were quietly being ingested *as central-government policy* — a legal-news site and a business paper — turned out to be missing a config flag, so they bypassed every filter. And we added a hard cap: news can fill at most 40% of the dataset.

That got the number down. But it also exposed the real problem — which was never the filter at all.

## The dataset was tiny because the pipeline never finished

![Before and after: 406 items at 87% news became 1,727 items at 21% news, via three levers — parallel fetch, a spectacle filter, and a 40% news cap.](/PolicyDhara/blog/policy-filter-before-after.svg)

Here is the thing we should have checked first. The tracker aggregates **422 sources**. When we ran each one directly, **196 of them worked** — they returned real content. But the live dataset only had data from about **twenty**.

Where did the other ~180 working sources go? They were never fetched.

The pipeline fetched sources one at a time, with a per-source timeout, inside a 12-minute total budget. Do the arithmetic: 400+ sources, many of them slow government scrapers, fetched sequentially, and the clock runs out after reaching roughly the first forty. Everything past that point in the config — half the working government sources — was simply never tried on any given run.

![Sequential fetch reached only ~40 of 422 sources before the 12-minute timeout, so most government sources were never tried and news dominated by default. Parallel fetch reaches all 422.](/PolicyDhara/blog/sequential-vs-parallel.svg)

And which sources happened to sit early in the config, inside the reachable window? The news RSS feeds. They're fast, they always respond, and they were near the front of the list. So every run, the pipeline reliably fetched the news and reliably ran out of time before it got to most of the government portals. **The dataset wasn't mostly news because the filter was weak. It was mostly news because news was the only thing the pipeline had time to reach.**

The fix was to stop fetching one-at-a-time. Fetching sources concurrently, the whole set of 422 completes comfortably inside the budget. Suddenly PRS Bill Track and Legislative Research, RBI press releases *and* notifications, the PIB feeds for the Cabinet, PMO, and both houses of Parliament, the GST Council, TRAI, dozens of ministries, and a shelf of research institutes all show up on the same run.

While we were in there, we fixed one scraper by hand: the RBI master-notifications page returned zero items because its date-grouped table didn't match the generic parser. It's the kind of source — the actual circulars and directions the RBI issues — that a policy tracker exists to carry. Now it returns them, with real dates.

## What the numbers look like now

The dataset went from **406 items to 1,727**, and news dropped from **87% to 21%** — comfortably under the cap, not because we filtered harder, but because there is finally enough real policy for news to be the minority. The homepage now leads with RBI directions, cabinet approvals, PRS bill tracking, and NITI analysis, with recent journalism interleaved rather than dominating.

## What we took from it

The filter work was necessary and it wasn't the answer. The instinct when a dashboard shows the wrong mix is to reach for the thing that decides the mix — the filter, the ranking, the weights. But the mix is downstream of *what you collected*, and we had quietly been collecting almost none of what we claimed to. A tracker that advertises 422 sources and reaches 20 of them isn't filtering wrong; it's barely running.

So the un-showable lesson, again: before tuning how you rank the data, check that you actually have the data. We now also run every source through a health check that says not just "did the URL respond" but "did the scraper extract anything" — because a page can return a cheerful `200 OK` and a shell of nothing, and for months, ~170 of ours did exactly that. Those are the next thing to fix.

The tracker is at [varnasr.github.io/PolicyDhara](https://varnasr.github.io/PolicyDhara) and the code is at [github.com/Varnasr/PolicyDhara](https://github.com/Varnasr/PolicyDhara). The source-health backlog is public — if you want to revive a dead government scraper, that's the most useful contribution there is.

---

*PolicyDhara is an [ImpactMojo](https://impactmojo.com) initiative. Built with Astro, Python, and GitHub Actions.*
