/**
 * Unified Performance State Model.
 *
 * Every subsystem — audio, visuals, lighting, performer telemetry, crowd,
 * steering fields, chaos engine — reads from and writes to this state space.
 *
 * This is the "common language" layer.
 * State-driven show logic replaces timeline-driven cue lists.
 *
 * Example:
 *   Energy ↑ + Stability ↓ + Crowd Resonance ↑
 *   → Visual sequence extends
 *   → Lighting delays transition
 *   → Stem engine preserves tension
 */
export interface PerformanceState {
  // ── Physics core (from ManifoldRuntime) ──────────────────────────────────
  energy:        number; // [0, 1]  — performance vitality
  stability:     number; // [0, 1]  — behavioral coherence
  chaos:         number; // [0, 1]  — active instability level
  tension:       number; // [0, 1]  — distance from nearest attractor
  recovery:      number; // [0, 1]  — rate of return toward stability

  // ── Social dynamics ───────────────────────────────────────────────────────
  crowdResonance:  number; // [0, 1]  — estimated audience coupling (external input)
  performerIntent: [number, number]; // 2D force vector from performer telemetry

  // ── Venue physics ─────────────────────────────────────────────────────────
  venuePressure:   number; // [0, 1]  — accumulated environmental pressure

  // ── Temporal dynamics ────────────────────────────────────────────────────
  groove:          number; // [0, 1]  — rhythmic coherence / beat-lock depth
  drift:           number; // [0, 1]  — accumulated long-term deviation pressure

  // ── Meta ──────────────────────────────────────────────────────────────────
  timestamp:       number; // performance.now()
  frameIndex:      number;
  lastEvent?:      string; // most recent action type dispatched (debug tracing)
}

export const DEFAULT_PERFORMANCE_STATE: PerformanceState = {
  energy:          0.5,
  stability:       0.7,
  chaos:           0.1,
  tension:         0.3,
  recovery:        0.8,
  crowdResonance:  0.5,
  performerIntent: [0, 0],
  venuePressure:   0.1,
  groove:          0.4,
  drift:           0.0,
  timestamp:       0,
  frameIndex:      0,
};

import type { ManifoldState } from './manifold/ManifoldRuntime';

/**
 * Map a ManifoldState + injector values into the unified PerformanceState.
 * Additional subsystem readings (crowd, venue) are supplied as overrides.
 */
export function fromManifoldState(
  manifold: ManifoldState,
  chaos: number,
  frameIndex: number,
  overrides: Partial<PerformanceState> = {},
): PerformanceState {
  return {
    ...DEFAULT_PERFORMANCE_STATE,
    energy:          manifold.energy,
    stability:       manifold.coherence,
    chaos,
    tension:         Math.max(0, Math.abs(manifold.drift) - 0.2),
    recovery:        manifold.coherence * (1 - chaos * 0.4),
    drift:           Math.min(1, Math.abs(manifold.drift)),
    timestamp:       typeof performance !== 'undefined' ? performance.now() : 0,
    frameIndex,
    ...overrides,
  };
}

/**
 * A state-driven decision helper.
 * Returns a named verdict based on the current state.
 */
export function assessPerformanceState(
  state: PerformanceState,
): 'OPTIMAL' | 'ENERGIZED' | 'TENSE' | 'RECOVERING' | 'CRITICAL' {
  if (state.stability < 0.25 || state.chaos > 0.8)      return 'CRITICAL';
  if (state.energy < 0.3 && state.stability > 0.5)       return 'RECOVERING';
  if (state.tension > 0.6 && state.chaos > 0.4)          return 'TENSE';
  if (state.energy > 0.8 && state.stability > 0.7)       return 'OPTIMAL';
  return 'ENERGIZED';
}
