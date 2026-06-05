import type { PerformanceState } from '../PerformanceState';
import type { IntentMemory }     from './IntentMemory';
import type { Style }            from './Style';

// ─── Types ─────────────────────────────────────────────────────────────────────

export interface ScoringWeights {
  groove:       number; // [0, 1]
  stability:    number; // [0, 1]
  chaosControl: number; // [0, 1] — rewards low chaos
  energy:       number; // [0, 1]
}

export type DriftBias = 'good' | 'bad' | 'neutral';

/**
 * MetaPolicy is the system's LEARNED understanding of what constitutes a
 * good outcome.  It lives in Layer B (learnable evaluation) and NEVER
 * touches Layer A (immutable physics, reducer, constraints).
 *
 * Only the scoring weights change — and only by ±0.01/0.005 per 50 ticks.
 */
export interface MetaPolicy {
  scoringWeights:      ScoringWeights;
  driftInterpretation: { aggression: DriftBias; chaos: DriftBias };
  environmentPreferences: Record<string, number>; // learned fit bias [0.5, 1.5]
}

export interface MetaObservation {
  timestamp:   number;
  environment: string;
  score:       number;      // policy-aware outcome quality
  drift:       number;      // style drift magnitude [0, 1]
  instability: number;      // recent state variance [0, 1]
  intentKey:   string;      // embeddingKey of last intent
}

// ─── Base policy ───────────────────────────────────────────────────────────────

/** Safe initialization — deliberately matches scoreOutcome() distribution. */
export const BASE_META_POLICY: MetaPolicy = {
  scoringWeights: {
    groove:       0.40,
    stability:    0.30,
    chaosControl: 0.20,
    energy:       0.10,
  },
  driftInterpretation: {
    aggression: 'neutral',
    chaos:      'neutral',
  },
  environmentPreferences: {
    cinematic: 1.0,
    precision: 1.0,
    chaosJam:  1.0,
  },
};

// ─── Scoring ───────────────────────────────────────────────────────────────────

const clamp01 = (v: number): number => Math.max(0, Math.min(1, v));

/**
 * Policy-aware outcome score. Unlike scoreOutcome(), the weights here are
 * learned — the system's evolving definition of what "good" means.
 */
export function scoreOutcomeWithPolicy(
  state:  PerformanceState,
  policy: MetaPolicy,
): number {
  const w = policy.scoringWeights;
  return clamp01(
    state.groove    * w.groove +
    state.stability * w.stability +
    state.energy    * w.energy    +
    (1 - state.chaos) * w.chaosControl,
  );
}

/**
 * How well does this policy's predictions agree with actual recorded scores?
 * Returns [0, 1]: 1.0 = perfect predictor.
 */
export function evaluatePolicyPerformance(
  memories: IntentMemory[],
  policy:   MetaPolicy,
): number {
  if (memories.length === 0) return 0.5;
  let total = 0;
  for (const m of memories) {
    const predicted = scoreOutcomeWithPolicy(m.after, policy);
    total += 1 - Math.abs(predicted - m.score);
  }
  return total / memories.length;
}

// ─── Bounded policy update ─────────────────────────────────────────────────────

const WEIGHT_MIN = 0.05;
const WEIGHT_MAX = 0.70;

/**
 * Adjust scoring weights by a small bounded delta based on whether the policy
 * is currently a good predictor of outcomes.  Runs every N ticks, not per frame.
 *
 * delta = +0.01 when reward > 0.7 (policy predicting well → reinforce)
 * delta = −0.005 when reward ≤ 0.7 (diverging → small correction)
 */
export function updateMetaPolicy(
  policy:   MetaPolicy,
  memories: IntentMemory[],
): MetaPolicy {
  const reward = evaluatePolicyPerformance(memories, policy);
  const delta  = reward > 0.7 ? 0.01 : -0.005;
  const w      = policy.scoringWeights;
  const clampW = (v: number): number => Math.max(WEIGHT_MIN, Math.min(WEIGHT_MAX, v));

  return {
    ...policy,
    scoringWeights: {
      groove:       clampW(w.groove       + delta),
      stability:    clampW(w.stability    + delta),
      chaosControl: clampW(w.chaosControl + delta),
      energy:       clampW(w.energy       + delta),
    },
  };
}

// ─── Identity quality ──────────────────────────────────────────────────────────

/**
 * Is the system improving at being itself over time?
 *
 * High quality = high scores + behavioral stability + drift within bounds.
 * Drift < 0.3 is healthy; above that it's penalized.
 */
export function computeIdentityQuality(obs: MetaObservation[]): number {
  if (obs.length === 0) return 0.5;
  const recent = obs.slice(-100);
  let scoreSum     = 0;
  let stabilitySum = 0;
  let driftSum     = 0;
  for (const o of recent) {
    scoreSum     += o.score;
    stabilitySum += 1 - o.instability;
    driftSum     += o.drift;
  }
  const n            = recent.length;
  const avgScore     = scoreSum     / n;
  const avgStability = stabilitySum / n;
  const avgDrift     = driftSum     / n;
  const driftPenalty = Math.max(0, avgDrift - 0.3);
  return clamp01(avgScore * 0.5 + avgStability * 0.3 - driftPenalty * 0.2);
}

// ─── Diagnostic utilities ──────────────────────────────────────────────────────

/** Euclidean distance between two style vectors, capped to [0, 1]. */
export function computeStyleDrift(current: Style, prev: Style): number {
  const da = current.aggression - prev.aggression;
  const dp = current.precision  - prev.precision;
  const dg = current.grooveBias - prev.grooveBias;
  return Math.min(1, Math.sqrt(da * da + dp * dp + dg * dg));
}

/** Average chaos+stability variance across a recent state window. */
export function computeInstability(states: PerformanceState[]): number {
  if (states.length < 2) return 0;
  let sum = 0;
  for (let i = 1; i < states.length; i++) {
    const prev = states[i - 1]!;
    const curr = states[i]!;
    sum += Math.abs(curr.chaos     - prev.chaos);
    sum += Math.abs(curr.stability - prev.stability);
  }
  return Math.min(1, sum / (states.length - 1));
}

// ─── Meta-Observer ─────────────────────────────────────────────────────────────

/**
 * Sits OUTSIDE the runtime loop.  Watches environment switching, style drift,
 * and outcome quality.  Does not emit actions — only answers "is the system
 * becoming better at being itself?"
 */
export class MetaObserver {
  private history: MetaObservation[] = [];

  log(obs: MetaObservation): void {
    this.history.push(obs);
  }

  evaluate(): number {
    return computeIdentityQuality(this.history);
  }

  recent(n = 20): MetaObservation[] {
    return this.history.slice(-n);
  }

  get size(): number {
    return this.history.length;
  }

  clear(): void {
    this.history = [];
  }
}
