import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { getAllPolicies } from '../lib/data';
import { renderPolicyHtml } from '../lib/rss-content';

const SITE_URL = 'https://varnasr.github.io/PolicyDhara';

export function GET(context: APIContext) {
  const policies = getAllPolicies();
  const base = (import.meta.env.BASE_URL || '/').replace(/\/?$/, '/');
  const siteRoot = context.site
    ? new URL(base, context.site).toString().replace(/\/$/, '')
    : SITE_URL;

  return rss({
    title: 'PolicyDhara',
    description: 'Auto-updating tracker of Indian development policies across 22 sectors — by ImpactMojo',
    site: siteRoot,
    items: policies.slice(0, 100).map(p => {
      // pubDate prefers issuance date, falls back to ingestion (first_seen),
      // then to today — RSS spec requires a valid date.
      const dateStr = p.date || p.first_seen || new Date().toISOString().slice(0, 10);
      const parsed = new Date(dateStr);
      const pubDate = Number.isNaN(parsed.getTime()) ? new Date() : parsed;
      return {
        title: p.title,
        description: `[${p.sectors.join(', ')}] ${p.description}`,
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
