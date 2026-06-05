import type { PerformanceState } from '../PerformanceState';
import type { PerformanceAction } from './PerformanceAction';

const clamp = (v: number, lo = 0, hi = 1): number => Math.max(lo, Math.min(hi, v));

/**
 * Pure reducer — PerformanceState × PerformanceAction → PerformanceState.
 *
 * Rules:
 *   - All values clamped to [0, 1] on exit
 *   - No side effects; no I/O; no external references
 *   - lastEvent tracks causal origin for debug tracing
 */
export function performanceReducer(
  state: PerformanceState,
  action: PerformanceAction,
): PerformanceState {
  switch (action.type) {
    case 'CHAOS_SPIKE':
      return {
        ...state,
        chaos:     clamp(state.chaos     + action.amount),
        stability: clamp(state.stability - action.amount * 0.4),
        lastEvent: action.type,
      };

    case 'TENSION_BUILD':
      return {
        ...state,
        tension:   clamp(state.tension + action.amount),
        energy:    clamp(state.energy  + action.amount * 0.2),
        lastEvent: action.type,
      };

    case 'TENSION_RELEASE':
      return {
        ...state,
        tension:   clamp(state.tension   * 0.6),
        stability: clamp(state.stability + 0.1),
        lastEvent: action.type,
      };

    case 'GROOVE_LOCK':
      return {
        ...state,
        groove:    clamp(state.groove + 0.12),
        chaos:     clamp(state.chaos  * 0.85),
        lastEvent: action.type,
      };

    case 'DRIFT_INJECTION':
      return {
        ...state,
        drift:     clamp(state.drift + action.amount),
        chaos:     clamp(state.chaos + action.amount),
        lastEvent: action.type,
      };

    case 'ENERGY_PULSE':
      return {
        ...state,
        energy:    clamp(state.energy + action.amount),
        lastEvent: action.type,
      };

    case 'STABILITY_RESTORE':
      return {
        ...state,
        stability: clamp(state.stability + action.amount),
        lastEvent: action.type,
      };
  }
}
