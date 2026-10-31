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

The cause was a two-year-old rule in the way we collect items: if a source gives no date, use today's.

Roughly half of Indian government sources do not show a publication date. For those, we stamped today's date and moved on. Every six hours, another batch of undated items was labelled with that day. Over months, ninety-four percent of the collection ended up on the three most recent update days.

![94% of the collection was stamped with today's date onto just three dates, the days the site had most recently updated; only 6% carried a real publication date.](/blog/date-clustering.svg)

We had tried to fix this in April, and corrected the dates already stored. But the regular updates used a second copy of the collecting program that still had the old rule, and within a few updates the false dates were back.

The same thing happened to the record of when we first saw each item, which was added so that we could tell when we collected a policy apart from when it was issued. Only the copy that was not in use filled it in, so none of 2,000 records had it.

Each fix was small. The hard part was noticing.

## Lie 2: "Trending this week"

Once we fixed the false dates, the homepage widget went from "1,888 added this week" to "9 enacted this week." That number is honest, and it is sobering. Only about six percent of PolicyDhara's items have a verified publication date. The rest of the sources publish press releases, notifications and press notes with no date anywhere on the page that we can read.

We could keep showing a big number that measured how often we update, or show a small number that admits the coverage gap. We chose the small number. The widget now says "Enacted this week: 9" with a note underneath: "Only 6% of items in the dataset expose a publication date; the rest are excluded from this metric."

A small number you can trust is worth more than a big one you cannot.

## Lie 3: "10,495 amendments to one policy"

PolicyDhara detects amendments. When a policy reappears with different content, we record what changed: title, description or sectors. Over 21,000 events had accumulated across 2,669 policy IDs.

There were two problems, both structural.

The largest single "policy" was an IRDAI vigilance page, with 10,495 recorded amendments, forty-eight percent of the whole log. It had not been amended that many times. The source page has a rotating content module that shows different text on each visit, and we recorded each visit's text as an amendment to the previous visit's text.

Separately, 2,578 of the 2,669 policies in the amendment record were no longer on the site. They had been removed or merged with duplicates, but their amendment history had stayed behind.

The amendment record was 9.5 MB. After we kept at most 20 changes per field of each policy and cleared out the history of policies no longer on the site, it was 0.2 MB. The remaining 356 changes are real amendments.

## What the three have in common

All three failed silently, with no error and no warning. The site kept updating, and the dashboard kept showing something that looked like a signal but mostly reflected how we collected the data.

Every civic-tech dashboard should assume the way it collects data is wrong about something. Finding the fault then runs in reverse: start with a number that looks off and trace it back until you find the step that made it up. In our case, all three times, that step was a convenient default that created data when it should have admitted we did not have any.

PolicyDhara now does the following:

- It never stamps today's date on an undated item, so the count of "enacted this week" is what it actually is.
- It keeps when we first saw an item apart from when it was issued, and never uses one in place of the other.
- It keeps at most 20 changes per field of each policy, so a page with rotating content can no longer flood the amendment record.
- It filters news. General news feeds bring in celebrity, sports and crime items alongside real policy, and those are now dropped before they reach the site.
- It watches its sources. Every source is checked weekly, and one that has given nothing for three weeks is flagged to us and counted on the [sources page](/sources/).
- It tests each update before it goes live, and holds back an update that fails.

None of these changes is ambitious, and all of them are things the platform should have done from the start. Some of the most valuable work shows nothing on the surface: the number on the dashboard goes down, and we can trust it more.

The tracker is at [policydhara.impactmojo.in](https://policydhara.impactmojo.in) and the code is at [github.com/Varnasr/PolicyDhara](https://github.com/Varnasr/PolicyDhara). If you spot another false number, tell us. Those reports are the contribution we like most.

---

*PolicyDhara is an [ImpactMojo](https://impactmojo.com) initiative.*
