// ─── Types ─────────────────────────────────────────────────────────────────────

/**
 * Four-dimensional objective space.  Every behavioral state maps to one of
 * these vectors; the Pareto frontier filters out strictly-dominated points.
 */
export interface ObjectiveVector {
  stability:   number; // [0, 1]
  performance: number; // [0, 1]
  exploration: number; // [0, 1]
  coherence:   number; // [0, 1]
}

/**
 * Operator-supplied bias that reshapes Pareto selection in real time.
 * Matches the keys of ObjectiveVector — acts as a weighted dot-product mask.
 */
export interface ControlSurface {
  stability:   number; // [0, 1]
  performance: number; // [0, 1]
  exploration: number; // [0, 1]
  coherence:   number; // [0, 1]
}

type ObjKey = keyof ObjectiveVector;
const OBJ_KEYS: ObjKey[] = ['stability', 'performance', 'exploration', 'coherence'];

// ─── Pareto dominance ──────────────────────────────────────────────────────────

/**
 * Returns true if `a` weakly dominates `b`:
 * a >= b in every dimension AND a > b in at least one.
 */
export function dominates(a: ObjectiveVector, b: ObjectiveVector): boolean {
  let better = false;
  for (const k of OBJ_KEYS) {
    if (a[k] < b[k]) return false;
    if (a[k] > b[k]) better = true;
  }
  return better;
}

/**
 * Return the non-dominated subset of `states`.
 * A state is on the frontier if no other state weakly dominates it.
 */
export function paretoFrontier(states: ObjectiveVector[]): ObjectiveVector[] {
  return states.filter(
    s => !states.some(other => other !== s && dominates(other, s)),
  );
}

// ─── Equilibrium selection ─────────────────────────────────────────────────────

/**
 * Min-variance equilibrium: choose the Pareto-optimal point whose dimension
 * values are most balanced.  Prefers "sustainable" regions over performance spikes.
 */
export function selectEquilibrium(frontier: ObjectiveVector[]): ObjectiveVector | null {
  if (frontier.length === 0) return null;
  let best:      ObjectiveVector | null = null;
  let bestVar    = Infinity;
  for (const f of frontier) {
    const mean    = OBJ_KEYS.reduce((s, k) => s + f[k], 0) / OBJ_KEYS.length;
    const variance = OBJ_KEYS.reduce((s, k) => s + (f[k] - mean) ** 2, 0) / OBJ_KEYS.length;
    if (variance < bestVar) { bestVar = variance; best = f; }
  }
  return best;
}

// ─── Control-surface selection ─────────────────────────────────────────────────

/**
 * Dot-product score of a state against a control surface.
 * Higher = more aligned with operator intent.
 */
export function scoreWithControl(
  state:   ObjectiveVector,
  control: ControlSurface,
): number {
  return OBJ_KEYS.reduce((s, k) => s + state[k] * control[k], 0);
}

/**
 * Pick the Pareto-optimal point that best satisfies the current control surface.
 * Replaces equilibrium selection when an operator is actively steering.
 */
export function selectWithControl(
  frontier: ObjectiveVector[],
  control:  ControlSurface,
): ObjectiveVector | null {
  if (frontier.length === 0) return null;
  let best:      ObjectiveVector | null = null;
  let bestScore  = -Infinity;
  for (const f of frontier) {
    const s = scoreWithControl(f, control);
    if (s > bestScore) { bestScore = s; best = f; }
  }
  return best;
}

// ─── Preset control scenes ─────────────────────────────────────────────────────

/**
 * Named presets that mirror environment personalities.
 * Passed to selectWithControl() to bias Pareto selection without manual knobs.
 */
export const CONTROL_SCENES: Record<string, ControlSurface> = {
  cinematic: { stability: 0.6, performance: 0.7, exploration: 0.3, coherence: 0.8 },
  precision: { stability: 0.9, performance: 0.8, exploration: 0.2, coherence: 0.9 },
  chaosJam:  { stability: 0.2, performance: 0.6, exploration: 0.9, coherence: 0.3 },
};
