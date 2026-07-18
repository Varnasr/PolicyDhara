# PolicyDhara Roadmap

A living list of what's next. PolicyDhara aggregates Indian development
policy from official sources every six hours. This roadmap is public so
contributors can pick something up — see [CONTRIBUTING](#how-to-help) at the
bottom.

Status legend: 🟢 done · 🟡 in progress · ⚪ planned

---

## Recently shipped 🟢

- **Parallel fetch.** Sources fetch concurrently, so all are reached inside the
  time budget instead of ~40. Dataset grew 406 → 1,727 items.
- **News filter + cap.** Spectacle blocklist (crime/sport/celebrity), source
  gating fixes, and a hard 40% cap on media items. News share 87% → 21%.
- **Policy-forward homepage ranking.** Official policy leads and dominates;
  news is interleaved; operational chaff (auctions, workshops, exam results)
  sinks below the feed.
- **Charts are policy-only.** Every graph, ticker, and stat now counts policy
  items (`level != media`), so the visualisations stop being skewed by news.
- **Government-era normalisation.** The UPA-vs-NDA comparison is reframed as
  per-month rates with a partial-window flag and de-emphasised, so a documented
  collection artefact stops reading as a real policy gap.
- **Historical backfill (1991–2014).** 181 Central Acts pulled from India Code
  by enactment year (RTI, NREGA, RTE, Food Security, …) fill the older-era
  coverage hole authoritatively.
- **RBI notifications scraper.** The master circulars/directions list now
  returns dated items.
- **Source health, honest.** The weekly probe runs the real fetcher and buckets
  every source `WORKS / REDUNDANT / SELECTOR_BROKEN / SHELL / DEAD`. Direct
  ministry sites whose releases already arrive via PIB are marked `REDUNDANT`
  (no data lost), not "broken".
- **Scraper cleanup.** SEBI and ADB revived via correct RSS; 26 truly-dead /
  redundant / news sources removed; a lenient `lxml` fallback keeps malformed
  feeds parsing.
- **Package filter parity.** `pip install policydhara` now filters news the
  same way the live pipeline does.
- **Astro 7**, formal typography (Libre Franklin + Newsreader), and a
  mobile-responsiveness pass.

---

## Next: source coverage ⚪

A triage of all sources (latest local probe):

| Bucket | Count | Meaning | Fix |
|---|---|---|---|
| `WORKS` | ~195 | returns content | — |
| `REDUNDANT` | ~27 | ministry site duplicated by its PIB feed | none — no data lost |
| `SHELL` | ~105 | JS-rendered / empty page | needs a headless fetch path |
| `DEAD` | ~24 | unreachable / TLS / 404 | CI re-probes; prune if confirmed |

The honest finding: most "broken" sources are **not** losing us policy. The
biggest genuine lever left is the `SHELL` bucket — JS-rendered government SPAs
(NITI Aayog, Parliament bills, several regulators) that a plain HTTP fetch can't
read.

- ⚪ **Headless fetch path** for `SHELL` sources — render JS with the
  pre-installed Chromium, then parse. This is the real unlock, tracked as a
  GitHub issue.
- ⚪ **Per-source CSS-selector overrides** in `feeds.json` (`row_selector` /
  `title_selector` / `date_selector`) so one pattern revives many sources.
- ⚪ **Let CI prune the `DEAD` set.** Several gov gazette/regulator sources
  (e-Gazette, TRAI, CCI, Parliament) fail only from a sandboxed network; the
  weekly CI probe judges them from a clean network and the board flags the rest.

## Data quality ⚪

- ⚪ De-duplicate near-identical policies across sources more aggressively.
- ⚪ Backfill publication dates where a source buries them in the page body.
- ⚪ Confidence/provenance flag per item (official vs media vs research).

## Features ⚪

- 🟢 **Source-health page** — the `WORKS / REDUNDANT / SHELL / DEAD` buckets are
  live on `/sources`, with a "covered by PIB" badge so coverage is transparent.
- ⚪ Per-policy social share cards (OG images).
- ⚪ Saved searches / email alerts per keyword (sector alerts already exist).
- ⚪ Diff view on the policy detail page (amendment history is tracked).

## Performance / tech ⚪

- ⚪ Build time grows with the dataset (~2.5 min at 1,727 items). Investigate
  content-collection build cost and paginate the JSON API (`policies.json`
  is served whole at ~1.3 MB).
- ⚪ **Consolidate the two codebases.** `scripts/` (the live pipeline) and the
  `policydhara/` package duplicate fetch + sector logic. Only the relevance
  filter is currently shared. Merging them removes a whole class of drift
  (see the April date-fallback regression in the blog).

## Writing ⚪

Blog posts we want to write (the codebase keeps generating good material):

- ⚪ "What breaks when you scrape the Indian government" — the
  `SELECTOR_BROKEN` / `SHELL` / `DEAD` taxonomy, with examples.
- ⚪ "What counts as a policy?" — designing a relevance filter for a firehose.
- ⚪ "The 40% rule" — keeping a policy tracker from becoming a news reader.
- ⚪ "`first_seen` vs `date`" — why civic dashboards must separate ingestion
  from enactment.

---

## How to help

The highest-value contribution is reviving a dead source. Run:

```bash
python3 scripts/check_source_health.py
```

Pick a `SHELL` or `SELECTOR_BROKEN` source, open its URL, find the right CSS
selectors, and fix its parser in `scripts/fetch_scrape.py` (or add selector
overrides once those land). The open [source-coverage issues](https://github.com/Varnasr/PolicyDhara/issues)
list the specific sources that need work. Found a wrong number on the
dashboard? Open an issue — that's the contribution we like most.
