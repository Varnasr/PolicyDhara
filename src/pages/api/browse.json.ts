import type { APIRoute } from 'astro';
import { getAllPolicies, getKind, getPriority, getImpactForPolicy } from '../../lib/data';
import type { Kind } from '../../lib/data';

/**
 * The compact index the Browse page filters in the browser. Every document is
 * here, so a filter covers the whole archive and not only the cards the page
 * renders. Records are in the page's default order (policy documents first,
 * then in the making, analysis, announcements and news, newest first inside
 * each kind), so the array position is the "recommended" ranking.
 * Fields: i id, t title, d date, k kind, y type, s source, c sectors,
 * x description (cut to 300 characters), p priority if not normal,
 * m impact [score, beneficiaries, implementation] if the policy has one.
 */
const KIND_ORDER: Kind[] = ['instrument', 'process', 'analysis', 'announcement', 'news'];

export const GET: APIRoute = () => {
  const rank = (k: Kind) => KIND_ORDER.indexOf(k);
  const rows = getAllPolicies()
    .map(p => ({ p, k: getKind(p) }))
    .sort((a, b) => rank(a.k) - rank(b.k) || (b.p.date || '').localeCompare(a.p.date || ''))
    .map(({ p, k }) => {
      const row: Record<string, unknown> = {
        i: p.id,
        t: p.title,
        d: p.date || '',
        k,
        y: p.type,
        s: p.source_short,
        c: p.sectors,
        x: (p.description || '').slice(0, 300),
      };
      const priority = getPriority(p);
      if (priority !== 'normal') row.p = priority;
      const impact = getImpactForPolicy(p.title);
      if (impact) row.m = [impact.impact_score, impact.beneficiaries, impact.implementation];
      return row;
    });

  return new Response(JSON.stringify(rows), {
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};
