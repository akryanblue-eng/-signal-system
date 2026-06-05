import type { ManifoldState, ManifoldForce } from '../core/manifold/ManifoldRuntime';
import { step, manifoldGovernor } from '../core/manifold/ManifoldRuntime';
import type { FlowFieldInjector } from './MidiForceInjector';
import type { FlowFieldRenderer, RenderPayload } from '../visualization/FlowFieldRenderer';
import { computeFieldFeedback, applyFeedbackToInjector } from './FieldFeedback';
import type { FieldFeedbackSignal } from './FieldFeedback';
import { SnapshotRecorder } from '../core/manifold/RuntimeSnapshot';
import type { RuntimeSnapshot } from '../core/manifold/RuntimeSnapshot';
import { blendSteeringState } from '../core/manifold/SteeringState';
import type { SteeringState } from '../core/manifold/SteeringState';
import type { Vec2 } from '../math/vector';

export interface BrainRuntimeOutput {
  state:    ManifoldState;
  force:    ManifoldForce;
  feedback: FieldFeedbackSignal;
  snapshot: RuntimeSnapshot;
  steering: SteeringState;
}

/**
 * Master orchestrator for the bidirectional brain loop.
 *
 * Tick order:
 *   1. Read injector state   (Performer → Field via MIDI)
 *   2. Advance physics       (ManifoldRuntime.step)
 *   3. Compute feedback      (Field → Performer signals)
 *   4. Push feedback back    (smoothed re-parameterization of injector)
 *   5. Record snapshot       (traceable frame state for inspection)
 *   6. Render                (physics snapshot → visual frame)
 *
 * Every frame produces a RuntimeSnapshot. If you can't explain why the
 * field moved, call getSnapshots() and inspect the last N frames.
 */
export class BidirectionalBrainRuntime {
  private state:     ManifoldState | null = null;
  private prevState: ManifoldState | null = null;
  private running    = false;
  private lastTime   = 0;
  private snapshots  = new SnapshotRecorder(300);
  private lastSteering: SteeringState | null = null;

  constructor(
    private readonly injector: FlowFieldInjector,
    private readonly renderer: FlowFieldRenderer,
  ) {}

  start(initialState: ManifoldState): void {
    if (this.running) return;
    this.state    = { ...initialState };
    this.running  = true;
    this.lastTime = performance.now();

    const loop = (t: number): void => {
      if (!this.running || !this.state) return;
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

  /** Single tick — callable externally for testing (pass dt in seconds). */
  tickStep(dt: number): BrainRuntimeOutput | null {
    if (!this.state) return null;

    // 1. Read performer force from injector (raw MIDI / audio input)
    const performerForce = this.injector.getForce();

    // 2. Compute governor correction (kernel policy)
    const policy       = manifoldGovernor(this.state);
    const kernelForce: ManifoldForce = [
      (policy.chaos - policy.stability) * 0.02,
      (policy.chaos - 0.3) * 0.02,
    ];

    // 3. Blend and track steering state (for visual separation)
    const steering = blendSteeringState(
      performerForce as Vec2,
      kernelForce    as Vec2,
    );
    this.lastSteering = steering;

    const finalForce = steering.finalForce as ManifoldForce;

    // 4. Advance physics
    const nextState = step(this.state, dt, finalForce);

    // 5. Compute reverse-path feedback
    const { chaos } = this.injector.getState();
    const feedback  = computeFieldFeedback(nextState, this.prevState, chaos);

    // 6. Apply feedback back via smoothed injector (α = 0.05 to prevent runaway)
    applyFeedbackToInjector(
      feedback,
      () => this.injector.getState(),
      v => this.injector.apply({ type: 'damping', stability: v }, true), // smoothed
      v => this.injector.apply({ type: 'chaos',   intensity: v }, true), // smoothed
    );

    // 7. Record traceable snapshot
    const snapshot = this.snapshots.record(nextState, feedback, chaos);

    // 8. Render
    const payload: RenderPayload = {
      state:    nextState,
      chaos,
      damping:  this.injector.getState().damping,
      feedback,
    };
    this.renderer.render(payload);

    this.prevState = this.state;
    this.state     = nextState;

    return { state: nextState, force: finalForce, feedback, snapshot, steering };
  }

  /** Current manifold state. */
  getState(): ManifoldState | null {
    return this.state;
  }

  /** Last N runtime snapshots for inspection. */
  getSnapshots(): readonly RuntimeSnapshot[] {
    return this.snapshots.all();
  }

  getLatestSnapshot(): RuntimeSnapshot | null {
    return this.snapshots.latest();
  }

  /** Most recent steering force breakdown. */
  getSteeringState(): SteeringState | null {
    return this.lastSteering;
  }

  /** True if drift has been above 0.85 for 10+ consecutive frames. */
  isRunaway(): boolean {
    return this.snapshots.isRunaway();
  }
}
