import type { PerformanceAction } from './PerformanceAction';

// ─── Type ──────────────────────────────────────────────────────────────────────

/**
 * A Style is a personality vector that modifies HOW compiled actions feel,
 * not WHICH actions exist. It lives between the intent compiler and the
 * event bus — same input phrase, different emotional weight.
 *
 *   aggression  → scales chaos/tension/drift amplitudes
 *   precision   → scales stability/energy amplitudes
 *   grooveBias  → gates GROOVE_LOCK (< 0.5 suppresses it)
 */
export interface Style {
  name:       string;
  aggression: number; // [0, 2] — chaos/tension amplitude multiplier
  precision:  number; // [0, 1] — stability/energy amplitude multiplier
  grooveBias: number; // [0, 2] — > 0.5 passes GROOVE_LOCK through
}

// ─── Presets ───────────────────────────────────────────────────────────────────

export const STYLES = {
  neutral:     { name: 'neutral',      aggression: 1.0, precision: 0.7, grooveBias: 1.0 },
  cinematic:   { name: 'cinematic',    aggression: 0.6, precision: 0.9, grooveBias: 1.2 },
  chaoticJazz: { name: 'chaoticJazz', aggression: 1.4, precision: 0.4, grooveBias: 0.7 },
  minimal:     { name: 'minimal',      aggression: 0.3, precision: 1.0, grooveBias: 1.5 },
  aggressive:  { name: 'aggressive',   aggression: 1.8, precision: 0.3, grooveBias: 0.5 },
} satisfies Record<string, Style>;

// ─── Transformer ───────────────────────────────────────────────────────────────

const clamp = (v: number, lo = 0, hi = 1): number => Math.max(lo, Math.min(hi, v));

/**
 * Apply a style vector to a compiled action list.
 *
 * Rules:
 *   - aggression  scales  CHAOS_SPIKE, DRIFT_INJECTION, TENSION_BUILD amounts
 *   - precision   scales  ENERGY_PULSE, STABILITY_RESTORE amounts
 *   - grooveBias  gates   GROOVE_LOCK   (< 0.5 → drop)
 *   - aggression  gates   TENSION_RELEASE (≥ 1.5 → drop — aggressive styles don't self-dampen)
 */
export function applyStyle(
  actions: PerformanceAction[],
  style:   Style,
): PerformanceAction[] {
  const out: PerformanceAction[] = [];

  for (const action of actions) {
    switch (action.type) {
      case 'CHAOS_SPIKE':
        out.push({ ...action, amount: clamp(action.amount * style.aggression) });
        break;
      case 'DRIFT_INJECTION':
        out.push({ ...action, amount: clamp(action.amount * style.aggression) });
        break;
      case 'TENSION_BUILD':
        out.push({ ...action, amount: clamp(action.amount * style.aggression) });
        break;

      case 'ENERGY_PULSE':
        out.push({ ...action, amount: clamp(action.amount * style.precision) });
        break;
      case 'STABILITY_RESTORE':
        out.push({ ...action, amount: clamp(action.amount * style.precision) });
        break;

      case 'GROOVE_LOCK':
        if (style.grooveBias >= 0.5) out.push(action);
        break;

      case 'TENSION_RELEASE':
        if (style.aggression < 1.5) out.push(action);
        break;
    }
  }

  return out;
}
