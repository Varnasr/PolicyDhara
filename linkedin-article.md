# PolicyDhara: building an open-source policy intelligence engine for India

*How we automated the tracking of 2,000+ development policies across 22 sectors and 420+ sources, and what we learned from six months of running it.*

---

India generates a large volume of policy actions every day. They include gazette notifications, PIB press releases from every ministry, RBI circulars, bills introduced and passed in Parliament, state government orders, budget allocations, think-tank analyses and court judgments. For researchers, journalists, civil-society organisations and even policymakers, keeping up has been a manual, fragmented and often incomplete exercise.

**PolicyDhara** was built to solve this problem. This year we learned as much from getting it wrong as from getting it right.

## What is PolicyDhara?

PolicyDhara (from the Hindi/Sanskrit *dhara*, "flow" or "stream") is an open-source, auto-updating tracker of Indian development policies. It is an [ImpactMojo](https://impactmojo.com) initiative. It continuously aggregates policy actions from **400+ configured sources**, classifies them across **22 sectors**, and publishes everything on a searchable, free-to-use platform that refreshes automatically every six hours.

In practice it is a dashboard for Indian policy that updates itself.

**Live at:** [varnasr.github.io/PolicyDhara](https://varnasr.github.io/PolicyDhara)

## The scale of the problem

A policy researcher today faces all of the following:

- **50+ central-ministry press portals**, one per body, with different formats and update cadences
- **Multiple constitutional bodies** (Election Commission, NHRC, CAG, Law Commission, NGT, IBBI, PNGRB, AERB) publishing primary output on their own websites
- **28 state governments** and Union Territories with their own DIPR portals
- **Parliament and Budget** data buried in PDF repositories
- **The judiciary**, meaning the Supreme Court and every High Court, publishing judgments separately
- **Think tanks** (PRS, CPR, NIPFP, Takshashila, CSEP, Vidhi) with their own publication feeds
- **No single, unified search** across any of this

PolicyDhara brings all of it into one place.

## Coverage highlights (mid-2026)

### 400+ configured sources across three tiers

- **Central government:** every English-language Press Information Bureau ministry filter (92 dedicated feeds, one per ministry or constitutional body), plus India Code, eGazette, Parliament, RBI, NITI Aayog and data.gov.in.
- **Constitutional bodies and regulators:** Election Commission, NHRC, Lokpal, UPSC, EAC-PM, Law Commission, IBBI, PNGRB, AERB, MCA notifications, NGT, CVC, NCW and NCBC.
- **State and judiciary:** 14 state PIB regional offices, direct DIPR portals for Tamil Nadu, Karnataka and other high-volume states, the eCourts judgment aggregator and Delhi High Court's live feed.
- **Research and multilateral:** PRS Legislative Research, CPR, NIPFP, Takshashila, CSEP, Vidhi, IDFC Institute, ICMR, ICAR, and India-country pages for the World Bank, IMF and UNICEF.

### Every source is monitored

A weekly source-health job probes every URL, tracks the streak of failing probes, and files a GitHub issue when a source has gone three weeks silent. In year one a dead source simply stopped appearing and nobody saw it. Now each one is listed where we can see it.

### Sector intelligence across 22 domains

Every policy is auto-classified into one or more sectors, including Education, Health, Agriculture, Digital & Technology, Climate & Environment, Defence & Security, Governance, Social Justice, Urbanisation and Labour & Employment. Each sector has its own page with trend analysis, a source breakdown and a chronological feed.

### Parliament, Budget and state trackers

Dedicated modules cover the 18th Lok Sabha (bill introductions, session productivity, legislative trends), the Union Budget broken down by ministry and scheme, and a federal view spanning 13+ major states.

### Policy continuity across government eras

This is one of the most-used features. PolicyDhara maps policies across **five government eras**: UPA I (2004–2009), UPA II (2009–2014), NDA I (2014–2019), NDA II (2019–2024) and NDA III (2024–present). That allows longitudinal analysis of how sectors have changed across political cycles.

### Amendment tracking, now bounded

When a policy reappears with changed text, PolicyDhara logs a field-level diff. This year we found that the log had grown to 9.5 MB with 21,000+ events. Most of that came from one rotating-content page on the IRDAI website, which produced 10,495 spurious "amendments", plus 2,578 zombie entries for policy IDs that the dedup step had dropped but nothing had garbage-collected. The log is now capped and garbage-collected, and it holds the real amendment history in 0.2 MB.

### Alerts, watchlists and feeds

- Sector-based watchlists trigger email alerts on new policies (powered by Buttondown).
- A daily digest summarises additions, grouped by sector.
- Per-sector RSS feeds are available, and now per-ministry RSS as well (one feed per PIB-tracked ministry).
- Telegram alerts cover high-priority items (constitutional amendments, Union Budget, major bills).

### Full-text search

Search runs across the entire dataset with filters for sector, source, document type and date range. It runs entirely in the browser, so it is fast, private and serverless.

## What we got wrong, and fixed

The hardest lesson of 2026 was that a dashboard can quietly report false numbers. We caught and fixed three this year.

**"Added this week: 1,888."** The fetcher fell back to today's date when a source did not expose a publication date, and about half do not. Ninety-four percent of the dataset ended up clustered on three consecutive days, the days CI had run most recently. We removed the fallback, and undated items now stay undated. The homepage widget was renamed "Enacted This Week" and reports a small, accurate number in place of a large, spurious one.

**Ingestion masquerading as enactment.** Once dates were clean, the widget briefly used `first_seen` (when we ingested the item) as a fallback for `date` (when it was enacted), with the label "added this week." Any reader would take that as enactment. We now count only the enactment date, exclude undated items, and state the caveat prominently.

**Runaway amendment log.** As described above, 48% of the log was a single rotating-content page, and 96% of the policy IDs it tracked had been dropped from the main dataset months earlier.

Each fix took a few lines. The hard part was noticing.

We wrote the story up as a blog post, the kind of candid change-log that civic tech should publish more often.

## The tech behind PolicyDhara

### Architecture: serverless by design

The platform runs no servers. It is a static site generated by [Astro](https://astro.build) and hosted on GitHub Pages, with data updates driven by GitHub Actions cron jobs. That gives us **zero hosting cost and zero maintenance overhead**. It also gives us **full version history**, because every data update is a Git commit, and CDN-backed resilience.

### The data pipeline

Every six hours, a GitHub Actions workflow runs the following:

```
420+ Source Configs (feeds.json)
    ↓
Python Pipeline (fetch_all.py)
    ├→ RSS Fetcher (XML parsing, namespace handling)
    ├→ HTML Scraper (BeautifulSoup + CSS selectors, per-source scraper map)
    ├→ Sector Classifier (curated keyword-based, multi-label)
    ├→ Deduplication (by ID, source+title, title-across-sources)
    ├→ Amendment Detection (bounded per-field history + GC)
    └→ first_seen stamping + honest date handling
    ↓
Structured JSON (policies.json, amendments.json, source_health.json, meta.json)
    ↓
pytest (gates the auto-merge — bad data can't land)
    ↓
Astro Build (~2,100 static pages in ~2 minutes)
    ↓
GitHub Pages Deployment
    ↓
Email + Telegram alerts (if high-priority items detected)
```

### The classifier

PolicyDhara uses a **curated keyword-based classifier** tuned for Indian policy language, with no machine learning involved. "MGNREGA" maps to Social Protection, "5G spectrum" to Digital & Technology, and "carbon credit" to Climate & Environment. Each policy can belong to multiple sectors, and the classifier handles transliterations, acronyms and ministry-specific terminology. It is fast, transparent and auditable: anyone can read the keyword lists and see why a policy landed where it did.

### The API and embeddable widgets

- A **JSON API** at `/api/` for programmatic access with filtering
- **RSS feeds** at `/rss.xml` (all policies), `/rss/[sector].xml`, and `/rss/ministry/[ministry].xml`
- **CSV/JSON export** for bulk download
- **Embeddable widgets**: a stats badge, a sector feed, and a ~1 KB JavaScript widget with `data-*` configuration for theme, sector and count

If you run a policy research blog, an NGO website or a news portal, you can embed a live feed in under 30 seconds, with no API key required.

## Why open source?

PolicyDhara is fully open source under a permissive licence, and we chose that deliberately.

Policy transparency should be free to everyone. The data comes from public sources, and the classification logic should be auditable. Bugs should be findable by anyone who reads the code, and this year showed that they are.

Contributors have added sources, tightened classifier keyword lists, and filed issues on stats that looked off. That is how civic tech should work.

## Who is this for?

- **Policy researchers** tracking sectoral trends across government eras
- **Journalists** searching a full archive of government policy actions
- **NGOs and civil society** monitoring policies that affect their constituents
- **Students and academics** studying Indian governance
- **Government officials** wanting a cross-ministry view
- **International organisations** tracking India's development trajectory

## What's next

- Deeper judicial coverage (High Court judgments per state, via eCourts)
- Vernacular-language sources (regional press portals in Hindi, Tamil, Telugu, Kannada, Bengali)
- Better first-party date extraction (parsing PDF metadata where the page does not expose dates)
- Community-contributed source configs for niche policy domains
- Continued source-health work, since this year's audit showed that a stale source reports nothing and gives no sign that it has stopped

## Try it

- **Browse:** [varnasr.github.io/PolicyDhara](https://varnasr.github.io/PolicyDhara)
- **Contribute:** [github.com/Varnasr/PolicyDhara](https://github.com/Varnasr/PolicyDhara)
- **Embed:** Add a live policy feed to your site in one line of code
- **Subscribe:** Email digest, per-sector RSS, per-ministry RSS, or Telegram alerts

Policy is one of the most powerful levers for development outcomes. We think making it trackable, searchable and, as this year taught us, accurately measurable is a civic responsibility as well as a technical task.

---

*PolicyDhara is an [ImpactMojo](https://impactmojo.com) initiative. Built with Astro, Python, and GitHub Actions. Zero servers, zero cost, fully open source.*

*#PublicPolicy #India #OpenSource #CivicTech #GovTech #Development #PolicyResearch #DataForGood #ImpactMojo*
