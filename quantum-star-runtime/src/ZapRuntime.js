// ZapRuntime is the ONLY system allowed to mutate CoreState.
// step(dt, events) is the atomic unit of reality.
// Everything else (audio, skins, UI, replay) is upstream or downstream.

export function createCoreState() {
  return {
    t: 0,
    hitCount: 0,
    comboCount: 0,
    score: 0,
    zap: { force: 0, flow: 0, chaos: 0, focus: 0 },
  };
}

export function createDerivedState(core) {
  const { force, flow, chaos, focus } = core.zap;
  return {
    intensity: (force + flow) / 2,
    entropy: chaos * (1 - focus),
    dominantVector: Object.entries(core.zap).reduce((a, b) => (b[1] > a[1] ? b : a))[0],
  };
}

export class ZapRuntime {
  #state;

  constructor(initialState = createCoreState()) {
    this.#state = structuredClone(initialState);
  }

  // The single entry point for time and state advancement.
  step(dt, events) {
    this.#state.t += dt;
    for (const event of events) this.#applyEvent(event);
    this.#decayZap(dt);
    return this.snapshot();
  }

  // Deterministic replay: reconstruct state(T) from scratch using the event tape.
  // Proves: state(t) == reduce(step, events[0..t])
  static replay(tape, targetT, frameDt = 1 / 60) {
    const runtime = new ZapRuntime();
    let tCursor = 0;
    while (tCursor < targetT) {
      const dt = Math.min(frameDt, targetT - tCursor);
      const events = tape.slice(tCursor, tCursor + dt);
      runtime.step(dt, events);
      tCursor += dt;
    }
    return runtime.snapshot();
  }

  snapshot() {
    const core = structuredClone(this.#state);
    return Object.freeze({ core, derived: createDerivedState(core) });
  }

  loadSnapshot(snapshot) {
    this.#state = structuredClone(snapshot.core);
  }

  #applyEvent(event) {
    const s = this.#state;
    if (event.type === 'HIT') {
      s.hitCount++;
      s.comboCount++;
      s.score += 100 * s.comboCount;
      s.zap.force = Math.min(1, s.zap.force + 0.25);
      s.zap.flow  = Math.min(1, s.zap.flow  + 0.12);
      s.zap.focus = Math.min(1, s.zap.focus + 0.08);
    } else if (event.type === 'MISS') {
      s.comboCount = 0;
      s.zap.chaos = Math.min(1, s.zap.chaos + 0.20);
      s.zap.focus = Math.max(0, s.zap.focus - 0.15);
    } else if (event.type === 'BEAT') {
      s.zap.flow = Math.min(1, s.zap.flow + 0.04);
    }
  }

  #decayZap(dt) {
    const z = this.#state.zap;
    const d = dt * 0.4;
    z.force = Math.max(0, z.force - d);
    z.flow  = Math.max(0, z.flow  - d * 0.5);
    z.chaos = Math.max(0, z.chaos - d * 0.9);
    z.focus = Math.max(0, z.focus - d * 0.2);
  }
}
