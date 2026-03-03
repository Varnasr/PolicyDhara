import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { getAllPolicies } from '../lib/data';

export function GET(context: APIContext) {
  const policies = getAllPolicies();

  return rss({
    title: 'India Policy Tracker',
    description: 'Auto-updating tracker of Indian development policies across 22 sectors — by ImpactMojo',
    site: context.site?.toString() || 'https://varnasr.github.io/india-policy-tracker',
    items: policies.slice(0, 100).map(p => ({
      title: p.title,
      description: `[${p.sectors.join(', ')}] ${p.description}`,
      link: p.link || `https://varnasr.github.io/india-policy-tracker/`,
      pubDate: new Date(p.date),
      categories: p.sectors,
      customData: `<source>${p.source_short}</source><type>${p.type}</type>`,
    })),
    customData: `<language>en-in</language>`,
  });
}
