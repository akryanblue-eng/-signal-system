/** Observed dynamical state of the manifold — what the system measures. */
export interface ManifoldState {
  drift:     number; // [−1, 1]  — bounded phase variable (negative = receding, positive = advancing)
  energy:    number; // [ 0, 1]  — vitality level
  coherence: number; // [ 0, 1]  — derived: 1 − |drift|
}

/** Governor policy output — what the system intends to do. */
export interface ManifoldPolicy {
  stability: number; // [0, 1] — weight toward anchoring attractors
  chaos:     number; // [0, 1] — weight toward energizing attractors
  sparsity:  number; // [0, 1] — damping / hands-off weight
}

/** Resolved 2D force vector in manifold space. */
export type ManifoldForce = readonly [dDrift: number, dEnergy: number];

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

/**
 * Pure governor function: observed state → steering policy.
 * No side effects, no memory. Deterministic.
 */
export function manifoldGovernor(state: ManifoldState): ManifoldPolicy {
  if (state.drift > 0.7) {
    return { stability: 0.8, chaos: 0.1, sparsity: 0.1 };
  }
  if (state.energy < 0.4) {
    return { stability: 0.2, chaos: 0.7, sparsity: 0.1 };
  }
  if (state.coherence > 0.85) {
    return { stability: 0.4, chaos: 0.4, sparsity: 0.2 };
  }
  return { stability: 0.5, chaos: 0.3, sparsity: 0.2 };
}

/**
 * Time-aware, bounded state step.
 * dt is in seconds. Forces are resolved before this function is called.
 */
export function step(state: ManifoldState, dt: number, force: ManifoldForce): ManifoldState {
  const drift     = clamp(state.drift  + force[0] * dt, -1,  1);
  const energy    = clamp(state.energy + force[1] * dt,  0,  1);
  const coherence = clamp(1 - Math.abs(drift),            0,  1);
  return { drift, energy, coherence };
}

/**
 * requestAnimationFrame-driven runtime loop.
 *
 * Drives physics at display framerate, calls renderFn with the current
 * state after each physics step. Frame-rate independent via dt accumulation.
 *
 * Usage:
 *   const rt = new ManifoldRuntime(initialState);
 *   rt.start(
 *     (state, dt) => step(state, dt, resolveForces(state, policy)),
 *     (state)     => renderer.draw(state),
 *   );
 */
export class ManifoldRuntime {
  public  state:    ManifoldState;
  /** Injectable force vector — set this externally (e.g. from MIDI) to perturb the field. */
  public  forces:   ManifoldForce = [0, 0];
  private running:  boolean = false;
  private lastTime: number  = 0;
  private rafId:    number  = 0;

  constructor(initialState: ManifoldState) {
    this.state = { ...initialState };
  }

  /** Convenience wrapper: apply `this.forces` unless an explicit force is provided. */
  step(currentState: ManifoldState, dt: number, force?: ManifoldForce): ManifoldState {
    return step(currentState, dt, force ?? this.forces);
  }

  start(
    stepFn:   (state: ManifoldState, dt: number) => ManifoldState,
    renderFn: (state: ManifoldState) => void,
  ): void {
    if (this.running) return;
    this.running  = true;
    this.lastTime = performance.now();

    const loop = (t: number): void => {
      if (!this.running) return;
      const dt  = Math.min((t - this.lastTime) / 1000, 0.05); // cap at 50ms to survive tab hide
      this.lastTime = t;
      this.state = stepFn(this.state, dt);
      renderFn(this.state);
      this.rafId = requestAnimationFrame(loop);
    };

    this.rafId = requestAnimationFrame(loop);
  }

  stop(): void {
    this.running = false;
    cancelAnimationFrame(this.rafId);
  }

  /** Snap state without stopping the loop. Useful for hard resets. */
  resetState(state: ManifoldState): void {
    this.state = { ...state };
  }
}
