# PolicyDhara

Shared engineering standard: @.claude/engineering-standards.md. It applies to all work in this repository. This file adds what is specific to the project, and wins where the two disagree.

Indian government scheme tracker. Astro, static output, 2,424 pages, with a
Pagefind search index built after the pages.

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
2,424, and the presence of the index.

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

Verified before and after on the same machine: 2,424 pages both times, the
Pagefind index built both times, and `npm audit` from 5 vulnerabilities to 0.

`sharp` is at 0.35.5 (from 0.35.4 on 2026-10-19, for the librsvg advisory), `svgo` at 4.1.0, `js-yaml` at 4.3.2.

## Watch out for

- **`npm audit` matters more here than in most repositories**, because Astro
  ships the whole rendering path and this site has 2,424 pages of it. Read the
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
`data/evidence.json` (25 cases on 27 October 2026). Each case carries its study
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

**Add a case only from a source you opened.** All 25 were checked by
downloading the paper or its abstract and matching each quotation to its text. Several rest on something short of the journal
text, and each case names its version in the citation: the working paper for
Balsakhi, Surat, Rajasthan police reform, women's police stations, the Debt
Recovery Tribunals, Gujarat audits, Bihar e-FMS, Hyderabad microfinance and
teacher performance pay; the publisher page for the midday meals quotations;
the Lancet abstract for Janani Suraksha Yojana (the 3ie replication reproduces
the table with unlabelled units, so those figures are not printed). The Chennai
property tax paper (November 2025) is unpublished. Balsakhi year-two effect is
0.27 SD in the 2005 draft and 0.28 in the published paper. The Surat 20 to 30
percent range includes imputed estimates; without imputation it is about 18
percent. The BMJ immunisation abstract swaps the two cost figures; the Results
section is followed. A verdict for the Jaunpur committees (mixed) and the
Chennai paper (worked) are judgement calls: reading the targeted outcome as
school-level involvement makes the first "did not work", and reading the
question as "does outsourcing work" makes the second weaker.
