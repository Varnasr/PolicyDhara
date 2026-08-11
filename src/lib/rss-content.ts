/**
 * Generates styled HTML content for RSS <content:encoded> fields.
 * Buttondown (and other RSS-to-email services) use this as the email body.
 */

import type { PolicyItem } from './data';

const SITE_URL = 'https://varnasr.github.io/PolicyDhara';

const TYPE_COLORS: Record<string, { color: string; bg: string }> = {
  legislation:   { color: '#dc2626', bg: '#fef2f2' },
  notification:  { color: '#d97706', bg: '#fffbeb' },
  scheme:        { color: '#16a34a', bg: '#f0fdf4' },
  budget:        { color: '#ea580c', bg: '#fff7ed' },
  research:      { color: '#7c3aed', bg: '#f5f3ff' },
  announcement:  { color: '#2563eb', bg: '#eff6ff' },
  policy:        { color: '#9333ea', bg: '#faf5ff' },
  act:           { color: '#dc2626', bg: '#fef2f2' },
  rules:         { color: '#d97706', bg: '#fffbeb' },
  bill:          { color: '#7c3aed', bg: '#f5f3ff' },
  draft:         { color: '#d97706', bg: '#fffbeb' },
  question:      { color: '#d97706', bg: '#fffbeb' },
  committee_report: { color: '#7c3aed', bg: '#f5f3ff' },
  debate:        { color: '#7c3aed', bg: '#f5f3ff' },
  judgment:      { color: '#dc2626', bg: '#fef2f2' },
  release:       { color: '#64748b', bg: '#f8fafc' },
  report:        { color: '#7c3aed', bg: '#f5f3ff' },
  analysis:      { color: '#7c3aed', bg: '#f5f3ff' },
  longform:      { color: '#7c3aed', bg: '#f5f3ff' },
  news:          { color: '#64748b', bg: '#f8fafc' },
  opinion:       { color: '#64748b', bg: '#f8fafc' },
};

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function getSectorSlug(sector: string): string {
  return sector.toLowerCase().replace(/ & /g, '-').replace(/ /g, '-');
}

/** Render a single policy item as styled HTML for RSS content:encoded */
export function renderPolicyHtml(p: PolicyItem): string {
  const typeKey = (p.type || 'policy').toLowerCase();
  const { color, bg } = TYPE_COLORS[typeKey] ?? { color: '#4a4a48', bg: '#f7f6f3' };
  const typeLabel = escapeHtml(typeKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()));
  const title = escapeHtml(p.title);
  const source = escapeHtml(p.source_short || p.source_name || '');
  const desc = escapeHtml(p.description || '');
  const sectors = p.sectors.map(s =>
    `<a href="${SITE_URL}/sectors/${getSectorSlug(s)}/" style="color:#16a34a;text-decoration:none;font-size:12px;">${escapeHtml(s)}</a>`
  ).join(' &middot; ');

  return `<div style="font-family:-apple-system,'Libre Franklin','Segoe UI',system-ui,sans-serif;max-width:600px;margin:0 auto;color:#1a1a18;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;background:#fffef9;border-radius:10px;overflow:hidden;">
    <tr><td style="padding:24px 28px 20px;border-bottom:2px solid #16a34a;">
      <div style="margin-bottom:10px;">
        <span style="display:inline-block;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:${color};background:${bg};padding:2px 8px;border-radius:3px;">${typeLabel}</span>
        <span style="font-size:12px;color:#a0a09e;margin-left:8px;">${escapeHtml(source)} &middot; ${escapeHtml(p.date)}</span>
      </div>
      <div style="font-family:'Georgia','Newsreader',serif;font-size:18px;font-weight:600;line-height:1.35;color:#1a1a18;letter-spacing:-0.01em;">
        ${p.link ? `<a href="${escapeHtml(p.link)}" style="color:#1a1a18;text-decoration:none;">${title}</a>` : title}
      </div>
    </td></tr>
    ${desc ? `<tr><td style="padding:16px 28px;font-size:14px;line-height:1.55;color:#4a4a48;">
      ${desc}
    </td></tr>` : ''}
    <tr><td style="padding:12px 28px 16px;border-top:1px solid #f0ede6;">
      <div style="margin-bottom:10px;">${sectors}</div>
      <div style="font-size:12px;color:#7a7a78;">
        <a href="${SITE_URL}" style="color:#16a34a;text-decoration:none;font-weight:500;">Browse all policies</a> &nbsp;&middot;&nbsp;
        <a href="${SITE_URL}/digest/" style="color:#16a34a;text-decoration:none;font-weight:500;">Today's digest</a> &nbsp;&middot;&nbsp;
        <a href="${SITE_URL}/rss.xml" style="color:#16a34a;text-decoration:none;font-weight:500;">RSS</a>
      </div>
      <div style="margin-top:10px;font-size:11px;color:#a0a09e;">
        PolicyDhara by <a href="https://impactmojo.in" style="color:#a0a09e;">ImpactMojo</a> — Tracking 300+ official sources across India.
      </div>
    </td></tr>
  </table>
</div>`;
}
