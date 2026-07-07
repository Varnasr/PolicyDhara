import rss from '@astrojs/rss';
import type { APIContext, GetStaticPaths } from 'astro';
import { getAllPolicies, getMeta } from '../../../lib/data';
import { renderPolicyHtml } from '../../../lib/rss-content';
import fs from 'node:fs';
import path from 'node:path';

const SITE_URL = 'https://varnasr.github.io/PolicyDhara';

// Every source_id of the form `pib_<slug>` (excluding regional PIB offices
// which live under `state_pib_*`) is a ministry-filtered listing. This
// generator emits one RSS feed per such ministry, so `/rss/ministry/law-and-justice.xml`
// carries only items whose source_id is `pib_law_and_justice`.
function loadMinistrySources(): Array<{ id: string; slug: string; name: string; short: string }> {
  let feedsConfig: any = { sources: {} };
  try {
    const raw = fs.readFileSync(path.join(process.cwd(), 'feeds.json'), 'utf-8');
    feedsConfig = JSON.parse(raw);
  } catch {
    return [];
  }
  const out: Array<{ id: string; slug: string; name: string; short: string }> = [];
  for (const [id, cfg] of Object.entries<any>(feedsConfig.sources || {})) {
    if (!id.startsWith('pib_')) continue;
    // Only ministry-filtered listings — not the firehose (`pib` doesn't
    // start with `pib_`) and not the state PIB regional offices (they
    // start with `state_pib_`).
    const slug = id.replace(/^pib_/, '').replace(/_/g, '-');
    out.push({
      id,
      slug,
      name: cfg.name || id,
      short: cfg.short_name || id,
    });
  }
  return out;
}

export const getStaticPaths: GetStaticPaths = () => {
  const meta = getMeta();
  const counts = meta.source_counts || {};
  const ministries = loadMinistrySources();

  return ministries
    // Skip ministries that haven't contributed any items yet — an empty
    // RSS feed is worse than a 404 (crawlers treat it as "no news
    // available" and stop polling).
    .filter(m => (counts[m.id] || 0) > 0)
    .map(m => ({
      params: { ministry: m.slug },
      props: { ministry: m },
    }));
};

export function GET(context: APIContext & { props: { ministry: { id: string; name: string; short: string } } }) {
  const { ministry } = context.props;
  const policies = getAllPolicies()
    .filter(p => p.source_id === ministry.id)
    .slice(0, 100);
  const base = (import.meta.env.BASE_URL || '/').replace(/\/?$/, '/');
  const siteRoot = context.site
    ? new URL(base, context.site).toString().replace(/\/$/, '')
    : SITE_URL;

  return rss({
    title: `PolicyDhara — ${ministry.name}`,
    description: `Press releases and notifications from ${ministry.name}, tracked by PolicyDhara.`,
    site: siteRoot,
    items: policies.map(p => {
      const dateStr = p.date || p.first_seen || new Date().toISOString().slice(0, 10);
      const parsed = new Date(dateStr);
      const pubDate = Number.isNaN(parsed.getTime()) ? new Date() : parsed;
      return {
        title: p.title,
        description: p.description,
        link: p.link || `${siteRoot}/policies/${p.id}/`,
        pubDate,
        categories: p.sectors,
        content: renderPolicyHtml(p),
        customData: `<source>${p.source_short}</source><type>${p.type}</type>`,
      };
    }),
    customData: `<language>en-in</language>`,
  });
}
