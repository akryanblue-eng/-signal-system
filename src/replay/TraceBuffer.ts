import type { PerformanceState } from '../core/PerformanceState';

// ─── Frame ─────────────────────────────────────────────────────────────────────

/**
 * One snapshot per tick — the unified observation format that collapses all
 * runtime signals into a single addressable timeline record.
 */
export interface Frame {
  t:                   number;          // frameIndex at capture time
  input:               string;          // last active intent key
  state:               PerformanceState;
  env:                 string;          // active environment name
  policyEnv:           string;          // environment predicted by PolicyModel
  oracleEnv:           string;          // environment recommended by counterfactual oracle
  usedPolicy:          boolean;         // true = fast path; false = oracle simulation
  counterfactualDelta: number;          // score delta from oracle evaluation
  identityScore:       number;          // MetaObserver.evaluate() at this tick
  thought:             string;          // "fast-path intuition" | "oracle simulation fallback"
}

// ─── Buffer ────────────────────────────────────────────────────────────────────

/**
 * Circular buffer of Frames.  Cap defaults to 1000 ticks (~16 s at 60 fps).
 * Once full, oldest frames are evicted to bound memory.
 */
export class TraceBuffer {
  private frames:          Frame[] = [];
  private readonly capacity: number;

  constructor(capacity = 1000) {
    this.capacity = capacity;
  }

  push(frame: Frame): void {
    this.frames.push(frame);
    if (this.frames.length > this.capacity) this.frames.shift();
  }

  /** Last n frames, most-recent-last. */
  recent(n = 50): Frame[] {
    return this.frames.slice(-n);
  }

  /** All frames currently in the buffer. */
  getAll(): Frame[] {
    return [...this.frames];
  }

  get size():     number { return this.frames.length; }
  get maxSize():  number { return this.capacity; }

  clear(): void { this.frames = []; }
}
