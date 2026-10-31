---
layout: ../../layouts/Base.astro
title: "The policy tracker that was mostly news"
description: "PolicyDhara was 87% news. Fixing it meant discovering the filter was never the real problem."
pubDate: 2026-07-18
---

# The policy tracker that was mostly news

*July 2026. How a complaint about "too much news" led us to the real reason most of our sources were never read, and what the collection looked like then. The figures in this post are from July 2026 and are not updated; the [sources page](/sources/) and the home page show current counts.*

---

The feedback was one sentence: *"There are serious problems with the filter. Mostly it is news."*

It was right. The homepage of a tracker is supposed to surface gazette notifications, cabinet decisions and bills, and ours showed crime blotter, cricket scores and celebrity items. When we counted, **87% of the dataset was generalist-media content**, and only about 12% was government or research policy. For a project called *PolicyDhara*, "policy stream", that is close to a definition of failure.

The filter looked like the culprit, so we started there. There was real work to do: the test that decides whether a news story is about policy had been made deliberately lenient. We added a spectacle blocklist that drops the clear noise (violent-crime blotter, road accidents, sports, celebrity, astrology) and pruned the keywords that were letting it through, since a bare "arrest" or "probe" is not policy. Two news sources, a legal-news site and a business paper, were being treated *as central-government policy*, so none of the news filters applied to them. We also added a hard cap: news can fill at most 40% of the dataset.

That brought the number down. It also showed us the real problem, which had nothing to do with the filter.

## The collection was small because most sources were never read

![Before and after: 406 items at 87% news became 1,727 items at 21% news, through three changes: reading every source at once, a filter for spectacle, and a 40% cap on news.](/blog/policy-filter-before-after.svg)

We should have checked this first. The tracker aggregates **422 sources**. When we tried each one by hand, **196 of them worked** and returned real content. But the site only held items from about **twenty**.

The other ~180 working sources were never read. Each update read the sources one after another and had 12 minutes in all. With 400+ sources, many of them slow government websites, time ran out after roughly the first forty. Every source further down the list, which included half the working government sources, was never tried on any given update.

![Reading one source at a time reached only ~40 of 422 sources before the 12 minutes ran out, so most government sources were never tried and news dominated by default. Reading them all at once reaches all 422.](/blog/sequential-vs-parallel.svg)

The news feeds happened to sit near the top of the list. They are fast and they always respond. So every update reliably read the news and ran out of time before it reached most of the government portals. **The site was mostly news because news was the only thing each update had time to reach.**

The fix was to read the sources at the same time. All 422 are now read well inside the 12 minutes, and a single update brings in PRS Bill Track and Legislative Research, RBI press releases and notifications, the PIB feeds for the Cabinet, PMO and both houses of Parliament, the GST Council, TRAI, dozens of ministries and a shelf of research institutes.

We also fixed how we read one page by hand. The RBI's master notifications page gave us nothing, because its table, grouped by date, is laid out differently from the pages around it. Those pages carry the circulars and directions the RBI issues, which is the material a policy tracker exists to carry. We now collect them, with their real dates.

## What the numbers look like now

The collection went from **406 items to 1,727**, and news dropped from **87% to 21%**. That is comfortably under the cap, because there is now enough real policy for news to be the minority. The homepage leads with RBI directions, cabinet approvals, PRS bill tracking and NITI analysis, with recent journalism interleaved among them.

## What we took from it

The filter work was necessary, and it did not solve the problem. When a dashboard shows the wrong mix, the instinct is to reach for the thing that decides the mix: the filter, the ranking, the weights. But the mix depends on what you collected, and we had been collecting almost none of what we claimed to. A tracker that advertises 422 sources and reaches 20 of them is barely running, so tuning its filter cannot help.

The lesson is to check that you have the data before you tune how you rank it. We now also check every source each week to see whether we actually got items from it, in addition to whether the page opened. A page can open perfectly well and give us nothing, and for months about 170 of ours did exactly that. Those are the next thing to fix, and the [sources page](/sources/) shows where each one stands.

The tracker is at [policydhara.impactmojo.in](https://policydhara.impactmojo.in) and the code is at [github.com/Varnasr/PolicyDhara](https://github.com/Varnasr/PolicyDhara). The list of sources we cannot yet read is public. If you can help us read one of those government sites again, that is the most useful contribution there is.

---

*PolicyDhara is an [ImpactMojo](https://impactmojo.com) initiative.*
