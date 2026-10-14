import type { APIRoute } from 'astro';
import { getAllPolicies, getMeta } from '../../lib/data';

export const GET: APIRoute = () => {
  const policies = getAllPolicies();
  const meta = getMeta();

  return new Response(
    JSON.stringify({
      meta: {
        last_updated: meta.last_updated,
        total: policies.length,
        version: '1.0',
        attribution: 'PolicyDhara by ImpactMojo (https://policydhara.impactmojo.in)',
      },
      policies,
    }, null, 2),
    {
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, max-age=3600',
        'Access-Control-Allow-Origin': '*',
      },
    },
  );
};
