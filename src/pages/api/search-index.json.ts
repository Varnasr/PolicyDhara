import type { APIRoute } from 'astro';
import { getAllPolicies, getMeta } from '../../lib/data';

/**
 * Compact client-side index: the fields the fast-filter search, alerts
 * preview, and bookmarks tracker need — a fraction of the size of the full
 * policies.json, and fetched on demand instead of being inlined into page
 * HTML (the /search/ and /api/ pages used to ship the whole corpus inside
 * their markup on every visit).
 */
export const GET: APIRoute = () => {
  const index = getAllPolicies().map(p => ({
    id: p.id,
    t: p.title,
    d: p.description,
    dt: p.date,
    src: p.source_short,
    sec: p.sectors,
    ty: p.type,
    lk: p.link,
  }));

  return new Response(
    JSON.stringify({ last_updated: getMeta().last_updated, index }),
    { headers: { 'Content-Type': 'application/json; charset=utf-8' } },
  );
};
