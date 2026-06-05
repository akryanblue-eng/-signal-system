import type { ManifoldState } from '../core/manifold/ManifoldRuntime';

/** Signals emitted by the field back toward the performer. */
export interface FieldFeedbackSignal {
  driftPressure:     number;          // [0, 1] — how unstable performance is
  attractorPull:     number;          // [0, 1] — strength of correction toward stability
  timingOffset:      number;          // ms ahead/behind perceived groove center
  energyGradient:    number;          // rate of energy change (positive = rising)
  correctionVector:  [number, number]; // 2D nudge direction in manifold space
}

/**
 * Derive field feedback signals from the current manifold state.
 *
 * These signals feed the reverse path of the bidirectional loop:
 * the field's diagnosis of what the performer needs to hear / see / feel.
 */
export function computeFieldFeedback(
  state:     ManifoldState,
  prevState: ManifoldState | null,
  chaosLevel: number,
): FieldFeedbackSignal {
  const driftPressure     = Math.min(1, Math.abs(state.drift));
  const attractorPull     = chaosLevel < 0.3 ? 0.9 : 0.4;
  const timingOffset      = state.energy * 12 - state.drift * 20;
  const energyGradient    = prevState ? state.energy - prevState.energy : 0;
  const correctionVector: [number, number] = [
    -state.drift  * 0.8,
    (1 - state.coherence) * 0.6,
  ];

  return { driftPressure, attractorPull, timingOffset, energyGradient, correctionVector };
}

/** Apply feedback to gently re-parameterize the injector's control surface. */
export function applyFeedbackToInjector(
  feedback:   FieldFeedbackSignal,
  getCurrentState: () => { chaos: number; damping: number },
  setStability: (v: number) => void,
  setChaos:     (v: number) => void,
): void {
  const { chaos, damping } = getCurrentState();
  setStability(Math.min(1, damping  + (1 - feedback.driftPressure) * 0.05));
  setChaos    (Math.max(0, chaos    - feedback.attractorPull        * 0.03));
}
