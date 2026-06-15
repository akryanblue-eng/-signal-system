import { ZapRuntime, createCoreState } from './ZapRuntime.js';
import { PhysicsRuntime }              from '../systems/PhysicsRuntime.js';
import { VisualRuntime }               from '../systems/VisualRuntime.js';
import { WindowAccumulator }           from './WindowAccumulator.js';

// MultiTapeBus: DAW-style dispatcher.
// Routes each tape to its own runtime — no cross-tape contamination.
// ZapRuntime sees BeatTape only. Physics sees PhysicsTape only. Etc.
export class MultiTapeBus {
  #zap;
  #physics;
  #visual;
  #accum;
  #lastSeq = { beat: -1, physics: -1, visual: -1, meta: -1 };

  constructor() {
    this.#zap     = new ZapRuntime();
    this.#physics = new PhysicsRuntime();
    this.#visual  = new VisualRuntime();
    this.#accum   = new WindowAccumulator();
  }

  // Live mode: O(1) seq-based drain — processes only events added since last frame
  step(dt, t, tapes) {
    const beatEv    = this.#drain(tapes.beat,    'beat');
    const physicsEv = this.#drain(tapes.physics, 'physics');
    const visualEv  = this.#drain(tapes.visual,  'visual');
    this.#drain(tapes.meta, 'meta'); // consumed, not yet dispatched

    return this.#dispatch(dt, t, beatEv, physicsEv, visualEv, tapes.beat);
  }

  // Replay mode: time-based slicing — deterministic, does NOT advance #lastSeq
  stepReplay(dt, tCursor, tapes) {
    const tNext     = tCursor + dt;
    const beatEv    = tapes.beat.slice(tCursor, tNext);
    const physicsEv = tapes.physics.slice(tCursor, tNext);
    const visualEv  = tapes.visual.slice(tCursor, tNext);
    return this.#dispatch(dt, tNext, beatEv, physicsEv, visualEv, tapes.beat);
  }

  // After replay, sync #lastSeq to tape ends so live mode doesn't reprocess events
  catchUpSeqs(tapes) {
    this.#lastSeq = {
      beat:    tapes.beat.length    - 1,
      physics: tapes.physics.length - 1,
      visual:  tapes.visual.length  - 1,
      meta:    tapes.meta.length    - 1,
    };
  }

  reset() {
    this.#zap     = new ZapRuntime(createCoreState());
    this.#physics = new PhysicsRuntime();
    this.#visual  = new VisualRuntime();
    this.#lastSeq = { beat: -1, physics: -1, visual: -1, meta: -1 };
  }

  #drain(tape, key) {
    const events = tape.since(this.#lastSeq[key] + 1);
    if (events.length > 0) this.#lastSeq[key] = events[events.length - 1].seq;
    return events;
  }

  #dispatch(dt, t, beatEv, physicsEv, visualEv, beatTape) {
    const zapSnap     = this.#zap.step(dt, beatEv);
    const physicsSnap = this.#physics.step(dt, physicsEv, zapSnap);
    const visualSnap  = this.#visual.step(dt, visualEv, zapSnap);
    const window      = this.#accum.update(beatTape, t);
    return Object.freeze({ t, zap: zapSnap, physics: physicsSnap, visual: visualSnap, window });
  }
}
