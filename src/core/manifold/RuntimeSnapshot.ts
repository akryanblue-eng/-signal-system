import type { ManifoldState } from './ManifoldRuntime';
import type { FieldFeedbackSignal } from '../../engine/FieldFeedback';

/**
 * A traceable frame-by-frame snapshot of the runtime loop.
 * Every state transition should produce one of these.
 * If you can't explain why the field moved, look here first.
 */
export interface RuntimeSnapshot {
  frame:         number;
  timestamp:     number; // performance.now()
  drift:         number; // ManifoldState.drift
  energy:        number; // ManifoldState.energy
  stability:     number; // ManifoldState.coherence (1 − |drift|)
  chaos:         number; // injector chaos level
  attractorPull: number; // FieldFeedbackSignal.attractorPull
  driftPressure: number; // FieldFeedbackSignal.driftPressure
  timingOffset:  number; // ms ahead/behind groove center
}

/** Circular buffer that records the last N runtime snapshots. */
export class SnapshotRecorder {
  private buffer:     RuntimeSnapshot[] = [];
  private frameCount = 0;

  constructor(private readonly maxSize = 300) {}

  record(
    state:    ManifoldState,
    feedback: FieldFeedbackSignal,
    chaos:    number,
  ): RuntimeSnapshot {
    const snapshot: RuntimeSnapshot = {
      frame:         this.frameCount++,
      timestamp:     typeof performance !== 'undefined' ? performance.now() : 0,
      drift:         state.drift,
      energy:        state.energy,
      stability:     state.coherence,
      chaos,
      attractorPull: feedback.attractorPull,
      driftPressure: feedback.driftPressure,
      timingOffset:  feedback.timingOffset,
    };

    this.buffer.push(snapshot);
    if (this.buffer.length > this.maxSize) this.buffer.shift();
    return snapshot;
  }

  latest(): RuntimeSnapshot | null {
    return this.buffer[this.buffer.length - 1] ?? null;
  }

  all(): readonly RuntimeSnapshot[] {
    return this.buffer;
  }

  /** Check for runaway drift: returns true if |drift| > threshold for last N frames. */
  isRunaway(threshold = 0.85, consecutiveFrames = 10): boolean {
    const tail = this.buffer.slice(-consecutiveFrames);
    return tail.length === consecutiveFrames && tail.every(s => Math.abs(s.drift) > threshold);
  }

  clear(): void {
    this.buffer     = [];
    this.frameCount = 0;
  }
}
