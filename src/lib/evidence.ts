/**
 * Evidence cases: Indian interventions with a published evaluation.
 * Read from data/evidence.json at build time. scripts/check_evidence.py
 * holds the shape of that file, so pages can rely on every field below.
 */

import fs from 'node:fs';
import path from 'node:path';

export type Verdict = 'worked' | 'did-not-work' | 'mixed';
export type Design = 'rct' | 'quasi-experimental' | 'observational' | 'other';

export interface EvidenceEffect {
  outcome: string;
  result: string;
  interval_or_se: string | null;
  quote: string;
  page_or_section: string;
}

export interface EvidenceSource {
  citation: string;
  url: string;
  kind: 'journal' | 'working-paper' | 'government' | 'other';
}

export interface EvidenceCase {
  id: string;
  title: string;
  area: string;
  geography: { level: 'national' | 'state' | 'district'; states: string[] };
  period: string;
  intervention: string;
  verdict: Verdict;
  verdict_basis: string;
  design: Design;
  design_detail: string;
  sample: string;
  effects: EvidenceEffect[];
  caveats: string[];
  sources: EvidenceSource[];
  verified_on: string;
}

export const VERDICT_LABELS: Record<Verdict, string> = {
  worked: 'Worked',
  'did-not-work': 'Did not work',
  mixed: 'Mixed',
};

export const DESIGN_LABELS: Record<Design, string> = {
  rct: 'Randomised trial',
  'quasi-experimental': 'Quasi-experimental',
  observational: 'Observational',
  other: 'Other design',
};

/** What each verdict means. Shown on the page, so a reader can judge the label. */
export const VERDICT_RULES: Record<Verdict, string> = {
  worked: 'The main study found a statistically significant improvement in the outcome the intervention targeted.',
  'did-not-work': 'The main study found no significant improvement in the targeted outcome, or found harm.',
  mixed: 'The study found improvement on some targeted outcomes but not others, or the effect depended on conditions.',
};

let cache: EvidenceCase[] | null = null;

export function getAllEvidence(): EvidenceCase[] {
  if (cache) return cache;
  const file = path.join(process.cwd(), 'data', 'evidence.json');
  const raw = JSON.parse(fs.readFileSync(file, 'utf-8'));
  cache = (raw.cases as EvidenceCase[]).slice().sort((a, b) => a.title.localeCompare(b.title));
  return cache;
}

export function getEvidenceById(id: string): EvidenceCase | undefined {
  return getAllEvidence().find(c => c.id === id);
}
