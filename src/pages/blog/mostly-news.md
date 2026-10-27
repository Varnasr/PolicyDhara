---
layout: ../../layouts/Base.astro
title: "The policy tracker that was mostly news"
description: "PolicyDhara was 87% news. Fixing it meant discovering the filter was never the real problem."
pubDate: 2026-07-18
---

# The policy tracker that was mostly news

*July 2026. How a complaint about "too much news" led us to a fetch-architecture bug, and what the dataset looked like then. The figures in this post are from July 2026 and are not updated; the [sources page](/sources/) and the home page show current counts.*

---

The feedback was one sentence: *"There are serious problems with the filter. Mostly it is news."*

It was right. The homepage of a tracker is supposed to surface gazette notifications, cabinet decisions and bills, and ours showed crime blotter, cricket scores and celebrity items. When we counted, **87% of the dataset was generalist-media content**, and only about 12% was government or research policy. For a project called *PolicyDhara*, "policy stream", that is close to a definition of failure.

The filter looked like the culprit, so we started there. There was real work to do: the news-relevance gate was, by its own code comment, "intentionally lenient." We added a spectacle blocklist that drops the clear noise (violent-crime blotter, road accidents, sports, celebrity, astrology) and pruned the keywords that were letting it through, since a bare "arrest" or "probe" is not policy. Two feeds were being ingested *as central-government policy*, a legal-news site and a business paper, and both were missing a config flag, so they bypassed every filter. We also added a hard cap: news can fill at most 40% of the dataset.

That brought the number down. It also showed us the real problem, which had nothing to do with the filter.

## The dataset was tiny because the pipeline never finished

![Before and after: 406 items at 87% news became 1,727 items at 21% news, through three changes: parallel fetch, a spectacle filter and a 40% news cap.](/blog/policy-filter-before-after.svg)

We should have checked this first. The tracker aggregates **422 sources**. When we ran each one directly, **196 of them worked** and returned real content. But the live dataset only had data from about **twenty**.

The other ~180 working sources were never fetched. The pipeline fetched sources one at a time, each with its own timeout, inside a 12-minute total budget. With 400+ sources, many of them slow government scrapers, the clock ran out after roughly the first forty. Everything past that point in the config, which included half the working government sources, was never tried on any given run.

![Sequential fetch reached only ~40 of 422 sources before the 12-minute timeout, so most government sources were never tried and news dominated by default. Parallel fetch reaches all 422.](/blog/sequential-vs-parallel.svg)

The news RSS feeds happened to sit early in the config, inside the reachable window. They are fast, they always respond, and they were near the front of the list. So every run reliably fetched the news and ran out of time before it reached most of the government portals. **The dataset was mostly news because news was the only thing the pipeline had time to reach.**

The fix was to fetch sources concurrently. The whole set of 422 now completes comfortably inside the budget, and a single run brings in PRS Bill Track and Legislative Research, RBI press releases and notifications, the PIB feeds for the Cabinet, PMO and both houses of Parliament, the GST Council, TRAI, dozens of ministries and a shelf of research institutes.

While we were in there, we fixed one scraper by hand. The RBI master-notifications page returned zero items because its date-grouped table did not match the generic parser. Those pages carry the circulars and directions the RBI issues, which is the material a policy tracker exists to carry. The scraper now returns them, with real dates.

## What the numbers look like now

The dataset went from **406 items to 1,727**, and news dropped from **87% to 21%**. That is comfortably under the cap, because there is now enough real policy for news to be the minority. The homepage leads with RBI directions, cabinet approvals, PRS bill tracking and NITI analysis, with recent journalism interleaved among them.

## What we took from it

The filter work was necessary, and it did not solve the problem. When a dashboard shows the wrong mix, the instinct is to reach for the thing that decides the mix: the filter, the ranking, the weights. But the mix depends on what you collected, and we had been collecting almost none of what we claimed to. A tracker that advertises 422 sources and reaches 20 of them is barely running, so tuning its filter cannot help.

The lesson is to check that you have the data before you tune how you rank it. We now also run every source through a health check that asks whether the scraper extracted anything, in addition to whether the URL responded. A page can return a cheerful `200 OK` with a shell of nothing in it, and for months about 170 of ours did exactly that. Those are the next thing to fix.

The tracker is at [policydhara.impactmojo.in](https://policydhara.impactmojo.in) and the code is at [github.com/Varnasr/PolicyDhara](https://github.com/Varnasr/PolicyDhara). The source-health backlog is public. If you want to revive a dead government scraper, that is the most useful contribution there is.

---

*PolicyDhara is an [ImpactMojo](https://impactmojo.com) initiative. Built with Astro, Python, and GitHub Actions.*
