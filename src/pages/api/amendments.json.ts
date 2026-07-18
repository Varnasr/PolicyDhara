import type { APIRoute } from 'astro';
import { getAmendments } from '../../lib/data';

// Change-history feed for My Tracker: the bookmarks page fetches this
// client-side and diffs it against each visitor's last-visit timestamp to
// show what changed among the policies they follow.
export const GET: APIRoute = () => {
  const amendments = getAmendments();
  return new Response(
    JSON.stringify({
      meta: {
        version: '1.0',
        attribution: 'PolicyDhara by ImpactMojo (https://varnasr.github.io/PolicyDhara)',
      },
      amendments,
    }),
    {
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, max-age=3600',
      },
    },
  );
};
