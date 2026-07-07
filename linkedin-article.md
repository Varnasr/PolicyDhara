# PolicyDhara: Building an Open-Source Policy Intelligence Engine for India

*How we automated the tracking of 2,000+ development policies across 22 sectors and 420+ sources — and what we learned from six months of running it.*

---

India generates an extraordinary volume of policy actions every day. Gazette notifications, PIB press releases from every ministry, RBI circulars, bills introduced and passed in Parliament, state government orders, budget allocations, think-tank analyses, court judgments — the sheer breadth is difficult to overstate. For researchers, journalists, civil-society organisations, and even policymakers, keeping up has been a manual, fragmented, and often incomplete exercise.

This is the problem **PolicyDhara** was built to solve — and this year we learned as much from getting it wrong as from getting it right.

## What Is PolicyDhara?

PolicyDhara (from the Hindi/Sanskrit *dhara* — "flow" or "stream") is an open-source, auto-updating tracker of Indian development policies. Built as an [ImpactMojo](https://impactmojo.com) initiative, it continuously aggregates policy actions from **400+ configured sources**, classifies them across **22 sectors**, and publishes everything on a searchable, free-to-use platform — refreshed every six hours, automatically.

Think of it as a living, breathing dashboard for Indian policy — one that never sleeps.

**Live at:** [varnasr.github.io/PolicyDhara](https://varnasr.github.io/PolicyDhara)

## The Scale of the Problem

Consider what a policy researcher faces today:

- **50+ central-ministry press portals**, one per body, with different formats and update cadences
- **Multiple constitutional bodies** (Election Commission, NHRC, CAG, Law Commission, NGT, IBBI, PNGRB, AERB) publishing primary output on their own websites
- **28 state governments** and Union Territories with their own DIPR portals
- **Parliament and Budget** data buried in PDF repositories
- **Judiciary** — Supreme Court and every High Court — publishing judgments separately
- **Think tanks** (PRS, CPR, NIPFP, Takshashila, CSEP, Vidhi) with their own publication feeds
- **No single, unified search** across any of this

PolicyDhara brings all of it into one place.

## Coverage Highlights (Mid-2026)

### 400+ configured sources across three tiers

- **Central government** — every English-language Press Information Bureau ministry filter (92 dedicated feeds, one per ministry / constitutional body), plus India Code, eGazette, Parliament, RBI, NITI Aayog, data.gov.in.
- **Constitutional bodies & regulators** — Election Commission, NHRC, Lokpal, UPSC, EAC-PM, Law Commission, IBBI, PNGRB, AERB, MCA notifications, NGT, CVC, NCW, NCBC.
- **State & judiciary** — 14 state PIB regional offices, direct DIPR portals for Tamil Nadu, Karnataka, and other high-volume states, plus eCourts judgment aggregator and Delhi High Court's live feed.
- **Research & multilateral** — PRS Legislative Research, CPR, NIPFP, Takshashila, CSEP, Vidhi, IDFC Institute, ICMR, ICAR, and India-country pages for World Bank, IMF, and UNICEF.

### Every source is monitored

A weekly source-health job probes every URL, tracks streak of failing probes, and files a GitHub issue when a source has gone three weeks silent. Dead sources become **visible**, not invisible — a big change from year one.

### Sector intelligence across 22 domains

Every policy is auto-classified into one or more sectors — Education, Health, Agriculture, Digital & Technology, Climate & Environment, Defence & Security, Governance, Social Justice, Urbanisation, Labour & Employment, and more. Each sector has its own page with trend analysis, source breakdown, and chronological feed.

### Parliament, Budget & State Trackers

Dedicated modules for the 18th Lok Sabha (bill introductions, session productivity, legislative trends), Union Budget breakdown by ministry and scheme, and a federal view spanning 13+ major states.

### Policy Continuity Across Government Eras

One of the most-used features: PolicyDhara maps policies across **five government eras** — UPA I (2004–2009), UPA II (2009–2014), NDA I (2014–2019), NDA II (2019–2024), and NDA III (2024–present) — enabling longitudinal analysis of how sectors have evolved across political cycles.

### Amendment Tracking, Now Bounded

When a policy reappears with changed text, PolicyDhara logs a field-level diff. This year we discovered the log had grown to 9.5 MB with 21,000+ events — largely from one rotating-content page on the IRDAI website spuriously producing 10,495 "amendments," plus 2,578 zombie entries for policy IDs that had been dropped by the dedup step but never garbage-collected. The log is now capped and GC'd; it holds real amendment history at 0.2 MB.

### Alerts, Watchlists & Feeds

- Sector-based watchlists trigger email alerts on new policies (powered by Buttondown).
- A daily digest summarises additions, grouped by sector.
- Per-sector RSS feeds and now per-ministry RSS (one feed per PIB-tracked ministry).
- Telegram alerts for high-priority items (constitutional amendments, Union Budget, major bills).

### Full-Text Search

Search across the entire dataset with filters for sector, source, document type, and date range. Runs entirely in the browser — fast, private, serverless.

## What We Got Wrong (And Fixed)

The hardest lesson of 2026 was that a dashboard can quietly lie to you. Three examples we caught and fixed this year:

**"Added this week: 1,888."** The fetcher fell back to today's date when a source didn't expose a publication date — and about half don't. Ninety-four percent of the dataset ended up clustered on three consecutive days: the days CI happened to run most recently. We removed the fallback; undated items now stay undated. The homepage widget was renamed "Enacted This Week" and reports a small, honest number instead of a large, spurious one.

**Ingestion masquerading as enactment.** Once dates were clean, the widget briefly used `first_seen` (when we ingested the item) as a fallback for `date` (when it was enacted) — with the label "added this week." That reads as enactment to any reader. We now count only the enactment date, exclude undated items, and label the caveat prominently.

**Runaway amendment log.** Detailed above — 48% of the log was a single rotating-content page, and 96% of the policy IDs it tracked had been dropped from the main dataset months earlier.

Each fix took a few lines. What mattered was noticing.

We wrote it up as a transparency-flavoured blog post — the honest kind of change-log that civic tech should be publishing more of.

## The Tech Behind PolicyDhara

### Architecture: Serverless by Design

Zero running servers. The whole platform is a static site generated by [Astro](https://astro.build), hosted on GitHub Pages, with data updates driven by GitHub Actions cron jobs. Result: **zero hosting cost, zero maintenance overhead, full version history** (every data update is a Git commit), and CDN-backed resilience.

### The Data Pipeline

Every six hours, a GitHub Actions workflow runs the following:

```
420+ Source Configs (feeds.json)
    ↓
Python Pipeline (fetch_all.py)
    ├→ RSS Fetcher (robust XML parsing, namespace handling)
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

### The Classifier

Rather than ML, PolicyDhara uses a **curated keyword-based classifier** tuned for Indian policy language. "MGNREGA" maps to Social Protection, "5G spectrum" to Digital & Technology, "carbon credit" to Climate & Environment. Each policy can belong to multiple sectors; the classifier handles transliterations, acronyms, and ministry-specific terminology. It's fast, transparent, and auditable — anyone can read the keyword lists and see why a policy landed where it did.

### The API & Embeddable Widgets

- A **JSON API** at `/api/` for programmatic access with filtering
- **RSS feeds** at `/rss.xml` (all policies), `/rss/[sector].xml`, and `/rss/ministry/[ministry].xml`
- **CSV/JSON export** for bulk download
- **Embeddable widgets** — stats badge, sector feed, and a ~1 KB JavaScript widget with `data-*` configuration for theme, sector, and count

If you run a policy research blog, an NGO website, or a news portal, you can embed a live feed in under 30 seconds — no API key required.

## Why Open Source?

PolicyDhara is fully open source under a permissive licence. This is deliberate.

Policy transparency shouldn't be a premium product. The data comes from public sources. The classification logic should be auditable. The bugs should be findable, and — as this year proved — findable by anyone who reads the code.

We've had contributors add sources, tighten classifier keyword lists, and file issues on stats that felt off. That's exactly how civic tech should work.

## Who Is This For?

- **Policy researchers** tracking sectoral trends across government eras
- **Journalists** searching a full archive of government policy actions
- **NGOs and civil society** monitoring policies that affect their constituents
- **Students and academics** studying Indian governance
- **Government officials** wanting a cross-ministry view
- **International organisations** tracking India's development trajectory

## What's Next

- Deeper judicial coverage (High Court judgments per state, via eCourts)
- Vernacular-language sources (regional press portals in Hindi, Tamil, Telugu, Kannada, Bengali)
- Better first-party date extraction (parsing PDF metadata where the DOM doesn't expose dates)
- Community-contributed source configs for niche policy domains
- Continued source-health hygiene — as this year's audit showed, a stale source is a silent lie

## Try It

- **Browse:** [varnasr.github.io/PolicyDhara](https://varnasr.github.io/PolicyDhara)
- **Contribute:** [github.com/Varnasr/PolicyDhara](https://github.com/Varnasr/PolicyDhara)
- **Embed:** Add a live policy feed to your site in one line of code
- **Subscribe:** Email digest, per-sector RSS, per-ministry RSS, or Telegram alerts

Policy is one of the most powerful levers for development outcomes. Making it trackable, searchable, and — as this year taught us — *honestly measurable* isn't just a technical exercise. It's a civic imperative.

---

*PolicyDhara is an [ImpactMojo](https://impactmojo.com) initiative. Built with Astro, Python, and GitHub Actions. Zero servers, zero cost, fully open source.*

*#PublicPolicy #India #OpenSource #CivicTech #GovTech #Development #PolicyResearch #DataForGood #ImpactMojo*
