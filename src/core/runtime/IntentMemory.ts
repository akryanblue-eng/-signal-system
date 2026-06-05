import type { PerformanceAction } from './PerformanceAction';
import type { PerformanceState }  from '../PerformanceState';
import type { Style }             from './Style';

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
  score:        number;   // [0, 1] — auto-computed outcome quality (scoreOutcome)
  rating?:      number;   // [-1, 1] — explicit user feedback (overrides score in queries)
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

  /**
   * Build and store a memory from runtime snapshot data.
   * Pass `score` to override the auto-computed scoreOutcome() — used by
   * PerformanceRuntime to supply a policy-aware score instead.
   */
  record(
    intent:  string,
    actions: PerformanceAction[],
    before:  PerformanceState,
    after:   PerformanceState,
    rating?: number,
    score?:  number,
  ): IntentMemory {
    const memory: IntentMemory = {
      intent,
      embeddingKey: normalizeIntentKey(intent),
      actions:      [...actions],
      before,
      after,
      delta:        computeDelta(before, after),
      score:        score ?? scoreOutcome(after),
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

// ─── Outcome scoring ───────────────────────────────────────────────────────────

const clamp01 = (v: number): number => Math.max(0, Math.min(1, v));

/**
 * Heuristic quality signal for a post-intent state.
 * "Good performance" = coherent but alive:
 *   groove (0.5 weight)  — rhythmic lock
 *   stability (0.3)      — system under control
 *   chaos near 0.4 (0.2) — some texture, not runaway
 */
export function scoreOutcome(state: PerformanceState): number {
  return clamp01(
    state.groove    * 0.5 +
    state.stability * 0.3 +
    (1 - Math.abs(state.chaos - 0.4)) * 0.2,
  );
}

// ─── Learned style derivation ──────────────────────────────────────────────────

/**
 * Derive a Style vector from recent memory by computing the score-weighted
 * average of action feature contributions.
 *
 * High-score memories bias the style toward "what worked":
 *   chaos-heavy patterns   → raises aggression
 *   stable/groove patterns → raises precision + grooveBias
 *
 * Returns `NEUTRAL_STYLE` when there are no scored memories.
 */
export function deriveStyle(memories: IntentMemory[]): Style {
  const NEUTRAL: Style = { name: 'learned', aggression: 1.0, precision: 0.7, grooveBias: 1.0 };

  const rated = memories.filter(m => m.score > 0);
  if (rated.length === 0) return NEUTRAL;

  let totalWeight = 0;
  let agg         = 0;
  let prec        = 0;
  let groove      = 0;

  for (const mem of rated) {
    const w = mem.score;
    totalWeight += w;

    for (const a of mem.actions) {
      if (a.type === 'CHAOS_SPIKE')    agg   += a.amount * w;
      if (a.type === 'DRIFT_INJECTION') agg  += a.amount * 0.5 * w;
      if (a.type === 'TENSION_BUILD')  agg   += a.amount * 0.3 * w;
      if (a.type === 'GROOVE_LOCK')    groove += 0.2 * w;
      if (a.type === 'STABILITY_RESTORE') prec += a.amount * w;
      if (a.type === 'ENERGY_PULSE')   prec   += a.amount * 0.5 * w;
    }
  }

  const safe = (v: number): number => v / totalWeight;

  return {
    name:       'learned',
    aggression: clamp01(0.5 + safe(agg)),
    precision:  clamp01(0.3 + safe(prec)),
    grooveBias: clamp01(0.5 + safe(groove)),
  };
}

/**
 * Exponential moving average for style vectors — prevents personality flicker.
 * alpha = 0.1 (default) means ~10% toward new style per call.
 */
export function smoothStyle(prev: Style, next: Style, alpha = 0.1): Style {
  const lerp = (a: number, b: number): number => a + (b - a) * alpha;
  return {
    name:       next.name,
    aggression: lerp(prev.aggression, next.aggression),
    precision:  lerp(prev.precision,  next.precision),
    grooveBias: lerp(prev.grooveBias, next.grooveBias),
  };
}
