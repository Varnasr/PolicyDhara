# PolicyDhara

Shared engineering standard: @.claude/engineering-standards.md. It applies to all work in this repository. This file adds what is specific to the project, and wins where the two disagree.

Indian government scheme tracker. Astro, static output, 2,459 pages (2,424 plus the 34 evidence cases and
their index), with a Pagefind search index built after the pages.

## Commands

```bash
npm ci
npm run build           # astro build, then pagefind --site dist
npm run fetch           # python3 scripts/fetch_all.py
npm run update          # fetch, then build
npm audit               # load-bearing here, see below
```

## The build has two halves and the second is easy to lose

`npm run build` is `astro build && pagefind --site dist --output-subdir _pagefind`.
Pagefind indexes the **built output**, so anything that changes what Astro emits
changes what is searchable. After a build, `dist/_pagefind` should hold about
sixteen files; an empty or missing one means the site ships with a search box
that finds nothing, and nothing errors.

Check both numbers after any build that matters: the page count, currently
2,459, and the presence of the index.

## The September 2026 dependency upgrade

Astro went 7.2.0 to 7.3.3 because `npm audit` reported **5 vulnerabilities, one
critical**, and none of them was fixable below 7.2.7:

- critical: remote code execution through AVIF image optimisation
  (GHSA-26w7-cxv4-gfx2)
- high: `sharp` inheriting libvips CVE-2026-33327/33328/35590/35591 and the
  libheif advisories
- high: `js-yaml`, where `maxTotalMergeKeys` does not bound CPU use
- high and moderate: `svgo` 4.0.0 to 4.0.2, whose `removeScripts` lets
  executable links through namespace and control-character bypasses

Verified before and after on the same machine: 2,424 pages both times (before the Evidence pages), the
Pagefind index built both times, and `npm audit` from 5 vulnerabilities to 0.

`sharp` is at 0.35.5 (from 0.35.4 on 2026-10-19, for the librsvg advisory), `svgo` at 4.1.0, `js-yaml` at 4.3.2.

## Watch out for

- **`npm audit` matters more here than in most repositories**, because Astro
  ships the whole rendering path and this site has 2,459 pages of it. Read the
  advisory rather than the count: a critical that only affects server-rendered
  output matters less on a prerendered site than a high that affects the build,
  which is why the AVIF one was the reason to move.
- **`scripts/fetch_all.py` is a separate, manual step.** `npm run build` does not
  refresh the data, so a build can succeed and still ship yesterday's figures.
  Use `npm run update` when the point is fresh data.
- **This repository supersedes PolicyStack**, which carries a Retired badge. Work
  belongs here.

## The Evidence pages

`/evidence/` lists Indian interventions with a published evaluation, from
`data/evidence.json` (34 cases on 27 October 2026). Each case carries its study
design, sample, effects, a short quotation for every figure, caveats and the
sources opened. `python3 scripts/check_evidence.py` refuses a case without an
https source, a quotation that contains the figure beside it, or a
verification date, and applies the house writing rules to our own prose
(quotations and citations are printed as the source wrote them).
`tests/test_evidence.py` injects the faults.

**Verdicts follow one rule, shown on the page.** Worked: a significant
improvement in the outcome the intervention targeted. Did not work: no
significant improvement in it, or harm. Mixed: improvement on some targeted
outcomes and not others, or the effect depends on conditions. Janani Suraksha
Yojana is mixed because the Lancet matching result and a replication using
district differences in differences disagree on mortality.

**Add a case only from a source you opened.** All 34 were checked by
downloading the paper or its abstract and matching each quotation to its text. Several rest on something short of the journal
text, and each case names its version in the citation: the working paper for
Balsakhi, Surat, Rajasthan police reform, women's police stations, the Debt
Recovery Tribunals, Gujarat audits, Bihar e-FMS, Hyderabad microfinance and
teacher performance pay; the publisher page for the midday meals quotations;
the Lancet abstract for Janani Suraksha Yojana (the 3ie replication reproduces
the table with unlabelled units, so those figures are not printed; the
facility-birth and neonatal results come from the open first version of
Powell-Jackson, Mazumdar and Mills, 2011). The Chennai
property tax paper (November 2025) is unpublished. The BMJ 2014 paper
evaluates Karnataka's Vajpayee Arogyashree, not Andhra Pradesh's Aarogyasri,
and is filed under that scheme. The health cases added the same day (IMNCI,
ASHA women's groups, IGMSY, PM-JAY, Vajpayee Arogyashree, Chiranjeevi, Kilkari,
Bihar frontline incentives, Mission Indradhanush) were each matched quote by
quote to the opened text. Balsakhi year-two effect is
0.27 SD in the 2005 draft and 0.28 in the published paper. The Surat 20 to 30
percent range includes imputed estimates; without imputation it is about 18
percent. The BMJ immunisation abstract swaps the two cost figures; the Results
section is followed. A verdict for the Jaunpur committees (mixed) and the
Chennai paper (worked) are judgement calls: reading the targeted outcome as
school-level involvement makes the first "did not work", and reading the
question as "does outsourcing work" makes the second weaker.

## Auto-update, and what it cannot cover

The policy feed refreshes every six hours (`update-policies.yml`: fetch, test,
build, a pull request that merges itself, deploy). The weekly source-health PR
used to wait for a person and the board showed a probe 36 days old; it merges
itself now. `freshness.yml` runs weekly, opens or updates one issue labelled
`freshness` when `scripts/check_freshness.py` finds data past its limit (policy
feed 2 days, source health 10, committee reports 14, Parliament sessions 120,
Budget year, hand-curated notes 365, evidence checks 365), and checks every
evidence source link (`scripts/check_evidence_links.py`; only 404 and 410 fail,
because publishers block robots). The Parliament, Budget, impact and state
datasets and the evidence cases are curated by hand because an unattended
script would publish unchecked figures; the freshness issue says when each is
due. `tests/test_claims.py` fails when a count of sources in the documents
differs from `feeds.json`; the About page and the page descriptions compute
their counts from the data.

## Browse reads every document

`/policies/` renders 30 cards and loads `/api/browse.json` (every document,
compact fields, in the default order) so kind, type, sector, source, date,
order, search and the CSV and JSON exports cover the whole archive. Before
2026-10-27 the page held only the newest 1,050 documents, so a sector or date
filter silently ignored the rest, and the export said it covered "all matches"
and did not. Client-drawn cards mirror `PolicyCard.astro`; change one and
change the other. The bookmark handler in `Base.astro` binds the buttons present
at load, so the Browse page binds its own by delegation.

## Writing check

`scripts/check_copy.py` is a ratchet over the prose a reader sees (pages,
posts, string literals in `src/lib`, the root documents): no em dash, no
banned word, no "not X but Y", no emoji. The baseline is empty. The page formerly named
"Policy Landscape" is "Policy Map" (the owner's choice, 27 October 2026); its URL
is still `/landscape/` so links keep working. A count that rises or falls fails; `--update` lowers it and
refuses to raise it. Policy records are not ours and are not read.

## Colour: ink and fill are different tokens

`--color-accent` is a link colour in the light theme and a pale blue in the
dark one, so white text on it measured 2.14:1. `--color-accent-fill` carries
white text in both themes and does not change. `--ink-good`, `--ink-bad`,
`--ink-warn`, `--ink-slate` and `--ink-teal` are the text colours for
status words and flip with the theme; `--type-*` are fills and tints, and a
badge's text is `color-mix` of the type colour into `--color-text`. Heat-map
cells use `src/lib/heat.ts`, opaque fills in two bands (dark text on a tint,
white on a deep blue), measured at 6.7:1 or better in both themes. An axe run
over 34 page types at 390x844 and 1280x900 in both themes found 157 distinct
failing selectors at the start of the 27 October 2026 pass. The last full run
showed one (a link in the sources page explainer); it was fixed and the pages
that share the rule were rechecked clean, but no full run followed it. The
audit script lived in the session scratchpad, so rerun axe over a changed page
rather than trusting this paragraph.
