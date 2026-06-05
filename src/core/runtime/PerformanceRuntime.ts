import type { PerformanceState } from '../PerformanceState';
import type { PerformanceAction, Dispatch } from './PerformanceAction';
import { EventBus } from './EventBus';
import { performanceReducer } from './performanceReducer';

// ─── System interface ──────────────────────────────────────────────────────────

/** A system reads state and queues actions — it never mutates state directly. */
export interface PerformanceSystem {
  tick(state: PerformanceState, dispatch: Dispatch): void;
}

// ─── Built-in systems ──────────────────────────────────────────────────────────

/**
 * Reacts to high tension and low stability by injecting chaos/drift.
 * The physic-level equivalent of "stress response."
 */
export class ChaosSystem implements PerformanceSystem {
  tick(state: PerformanceState, dispatch: Dispatch): void {
    if (state.tension > 0.65) {
      dispatch({ type: 'CHAOS_SPIKE', amount: state.tension * 0.08 });
    }
    if (state.stability < 0.35) {
      dispatch({ type: 'DRIFT_INJECTION', amount: 0.05 });
    }
  }
}

/**
 * Anti-explosion regulator — damps runaway chaos and tightens groove
 * when the field starts destabilizing.
 */
export class GovernorSystem implements PerformanceSystem {
  tick(state: PerformanceState, dispatch: Dispatch): void {
    if (state.chaos > 0.75) {
      dispatch({ type: 'TENSION_RELEASE' });
    }
    if (state.stability < 0.4) {
      dispatch({ type: 'GROOVE_LOCK' });
    }
  }
}

// ─── Runtime ───────────────────────────────────────────────────────────────────

/**
 * Orchestrates the per-tick pipeline:
 *
 *   systems.tick() → EventBus.flush() → performanceReducer() → new state
 *
 * Tick order (single causal pass per frame):
 *   1. Advance frame counter + timestamp
 *   2. Systems read current state and queue actions
 *   3. Flush event queue → reducer (atomic per frame)
 *   4. Return new state
 *
 * tickStep() is callable externally for testing; start()/stop() wraps RAF.
 */
export class PerformanceRuntime {
  private state:   PerformanceState;
  private bus:     EventBus<PerformanceAction> = new EventBus();
  private systems: PerformanceSystem[];
  private running  = false;
  private lastTime = 0;

  constructor(
    initialState: PerformanceState,
    systems: PerformanceSystem[] = [new ChaosSystem(), new GovernorSystem()],
  ) {
    this.state   = { ...initialState };
    this.systems = systems;
  }

  /** Queue an action for processing in the current (or next) tick. */
  readonly dispatch: Dispatch = (action) => {
    this.bus.dispatch(action);
  };

  /** Single deterministic tick — safe to call in tests without RAF. */
  tickStep(dt: number): PerformanceState {
    // 1. Advance time metadata
    this.state = {
      ...this.state,
      frameIndex: this.state.frameIndex + 1,
      timestamp:  this.state.timestamp  + dt * 1000,
    };

    // 2. Systems read current state and queue actions (read phase — no mutation)
    for (const sys of this.systems) {
      sys.tick(this.state, this.dispatch);
    }

    // 3. Flush queue → reducer (single causal pass)
    for (const action of this.bus.flush()) {
      this.state = performanceReducer(this.state, action);
    }

    return this.state;
  }

  getState(): PerformanceState {
    return this.state;
  }

  start(): void {
    if (this.running) return;
    this.running  = true;
    this.lastTime = performance.now();

    const loop = (t: number): void => {
      if (!this.running) return;
      const dt      = Math.min((t - this.lastTime) / 1000, 0.05);
      this.lastTime = t;
      this.tickStep(dt);
      requestAnimationFrame(loop);
    };

    requestAnimationFrame(loop);
  }

  stop(): void {
    this.running = false;
  }
}
