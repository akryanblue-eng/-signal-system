import type { ManifoldState, ManifoldForce } from '../core/manifold/ManifoldRuntime';
import { step, manifoldGovernor } from '../core/manifold/ManifoldRuntime';
import type { FlowFieldInjector } from './MidiForceInjector';
import type { FlowFieldRenderer, RenderPayload } from '../visualization/FlowFieldRenderer';
import { computeFieldFeedback, applyFeedbackToInjector } from './FieldFeedback';
import type { FieldFeedbackSignal } from './FieldFeedback';

export interface BrainRuntimeOutput {
  state:    ManifoldState;
  force:    ManifoldForce;
  feedback: FieldFeedbackSignal;
}

/**
 * Master orchestrator for the bidirectional brain loop.
 *
 * Tick order:
 *   1. Read injector state  (Performer → Field via MIDI)
 *   2. Advance physics      (ManifoldRuntime.step)
 *   3. Compute feedback     (Field → Performer signals)
 *   4. Push feedback back   (modulate injector's control surface)
 *   5. Render               (physics snapshot → visual frame)
 *
 * The loop drives itself via requestAnimationFrame.
 */
export class BidirectionalBrainRuntime {
  private state:     ManifoldState | null = null;
  private prevState: ManifoldState | null = null;
  private running    = false;
  private lastTime   = 0;

  constructor(
    private readonly injector: FlowFieldInjector,
    private readonly renderer: FlowFieldRenderer,
  ) {}

  start(initialState: ManifoldState): void {
    if (this.running) return;
    this.state   = { ...initialState };
    this.running  = true;
    this.lastTime = performance.now();

    const loop = (t: number): void => {
      if (!this.running || !this.state) return;
      const dt       = Math.min((t - this.lastTime) / 1000, 0.05);
      this.lastTime  = t;
      this.tickStep(dt);
      requestAnimationFrame(loop);
    };

    requestAnimationFrame(loop);
  }

  stop(): void {
    this.running = false;
  }

  /** Single tick — also callable externally for testing. */
  tickStep(dt: number): BrainRuntimeOutput | null {
    if (!this.state) return null;

    // 1. Read current force from injector (MIDI / audio)
    const force = this.injector.getForce();

    // 2. Advance physics — governor resolves policy when no explicit force
    const policy     = manifoldGovernor(this.state);
    const blendedForce: ManifoldForce = [
      force[0] + (policy.chaos - policy.stability) * 0.02,
      force[1] + (policy.chaos - 0.3) * 0.02,
    ];
    const nextState = step(this.state, dt, blendedForce);

    // 3. Compute reverse-path feedback signals
    const { chaos } = this.injector.getState();
    const feedback  = computeFieldFeedback(nextState, this.prevState, chaos);

    // 4. Push feedback back into injector's control surface
    applyFeedbackToInjector(
      feedback,
      () => ({ chaos: this.injector.getState().chaos, damping: this.injector.getState().damping }),
      // Note: FlowFieldInjector doesn't have setStability/setChaos directly;
      // feedback nudges are applied via apply() with synthetic events:
      v => this.injector.apply({ type: 'damping',  stability: v }),
      v => this.injector.apply({ type: 'chaos',    intensity: v }),
    );

    // 5. Render
    const payload: RenderPayload = {
      state:    nextState,
      chaos:    chaos,
      damping:  this.injector.getState().damping,
      feedback,
    };
    this.renderer.render(payload);

    // 6. Advance state
    this.prevState = this.state;
    this.state     = nextState;

    return { state: nextState, force: blendedForce, feedback };
  }

  getState(): ManifoldState | null {
    return this.state;
  }
}
