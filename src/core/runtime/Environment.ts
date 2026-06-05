import type { Style }           from './Style';
import type { StyleBounds }     from './Constraints';
import type { PerformanceState } from '../PerformanceState';
import type { IntentMemory }    from './IntentMemory';

// ─── Types ─────────────────────────────────────────────────────────────────────

/**
 * Per-environment multipliers that amplify or dampen the learned Style vector
 * before it reaches applyStyle().  Keeps the type system clean — bias is
 * folded into the Style copy rather than threading a new param through compilers.
 */
export interface CompilerBias {
  chaosWeight:     number; // multiplies aggression
  grooveWeight:    number; // multiplies grooveBias
  stabilityWeight: number; // multiplies precision
}

/**
 * A mode capsule: base style + constraint envelope + compiler bias.
 * Same EventBus, same State, same Memory — different behavioral physics.
 */
export interface StyleEnvironment {
  name:         string;
  style:        Style;
  constraints:  StyleBounds;
  compilerBias: CompilerBias;
}

// ─── Prebuilt environments ─────────────────────────────────────────────────────

export const ENVIRONMENTS = {
  cinematic: {
    name:  'cinematic',
    style: { name: 'cinematic', aggression: 0.6, precision: 0.9, grooveBias: 1.2 },
    constraints: {
      aggression: { min: 0.3, max: 0.8 },
      precision:  { min: 0.5, max: 1.0 },
      grooveBias: { min: 0.6, max: 1.8 },
    },
    compilerBias: { chaosWeight: 0.6, grooveWeight: 1.2, stabilityWeight: 1.4 },
  },
  precision: {
    name:  'precision',
    style: { name: 'precision', aggression: 0.3, precision: 1.0, grooveBias: 1.5 },
    constraints: {
      aggression: { min: 0.1, max: 0.5 },
      precision:  { min: 0.7, max: 1.0 },
      grooveBias: { min: 0.8, max: 1.8 },
    },
    compilerBias: { chaosWeight: 0.2, grooveWeight: 0.8, stabilityWeight: 1.8 },
  },
  chaosJam: {
    name:  'chaosJam',
    style: { name: 'chaosJam', aggression: 1.4, precision: 0.4, grooveBias: 0.7 },
    constraints: {
      aggression: { min: 0.8, max: 1.6 },
      precision:  { min: 0.2, max: 0.6 },
      grooveBias: { min: 0.3, max: 1.0 },
    },
    compilerBias: { chaosWeight: 1.6, grooveWeight: 0.6, stabilityWeight: 0.4 },
  },
} satisfies Record<string, StyleEnvironment>;

// ─── Bias merge ────────────────────────────────────────────────────────────────

/**
 * Fold compiler bias into a Style copy so applyStyle() can carry
 * the environment's intent without a separate code path.
 */
export function mergeStyleWithBias(style: Style, bias: CompilerBias): Style {
  return {
    name:       style.name,
    aggression: style.aggression * bias.chaosWeight,
    precision:  style.precision  * bias.stabilityWeight,
    grooveBias: style.grooveBias * bias.grooveWeight,
  };
}

// ─── Memory-weighted environment detection ─────────────────────────────────────

/**
 * Recency-weighted average score of memories tagged with envName.
 * Exponential decay with half-life ≈ 35 ticks (exp(-age/50)).
 * Returns 0.5 (neutral) when no tagged memories exist.
 */
export function scoreEnvironmentFromMemory(
  envName:  string,
  memories: IntentMemory[],
): number {
  const envMems = memories.filter(m => m.environment === envName);
  if (envMems.length === 0) return 0.5;

  let weightedScore = 0;
  let totalWeight   = 0;
  const n = envMems.length;
  for (let i = 0; i < n; i++) {
    const age       = n - 1 - i;           // 0 = most recent
    const w         = Math.exp(-age / 50);
    weightedScore  += envMems[i]!.score * w;
    totalWeight    += w;
  }
  return totalWeight > 0 ? weightedScore / totalWeight : 0.5;
}

/**
 * Soft state-match score [0, 1] for a candidate environment.
 * Replaces hard-threshold rules with graduated signals so memory evidence
 * can override state bias once enough history exists.
 */
function stateAffinity(
  state:          PerformanceState,
  env:            StyleEnvironment,
  entropyCount:   number,
  precisionCount: number,
): number {
  if (env.name === 'chaosJam') {
    const chaosSignal  = Math.max(0, (state.chaos - 0.5) * 2);
    const driftSignal  = Math.max(0, (state.drift - 0.3) * 1.43);
    const intentSignal = entropyCount >= 3 ? 0.6 : 0;
    return Math.min(1, Math.max(chaosSignal, driftSignal, intentSignal));
  }
  if (env.name === 'precision') {
    const stabilitySignal = Math.max(0, (state.stability - 0.6) * 2.5);
    const chaosOk         = Math.max(0, (0.5 - state.chaos) * 2);
    const intentBoost     = precisionCount >= 2 ? 0.2 : 0;
    return Math.min(1, stabilitySignal * chaosOk + intentBoost);
  }
  return 0.5; // cinematic: neutral baseline
}

/**
 * Suggest an environment using memory-weighted history blended with a soft
 * state-affinity signal (70 % memory, 30 % state).
 *
 * When no env-tagged memories exist (bootstrap), falls back to pure state
 * signals and preserves intent-pattern detection behavior.
 *
 * Returns null if the best-match environment is already current.
 */
export function detectEnvironment(
  state:    PerformanceState,
  memories: IntentMemory[],
  current:  StyleEnvironment,
): StyleEnvironment | null {
  const recent10      = memories.slice(-10);
  const entropyCount  = recent10.filter(
    m => m.embeddingKey === 'entropy_control' || m.embeddingKey === 'tension_control',
  ).length;
  const precisionCount = recent10.filter(
    m => m.embeddingKey === 'stability_control' || m.embeddingKey === 'rhythm_control',
  ).length;

  const envList = Object.values(ENVIRONMENTS);
  let best      = envList[0]!;
  let bestScore = -Infinity;

  for (const env of envList) {
    const memScore   = scoreEnvironmentFromMemory(env.name, memories);
    const stateScore = stateAffinity(state, env, entropyCount, precisionCount);
    const blended    = memScore * 0.7 + stateScore * 0.3;
    if (blended > bestScore) {
      bestScore = blended;
      best      = env;
    }
  }

  return best.name === current.name ? null : best;
}

// ─── Manager ───────────────────────────────────────────────────────────────────

export class EnvironmentManager {
  private current:          StyleEnvironment;
  private locked:           boolean = false;
  private ticksSinceSwitch: number  = 0;
  private readonly cooldown: number;

  constructor(
    initial:  StyleEnvironment = ENVIRONMENTS.cinematic,
    cooldown = 60, // minimum frames between auto-switches
  ) {
    this.current  = initial;
    this.cooldown = cooldown;
  }

  get(): StyleEnvironment {
    return this.current;
  }

  switch(env: StyleEnvironment): void {
    this.current          = env;
    this.ticksSinceSwitch = 0;
  }

  /** Prevent auto-switching (manual control mode). */
  lock():   void { this.locked = true; }
  unlock(): void { this.locked = false; }
  get isLocked(): boolean { return this.locked; }

  /**
   * Suggest and apply the best environment based on current state + memory.
   * No-ops when locked or within cooldown.  Returns true if a switch occurred.
   */
  autoSelect(state: PerformanceState, memories: IntentMemory[]): boolean {
    if (this.locked) return false;
    this.ticksSinceSwitch++;
    if (this.ticksSinceSwitch < this.cooldown) return false;

    const suggested = detectEnvironment(state, memories, this.current);
    if (!suggested) return false;

    this.switch(suggested);
    return true;
  }
}
