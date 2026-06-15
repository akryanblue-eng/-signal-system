// SkinRuntime is a pure projection layer.
// It receives state and window — never events, never audio, never UI input.
// Contract: SkinRuntime(state.zap, state.core, state.derived, window) → visual params

export class SkinRuntime {
  #name;
  #mapFn;

  constructor(name, mapFn) {
    this.#name = name;
    this.#mapFn = mapFn;
  }

  get name() { return this.#name; }

  project(state, window) {
    return this.#mapFn(state, window);
  }
}

// Beat Mania skin: high flow / medium focus vector
// Maps zap vectors directly to visual parameters — no logic, no state mutation.
export const BeatManiaSkin = new SkinRuntime('beat-mania', (state, window) => {
  const { force, flow, chaos, focus } = state.core.zap;
  const { intensity, entropy } = state.derived;
  return {
    padGlow: flow,
    padCount: 4,
    pulseRate: intensity,
    trailDensity: window.density,
    chaosShake: chaos,
    focusLock: focus,
    backgroundColor: `hsl(${230 + force * 40}, 70%, ${8 + flow * 18}%)`,
    accentColor: `hsl(${180 + focus * 60}, 90%, ${50 + intensity * 30}%)`,
    entropyFlicker: entropy,
    t: state.core.t,
  };
});
