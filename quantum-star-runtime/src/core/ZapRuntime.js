// ZapRuntime v0.5: reacts to BeatTape events ONLY.
// Physics, Visual, Meta tapes are not Zap's concern.
// Zap vectors (force/flow/chaos/focus) are the output field — downstream reads them.

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
    intensity:      (force + flow) / 2,
    entropy:        chaos * (1 - focus),
    dominantVector: Object.entries(core.zap).reduce((a, b) => (b[1] > a[1] ? b : a))[0],
  };
}

export class ZapRuntime {
  #state;

  constructor(initialState = createCoreState()) {
    this.#state = structuredClone(initialState);
  }

  step(dt, beatEvents) {
    this.#state.t += dt;
    for (const event of beatEvents) this.#applyBeatEvent(event);
    this.#decayZap(dt);
    return this.snapshot();
  }

  snapshot() {
    const core = structuredClone(this.#state);
    return Object.freeze({ core, derived: createDerivedState(core) });
  }

  loadSnapshot(snapshot) {
    this.#state = structuredClone(snapshot.core);
  }

  #applyBeatEvent(event) {
    const s = this.#state;
    switch (event.type) {
      case 'HIT':
        s.hitCount++;
        s.comboCount++;
        s.score += 100 * s.comboCount;
        s.zap.force = Math.min(1, s.zap.force + 0.25);
        s.zap.flow  = Math.min(1, s.zap.flow  + 0.12);
        s.zap.focus = Math.min(1, s.zap.focus + 0.08);
        break;
      case 'MISS':
        s.comboCount = 0;
        s.zap.chaos = Math.min(1, s.zap.chaos + 0.20);
        s.zap.focus = Math.max(0, s.zap.focus - 0.15);
        break;
      case 'ACCENT':
        s.zap.flow = Math.min(1, s.zap.flow + 0.08);
        break;
      case 'BEAT':
        s.zap.flow = Math.min(1, s.zap.flow + 0.04);
        break;
      case 'GHOST':
        s.zap.flow = Math.min(1, s.zap.flow + 0.02);
        break;
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
