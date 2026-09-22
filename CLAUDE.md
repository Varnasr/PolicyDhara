# PolicyDhara

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

`sharp` is at 0.35.4, `svgo` at 4.1.0, `js-yaml` at 4.3.2.

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
