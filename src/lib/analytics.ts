/**
 * Policy Intelligence Engine
 *
 * Computes real analytical insights from policy data:
 * - Sector momentum (acceleration / deceleration)
 * - Weekly anomaly detection (z-score)
 * - Cross-sector correlation (co-occurrence patterns)
 * - Policy concentration risk (Herfindahl index)
 * - Emerging vs declining sectors
 * - Source diversity scoring
 * - Legislative pipeline signals
 *
 * Time-based metrics use `first_seen` (when PolicyDhara ingested the
 * item) as the time signal, falling back to `date` (issuance date) when
 * present. Most sources don't expose a real publication date so `date`
 * is empty for the majority of items — see scripts/migrate_dates.py
 * for the rationale.
 */

import { getPolicyItems, type PolicyItem } from './data';

const DAY_MS = 86_400_000;

// ── Helpers ──────────────────────────────────────────────

function daysAgo(n: number): Date {
  return new Date(Date.now() - n * DAY_MS);
}

/** Effective time signal for analytics — see file header. */
function policyTime(p: PolicyItem): number | null {
  const ref = p.first_seen || p.date;
  if (!ref) return null;
  const t = new Date(ref).getTime();
  return Number.isNaN(t) ? null : t;
}

function inRange(p: PolicyItem, start: Date, end: Date): boolean {
  const t = policyTime(p);
  if (t === null) return false;
  return t >= start.getTime() && t <= end.getTime();
}

function mean(arr: number[]): number {
  if (!arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function stddev(arr: number[]): number {
  if (arr.length < 2) return 0;
  const m = mean(arr);
  return Math.sqrt(arr.reduce((sum, v) => sum + (v - m) ** 2, 0) / (arr.length - 1));
}

// ── Sector Momentum ─────────────────────────────────────

export interface SectorMomentum {
  sector: string;
  last7: number;
  last30: number;
  prev30: number;       // 30-60 days ago
  velocity: number;     // last30 / prev30 ratio (>1 = accelerating)
  trend: 'surging' | 'rising' | 'stable' | 'cooling' | 'declining';
  signal: string;       // human-readable signal
}

export function getSectorMomentum(): SectorMomentum[] {
  const all = getPolicyItems();
  const now = new Date();
  const d7 = daysAgo(7);
  const d30 = daysAgo(30);
  const d60 = daysAgo(60);

  const sectors = new Set<string>();
  for (const p of all) p.sectors.forEach(s => sectors.add(s));

  const results: SectorMomentum[] = [];

  for (const sector of sectors) {
    const sectorPolicies = all.filter(p => p.sectors.includes(sector));
    const last7 = sectorPolicies.filter(p => inRange(p, d7, now)).length;
    const last30 = sectorPolicies.filter(p => inRange(p, d30, now)).length;
    const prev30 = sectorPolicies.filter(p => inRange(p, d60, d30)).length;

    const velocity = prev30 > 0 ? last30 / prev30 : last30 > 0 ? 2.0 : 1.0;

    let trend: SectorMomentum['trend'];
    if (velocity >= 2.0) trend = 'surging';
    else if (velocity >= 1.3) trend = 'rising';
    else if (velocity >= 0.7) trend = 'stable';
    else if (velocity >= 0.4) trend = 'cooling';
    else trend = 'declining';

    let signal: string;
    if (trend === 'surging') signal = `${sector} activity surged ${Math.round((velocity - 1) * 100)}% vs prior period`;
    else if (trend === 'rising') signal = `${sector} seeing increased policy attention`;
    else if (trend === 'cooling') signal = `${sector} activity slowing — down ${Math.round((1 - velocity) * 100)}%`;
    else if (trend === 'declining') signal = `${sector} policy output dropped significantly`;
    else signal = `${sector} activity steady`;

    results.push({ sector, last7, last30, prev30, velocity, trend, signal });
  }

  return results.sort((a, b) => b.velocity - a.velocity);
}

// ── Weekly Anomaly Detection ────────────────────────────

export interface WeeklyAnomaly {
  week: string;
  count: number;
  zScore: number;
  isAnomaly: boolean;
  direction: 'high' | 'low' | 'normal';
}

export function getWeeklyAnomalies(): WeeklyAnomaly[] {
  const all = getPolicyItems();

  // Bucket by ISO week using first_seen (or date as fallback)
  const weekly: Record<string, number> = {};
  for (const p of all) {
    const t = policyTime(p);
    if (t === null) continue;
    const d = new Date(t);
    const year = d.getFullYear();
    const jan1 = new Date(year, 0, 1);
    const weekNum = Math.ceil(((d.getTime() - jan1.getTime()) / DAY_MS + jan1.getDay() + 1) / 7);
    const key = `${year}-W${String(weekNum).padStart(2, '0')}`;
    weekly[key] = (weekly[key] || 0) + 1;
  }

  const weeks = Object.entries(weekly).sort(([a], [b]) => a.localeCompare(b));
  const counts = weeks.map(([, c]) => c);
  const m = mean(counts);
  const sd = stddev(counts);

  return weeks.map(([week, count]) => {
    const zScore = sd > 0 ? (count - m) / sd : 0;
    const isAnomaly = Math.abs(zScore) > 1.5;
    const direction = zScore > 1.5 ? 'high' : zScore < -1.5 ? 'low' : 'normal';
    return { week, count, zScore: Math.round(zScore * 100) / 100, isAnomaly, direction };
  });
}

// ── Cross-Sector Correlation ────────────────────────────

export interface SectorCorrelation {
  sectorA: string;
  sectorB: string;
  coOccurrence: number;  // # policies tagged with both
  strength: number;      // Jaccard similarity
  label: string;
}

export function getCrossSectorCorrelations(minStrength = 0.15): SectorCorrelation[] {
  const all = getPolicyItems();
  const sectorPolicies: Record<string, Set<string>> = {};

  for (const p of all) {
    for (const s of p.sectors) {
      if (!sectorPolicies[s]) sectorPolicies[s] = new Set();
      sectorPolicies[s].add(p.id);
    }
  }

  const sectors = Object.keys(sectorPolicies);
  const results: SectorCorrelation[] = [];

  for (let i = 0; i < sectors.length; i++) {
    for (let j = i + 1; j < sectors.length; j++) {
      const a = sectorPolicies[sectors[i]];
      const b = sectorPolicies[sectors[j]];
      const intersection = [...a].filter(id => b.has(id)).length;
      if (intersection === 0) continue;
      const union = new Set([...a, ...b]).size;
      const strength = union > 0 ? intersection / union : 0;

      if (strength >= minStrength) {
        results.push({
          sectorA: sectors[i],
          sectorB: sectors[j],
          coOccurrence: intersection,
          strength: Math.round(strength * 100) / 100,
          label: strength >= 0.4 ? 'strong' : strength >= 0.25 ? 'moderate' : 'weak',
        });
      }
    }
  }

  return results.sort((a, b) => b.strength - a.strength);
}

// ── Policy Concentration (Herfindahl Index) ─────────────

export interface ConcentrationAnalysis {
  hhi: number;             // 0-10000: <1500 diverse, 1500-2500 moderate, >2500 concentrated
  label: string;
  topSectorShare: number;  // % share of largest sector
  topSector: string;
  interpretation: string;
}

export function getPolicyConcentration(): ConcentrationAnalysis {
  const all = getPolicyItems();
  const sectorCounts: Record<string, number> = {};
  let totalTags = 0;

  for (const p of all) {
    for (const s of p.sectors) {
      sectorCounts[s] = (sectorCounts[s] || 0) + 1;
      totalTags++;
    }
  }

  if (totalTags === 0) {
    return { hhi: 0, label: 'no data', topSectorShare: 0, topSector: '-', interpretation: 'No policies tracked yet' };
  }

  const shares = Object.values(sectorCounts).map(c => (c / totalTags) * 100);
  const hhi = Math.round(shares.reduce((sum, s) => sum + s * s, 0));

  const sorted = Object.entries(sectorCounts).sort(([, a], [, b]) => b - a);
  const topSector = sorted[0][0];
  const topSectorShare = Math.round((sorted[0][1] / totalTags) * 100);

  let label: string;
  let interpretation: string;
  if (hhi < 1500) {
    label = 'diverse';
    interpretation = 'Policy attention is spread broadly across sectors — no single area dominates';
  } else if (hhi < 2500) {
    label = 'moderate';
    interpretation = `Policy activity moderately concentrated — ${topSector} leads at ${topSectorShare}%`;
  } else {
    label = 'concentrated';
    interpretation = `Policy attention heavily concentrated in ${topSector} (${topSectorShare}%) — other sectors may be underserved`;
  }

  return { hhi, label, topSectorShare, topSector, interpretation };
}

// ── Source Diversity ────────────────────────────────────

export interface SourceDiversity {
  totalSources: number;
  activeLast30: number;
  dominantSource: string;
  dominantShare: number;
  shannonEntropy: number;  // higher = more diverse
  interpretation: string;
}

export function getSourceDiversity(): SourceDiversity {
  const all = getPolicyItems();
  const d30 = daysAgo(30);
  const now = new Date();

  const sourceCounts: Record<string, number> = {};
  const recentSources = new Set<string>();

  for (const p of all) {
    sourceCounts[p.source_short] = (sourceCounts[p.source_short] || 0) + 1;
    if (inRange(p, d30, now)) recentSources.add(p.source_short);
  }

  const total = all.length || 1;
  const sorted = Object.entries(sourceCounts).sort(([, a], [, b]) => b - a);
  const dominantSource = sorted[0]?.[0] || '-';
  const dominantShare = Math.round((sorted[0]?.[1] || 0) / total * 100);

  // Shannon entropy
  const shannonEntropy = -Object.values(sourceCounts).reduce((sum, c) => {
    const p = c / total;
    return sum + (p > 0 ? p * Math.log2(p) : 0);
  }, 0);

  const maxEntropy = Math.log2(Object.keys(sourceCounts).length || 1);
  const evenness = maxEntropy > 0 ? shannonEntropy / maxEntropy : 0;

  let interpretation: string;
  if (evenness > 0.8) interpretation = 'Excellent source diversity — broad coverage across multiple outlets';
  else if (evenness > 0.6) interpretation = `Good diversity, though ${dominantSource} contributes ${dominantShare}% of coverage`;
  else interpretation = `Source concentration risk — ${dominantSource} accounts for ${dominantShare}% of all policies`;

  return {
    totalSources: Object.keys(sourceCounts).length,
    activeLast30: recentSources.size,
    dominantSource,
    dominantShare,
    shannonEntropy: Math.round(shannonEntropy * 100) / 100,
    interpretation,
  };
}

// ── Legislative Pipeline ────────────────────────────────

export interface LegislativePipeline {
  recentBills: number;
  recentNotifications: number;
  recentSchemes: number;
  billToNotificationRatio: number;
  interpretation: string;
}

export function getLegislativePipeline(): LegislativePipeline {
  const d90 = daysAgo(90);
  const now = new Date();
  const recent = getPolicyItems().filter(p => inRange(p, d90, now));

  const recentBills = recent.filter(p => p.type === 'legislation').length;
  const recentNotifications = recent.filter(p => p.type === 'notification').length;
  const recentSchemes = recent.filter(p => p.type === 'scheme').length;

  const billToNotificationRatio = recentBills > 0
    ? Math.round((recentNotifications / recentBills) * 10) / 10
    : recentNotifications > 0 ? Infinity : 0;

  let interpretation: string;
  if (recentBills > 5 && billToNotificationRatio < 2) {
    interpretation = 'Active legislative session — high bill introduction, notifications following';
  } else if (recentNotifications > recentBills * 3) {
    interpretation = 'Implementation phase — executive notifications outpacing new legislation';
  } else if (recentSchemes > recentBills + recentNotifications) {
    interpretation = 'Scheme-heavy period — government focus on direct benefit programs';
  } else {
    interpretation = `${recentBills} bills, ${recentNotifications} notifications, ${recentSchemes} schemes in last 90 days`;
  }

  return { recentBills, recentNotifications, recentSchemes, billToNotificationRatio, interpretation };
}

// ── Composite Intelligence Brief ────────────────────────

export interface IntelligenceBrief {
  generatedAt: string;
  momentum: SectorMomentum[];
  surgingSectors: SectorMomentum[];
  coolingSectors: SectorMomentum[];
  anomalies: WeeklyAnomaly[];
  recentAnomalies: WeeklyAnomaly[];
  correlations: SectorCorrelation[];
  concentration: ConcentrationAnalysis;
  sourceDiversity: SourceDiversity;
  pipeline: LegislativePipeline;
  headlines: string[];    // top 3-5 narrative headlines
}

export function generateIntelligenceBrief(): IntelligenceBrief {
  const momentum = getSectorMomentum();
  const surgingSectors = momentum.filter(m => m.trend === 'surging' || m.trend === 'rising');
  const coolingSectors = momentum.filter(m => m.trend === 'cooling' || m.trend === 'declining');

  const anomalies = getWeeklyAnomalies();
  const recentAnomalies = anomalies.slice(-8).filter(a => a.isAnomaly);

  const correlations = getCrossSectorCorrelations(0.15);
  const concentration = getPolicyConcentration();
  const sourceDiversity = getSourceDiversity();
  const pipeline = getLegislativePipeline();

  // Detect whether the dataset has enough historical depth to make
  // velocity-style claims. Right after the date migration, prev30 is 0
  // for every sector so every sector reads as "surging" — that's a
  // measurement artefact, not a real signal. Suppress those headlines
  // until the data builds up.
  const totalPrior30 = momentum.reduce((s, m) => s + m.prev30, 0);
  const totalLast30 = momentum.reduce((s, m) => s + m.last30, 0);
  const hasComparablePrior = totalPrior30 > 0 && totalPrior30 >= 0.05 * totalLast30;

  // Generate narrative headlines
  const headlines: string[] = [];

  if (hasComparablePrior && surgingSectors.length > 0) {
    const top = surgingSectors[0];
    headlines.push(`${top.sector} policy activity ${top.trend === 'surging' ? 'surging' : 'rising'} — ${top.last30} updates in 30 days (${Math.round((top.velocity - 1) * 100)}% increase)`);
  }

  if (hasComparablePrior && coolingSectors.length > 0) {
    const top = coolingSectors[0];
    headlines.push(`${top.sector} attention declining — down ${Math.round((1 - top.velocity) * 100)}% from prior period`);
  }

  if (!hasComparablePrior) {
    headlines.push(`Most active sector last 30 days: ${momentum[0]?.sector ?? '—'} (${momentum[0]?.last30 ?? 0} items). "Versus prior period" comparisons will populate after more fetches.`);
  }

  if (pipeline.recentBills > 3) {
    headlines.push(`Legislative push: ${pipeline.recentBills} bills tracked in last 90 days`);
  }

  if (recentAnomalies.length > 0) {
    const highWeeks = recentAnomalies.filter(a => a.direction === 'high');
    if (highWeeks.length > 0) {
      headlines.push(`Unusual policy burst in ${highWeeks[0].week} — ${highWeeks[0].count} items (z-score: ${highWeeks[0].zScore})`);
    }
  }

  if (correlations.length > 0) {
    const top = correlations[0];
    headlines.push(`Strongest policy nexus: ${top.sectorA} + ${top.sectorB} (${Math.round(top.strength * 100)}% overlap)`);
  }

  headlines.push(concentration.interpretation);

  return {
    generatedAt: new Date().toISOString(),
    momentum,
    surgingSectors,
    coolingSectors,
    anomalies,
    recentAnomalies,
    correlations,
    concentration,
    sourceDiversity,
    pipeline,
    headlines: headlines.slice(0, 5),
  };
}
