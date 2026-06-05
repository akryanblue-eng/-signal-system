import type { PerformanceAction } from './PerformanceAction';
import type { PerformanceState }  from '../PerformanceState';

// ─── Types ─────────────────────────────────────────────────────────────────────

export interface StateDelta {
  tension: number;
  chaos:   number;
  groove:  number;
  energy:  number;
}

export interface IntentMemory {
  intent:       string;
  embeddingKey: string;
  actions:      PerformanceAction[];
  before:       PerformanceState;
  after:        PerformanceState;
  delta:        StateDelta;
  rating?:      number;   // [-1, 1] — positive = good outcome, negative = bad
  timestamp:    number;
}

// ─── Key normalization ─────────────────────────────────────────────────────────

const KEY_MAP: Array<[RegExp, string]> = [
  [/\b(energy|lift|hype|pump|push)\b/i,       'energy_control'],
  [/\b(groove|rhythm|lock|sync|tight)\b/i,    'rhythm_control'],
  [/\b(chaos|glitch|break|fract|shatter)\b/i, 'entropy_control'],
  [/\b(calm|settle|smooth|quiet|dampen)\b/i,  'stability_control'],
  [/\b(tension|build|pressure|wind|rise)\b/i, 'tension_control'],
];

/** Map a raw intent string to a cluster key without ML cost. */
export function normalizeIntentKey(text: string): string {
  for (const [re, key] of KEY_MAP) {
    if (re.test(text)) return key;
  }
  return 'general_control';
}

// ─── Delta ─────────────────────────────────────────────────────────────────────

export function computeDelta(before: PerformanceState, after: PerformanceState): StateDelta {
  return {
    tension: after.tension - before.tension,
    chaos:   after.chaos   - before.chaos,
    groove:  after.groove  - before.groove,
    energy:  after.energy  - before.energy,
  };
}

// ─── Store ─────────────────────────────────────────────────────────────────────

export class IntentMemoryStore {
  private memories: IntentMemory[] = [];

  add(memory: IntentMemory): void {
    this.memories.push(memory);
  }

  /** Build and store a memory from runtime snapshot data. Returns the stored entry. */
  record(
    intent:  string,
    actions: PerformanceAction[],
    before:  PerformanceState,
    after:   PerformanceState,
    rating?: number,
  ): IntentMemory {
    const memory: IntentMemory = {
      intent,
      embeddingKey: normalizeIntentKey(intent),
      actions:      [...actions],
      before,
      after,
      delta:        computeDelta(before, after),
      rating,
      timestamp:    Date.now(),
    };
    this.memories.push(memory);
    return memory;
  }

  query(key: string): IntentMemory[] {
    return this.memories.filter(m => m.embeddingKey === key);
  }

  recent(n = 20): IntentMemory[] {
    return this.memories.slice(-n);
  }

  /** Return up to n memories for a key, sorted by descending rating. */
  getBestPatterns(key: string, n = 5): IntentMemory[] {
    return this.query(key)
      .filter(m => m.rating !== undefined)
      .sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0))
      .slice(0, n);
  }

  /** Apply a rating to the most recent memory matching this key. */
  rateLast(key: string, rating: number): boolean {
    const last = this.query(key).at(-1);
    if (!last) return false;
    last.rating = rating;
    return true;
  }

  get size(): number {
    return this.memories.length;
  }

  clear(): void {
    this.memories = [];
  }
}

// ─── Semantic embedding ────────────────────────────────────────────────────────

/**
 * Compact [tension, chaos, groove] feature vector for an action sequence.
 * Euclidean distance in this space approximates behavioral similarity.
 */
export function embedActions(actions: PerformanceAction[]): [number, number, number] {
  let tension = 0;
  let chaos   = 0;
  let groove  = 0;

  for (const a of actions) {
    if (a.type === 'TENSION_BUILD')    tension += a.amount;
    if (a.type === 'CHAOS_SPIKE')      chaos   += a.amount;
    if (a.type === 'DRIFT_INJECTION')  chaos   += a.amount * 0.5;
    if (a.type === 'GROOVE_LOCK')      groove  += 0.2;
  }

  return [Math.min(1, tension), Math.min(1, chaos), Math.min(1, groove)];
}

/** Euclidean-distance similarity ∈ (−∞, 1]. Returns 1 for identical vectors. */
export function vectorSimilarity(a: readonly number[], b: readonly number[]): number {
  const dist = Math.sqrt(
    a.reduce((sum, v, i) => sum + (v - (b[i] ?? 0)) ** 2, 0),
  );
  return 1 - dist;
}

// ─── Merge ─────────────────────────────────────────────────────────────────────

/**
 * Merge base + learned action lists.
 * Learned actions take precedence — base is filtered for duplicate types.
 */
export function mergeActions(
  base:    PerformanceAction[],
  learned: PerformanceAction[],
): PerformanceAction[] {
  const learnedTypes = new Set(learned.map(a => a.type));
  return [...learned, ...base.filter(a => !learnedTypes.has(a.type))];
}
