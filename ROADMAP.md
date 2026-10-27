# PolicyDhara roadmap

A living list of what comes next. PolicyDhara aggregates Indian development
policy from official sources every six hours. This roadmap is public so
contributors can pick something up. See [How to help](#how-to-help) at the
bottom.

Status legend: Done, In progress, Planned. A section heading carries the status
of the items under it, except where an item says otherwise.

---

## Recently shipped (done)

- Parallel fetch. Sources fetch concurrently, so all of them are reached inside
  the time budget instead of about 40. The dataset grew from 406 to 1,727 items.
- News filter and cap. A spectacle blocklist (crime, sport, celebrity), source
  gating fixes and a hard 40% cap on media items brought the news share from
  87% to 21%.
- Policy-forward homepage ranking. Official policy leads and dominates, news is
  interleaved, and operational chaff (auctions, workshops, exam results) sinks
  below the feed.
- Policy-only charts. Every graph, ticker and stat now counts policy items
  (`level != media`), so news no longer skews the visualisations.
- Government-era normalisation. The UPA-vs-NDA comparison is now shown as
  per-month rates with a partial-window flag and is given less prominence, so a
  documented collection artefact no longer reads as a real policy gap.
- Historical backfill (1991–2014). 181 Central Acts pulled from India Code by
  enactment year (RTI, NREGA, RTE, Food Security and others) fill the gap in
  older-era coverage from an authoritative source.
- RBI notifications scraper. The master circulars and directions list now
  returns dated items.
- Source health reporting. The weekly probe runs the real fetcher and buckets
  every source as `WORKS / REDUNDANT / SELECTOR_BROKEN / SHELL / DEAD`. Direct
  ministry sites whose releases already arrive via PIB are marked `REDUNDANT`
  (no data lost) and no longer appear as broken.
- Scraper cleanup. SEBI and ADB were revived through the correct RSS feeds, 26
  dead, redundant or news sources were removed, and a lenient `lxml` fallback
  keeps malformed feeds parsing.
- Package filter parity. `pip install policydhara` now filters news the same
  way the live pipeline does.
- Astro 7, formal typography (Libre Franklin and Newsreader), and a
  mobile-responsiveness pass.

---

## Next: source coverage (planned)

A triage of all sources (latest local probe):

| Bucket | Count | Meaning | Fix |
|---|---|---|---|
| `WORKS` | ~195 | returns content | — |
| `REDUNDANT` | ~27 | ministry site duplicated by its PIB feed | none, no data lost |
| `SHELL` | ~105 | JS-rendered / empty page | needs a headless fetch path |
| `DEAD` | ~24 | unreachable / TLS / 404 | CI re-probes; prune if confirmed |

Most "broken" sources are not losing us any policy. The largest remaining gain
is in the `SHELL` bucket: JS-rendered government SPAs (NITI Aayog, Parliament
bills, several regulators) that a plain HTTP fetch cannot read.

- Headless fetch path for `SHELL` sources. Render JS with the pre-installed
  Chromium, then parse. This is the main remaining gain and is tracked as a
  GitHub issue.
- Per-source CSS-selector overrides in `feeds.json` (`row_selector` /
  `title_selector` / `date_selector`), so one pattern revives many sources.
- Let CI prune the `DEAD` set. Several gov gazette and regulator sources
  (e-Gazette, TRAI, CCI, Parliament) fail only from a sandboxed network. The
  weekly CI probe judges them from a clean network, and the board flags the
  rest.

## Data quality (planned)

- De-duplicate near-identical policies across sources more aggressively.
- Backfill publication dates where a source buries them in the page body.
- Add a confidence and provenance flag per item (official, media or research).

## Features (planned)

- Done: the source-health page. The `WORKS / REDUNDANT / SHELL / DEAD` buckets
  are live on `/sources`, with a "covered by PIB" badge so coverage is
  transparent.
- Per-policy social share cards (OG images).
- Saved searches and email alerts per keyword (sector alerts already exist).
- Diff view on the policy detail page (amendment history is tracked).

## Performance and tech (planned)

- Build time grows with the dataset (about 2.5 minutes at 1,727 items).
  Investigate content-collection build cost and paginate the JSON API
  (`policies.json` is served whole at about 1.3 MB).
- Consolidate the two codebases. `scripts/` (the live pipeline) and the
  `policydhara/` package duplicate fetch and sector logic, and only the
  relevance filter is currently shared. Merging them removes a whole class of
  drift (see the April date-fallback regression in the blog).

## Writing (planned)

Blog posts we want to write, since the codebase keeps generating material:

- "What breaks when you scrape the Indian government": the `SELECTOR_BROKEN` /
  `SHELL` / `DEAD` taxonomy, with examples.
- "What counts as a policy?": designing a relevance filter for a firehose.
- "The 40% rule": keeping a policy tracker from becoming a news reader.
- "`first_seen` vs `date`": why civic dashboards must separate ingestion from
  enactment.

---

## How to help

The most valuable contribution is reviving a dead source. Run:

```bash
python3 scripts/check_source_health.py
```

Pick a `SHELL` or `SELECTOR_BROKEN` source, open its URL, find the right CSS
selectors, and fix its parser in `scripts/fetch_scrape.py` (or add selector
overrides once those land). The open [source-coverage issues](https://github.com/Varnasr/PolicyDhara/issues)
list the specific sources that need work. If you find a wrong number on the
dashboard, open an issue. Those reports are the contribution we like most.
