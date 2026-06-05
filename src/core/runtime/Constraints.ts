import type { PerformanceState } from '../PerformanceState';
import type { Style } from './Style';
import type { PerformanceAction } from './PerformanceAction';

// ─── Style bounds ──────────────────────────────────────────────────────────────

export interface StyleBounds {
  aggression: { min: number; max: number };
  precision:  { min: number; max: number };
  grooveBias: { min: number; max: number };
}

/** Conservative bounds — prevents the learned style from becoming unplayable. */
export const DEFAULT_STYLE_BOUNDS: StyleBounds = {
  aggression: { min: 0.2, max: 1.6 },
  precision:  { min: 0.2, max: 1.0 },
  grooveBias: { min: 0.3, max: 1.8 },
};

/** Clamp a Style vector to bounds. Applied after smoothStyle to contain drift. */
export function clampStyle(style: Style, bounds: StyleBounds = DEFAULT_STYLE_BOUNDS): Style {
  return {
    name:       style.name,
    aggression: Math.max(bounds.aggression.min, Math.min(bounds.aggression.max, style.aggression)),
    precision:  Math.max(bounds.precision.min,  Math.min(bounds.precision.max,  style.precision)),
    grooveBias: Math.max(bounds.grooveBias.min, Math.min(bounds.grooveBias.max, style.grooveBias)),
  };
}

// ─── State safety zones ────────────────────────────────────────────────────────

export type SafetyVerdict = 'SAFE' | 'CAUTION' | 'CRITICAL';

/**
 * Classify the current state against safety thresholds.
 * CRITICAL states gate or attenuate destabilizing actions.
 */
export function classifyStateSafety(state: PerformanceState): SafetyVerdict {
  if (state.chaos > 0.9 || state.stability < 0.15 || state.drift > 0.85) return 'CRITICAL';
  if (state.chaos > 0.7 || state.stability < 0.3  || state.drift > 0.6)  return 'CAUTION';
  return 'SAFE';
}

// ─── Action gating ─────────────────────────────────────────────────────────────

/**
 * Filter and attenuate actions based on current state safety.
 *
 * CAUTION: destabilizing actions (CHAOS_SPIKE, DRIFT_INJECTION) are halved.
 * CRITICAL: destabilizing actions are dropped entirely; STABILITY_RESTORE is
 *   injected automatically to pull the system back.
 */
export function gateActions(
  actions:  PerformanceAction[],
  state:    PerformanceState,
): PerformanceAction[] {
  const verdict = classifyStateSafety(state);
  if (verdict === 'SAFE') return actions;

  const DESTABILIZING = new Set<string>(['CHAOS_SPIKE', 'DRIFT_INJECTION', 'TENSION_BUILD']);

  if (verdict === 'CAUTION') {
    return actions.map(a =>
      DESTABILIZING.has(a.type) && 'amount' in a
        ? { ...a, amount: a.amount * 0.5 }
        : a,
    );
  }

  // CRITICAL — drop destabilizing actions; inject recovery
  const safe = actions.filter(a => !DESTABILIZING.has(a.type));
  const alreadyRestoring = safe.some(a => a.type === 'STABILITY_RESTORE' || a.type === 'TENSION_RELEASE');
  if (!alreadyRestoring) {
    safe.push({ type: 'STABILITY_RESTORE', amount: 0.15 });
    safe.push({ type: 'TENSION_RELEASE' });
  }
  return safe;
}
