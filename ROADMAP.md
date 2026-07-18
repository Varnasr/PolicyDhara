# PolicyDhara Roadmap

A living list of what's next. PolicyDhara aggregates Indian development
policy from official sources every six hours. This roadmap is public so
contributors can pick something up — see [CONTRIBUTING](#how-to-help) at the
bottom.

Status legend: 🟢 done · 🟡 in progress · ⚪ planned

---

## Recently shipped 🟢

- **Parallel fetch.** Sources fetch concurrently, so all ~377 are reached
  inside the time budget instead of ~40. Dataset grew 406 → 1,727 items.
- **News filter + cap.** Spectacle blocklist (crime/sport/celebrity), source
  gating fixes, and a hard 40% cap on media items. News share 87% → 21%.
- **Policy-forward homepage ranking.** Official policy leads and dominates;
  news is interleaved; operational chaff (auctions, workshops, exam results)
  sinks below the feed.
- **RBI notifications scraper.** The master circulars/directions list now
  returns dated items.
- **Source health, upgraded.** The weekly probe now runs the real fetcher and
  buckets every source `WORKS / SELECTOR_BROKEN / SHELL / DEAD`.
- **Package filter parity.** `pip install policydhara` now filters news the
  same way the live pipeline does.
- **Astro 7.**

---

## Next: source coverage ⚪

The single biggest lever on data quality. A triage of all sources found:

| Bucket | Count | Meaning | Fix |
|---|---|---|---|
| `WORKS` | ~196 | returns content | — |
| `SELECTOR_BROKEN` | ~120 | page loads, parser extracts nothing | update selectors |
| `SHELL` | ~51 | JS-rendered / empty page | find an RSS or API source |
| `DEAD` | ~55 | unreachable / TLS / 404 | fix URL or remove |

- ⚪ **Per-source CSS-selector overrides.** Add optional `row_selector` /
  `title_selector` / `date_selector` fields to `feeds.json` so one fix
  pattern revives many `SELECTOR_BROKEN` sources without new code.
- ⚪ **Revive high-value scrapers first:** e-Gazette, major ministries, and
  regulators (the ones a policy tracker most needs).
- ⚪ **Find RSS/API alternatives** for the `SHELL` (JS-rendered) sources.
- ⚪ **Prune or repoint** the `DEAD` sources; the health board makes this a
  one-glance decision.

## Data quality ⚪

- ⚪ De-duplicate near-identical policies across sources more aggressively.
- ⚪ Backfill publication dates where a source buries them in the page body.
- ⚪ Confidence/provenance flag per item (official vs media vs research).

## Features ⚪

- 🟡 **Source-health page** — surface the `WORKS/BROKEN/SHELL/DEAD` buckets on
  the site so coverage is transparent and contributors can help.
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

Pick a `SELECTOR_BROKEN` source, open its URL, find the right CSS selectors,
and fix its parser in `scripts/fetch_scrape.py` (or add selector overrides
once those land). PRs welcome. Found a wrong number on the dashboard? Open an
issue — that's the contribution we like most.
