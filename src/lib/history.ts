/**
 * Policy History — Constituent Assembly debates loader.
 *
 * Reads the curated dataset in data/constitutional_debates.json, which maps
 * founding debates (1946–1949) to the tracker's sectors. Kept self-contained
 * (own readJson) so it does not depend on src/lib/data.ts.
 */

import fs from 'node:fs';
import path from 'node:path';

const DATA_DIR = path.join(process.cwd(), 'data');

export interface DebatesMetadata {
  description: string;
  source: string;
  curated: boolean;
  period?: string;
  last_reviewed?: string;
}

export interface Debate {
  id: string;
  topic: string;
  /** ISO date: 'YYYY-MM-DD', or 'YYYY-MM' where only the month is certain. */
  date: string;
  /** Constituent Assembly Debates volume, in Roman numerals (e.g. 'VII'). */
  volume: string;
  articles: string[];
  sectors: string[];
  summary: string;
  key_voices: string[];
  legacy: string;
  link: string;
}

export interface ConstitutionalDebatesData {
  metadata: DebatesMetadata;
  debates: Debate[];
}

function readJson<T>(filename: string, fallback: T): T {
  const filepath = path.join(DATA_DIR, filename);
  try {
    const raw = fs.readFileSync(filepath, 'utf-8');
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

const EMPTY: ConstitutionalDebatesData = {
  metadata: {
    description: '',
    source: '',
    curated: true,
  },
  debates: [],
};

/** All curated Constituent Assembly debates, in chronological order. */
export function getConstitutionalDebates(): ConstitutionalDebatesData {
  const data = readJson<ConstitutionalDebatesData>('constitutional_debates.json', EMPTY);
  const debates = (data.debates || [])
    .slice()
    .sort((a, b) => a.date.localeCompare(b.date));
  return { metadata: data.metadata || EMPTY.metadata, debates };
}

/** Debates mapped to a given sector (by display name, e.g. 'Rural Development'). */
export function getDebatesForSector(sectorName: string): Debate[] {
  return getConstitutionalDebates().debates.filter(d =>
    d.sectors.includes(sectorName)
  );
}
