// SkinRuntime: pure projection layer.
// Input: world snapshot = { t, zap, physics, visual, window }
// Output: render parameters
// Forbidden: EventTape access, cursor access, dt computation, internal memory affecting output.

export class SkinRuntime {
  #name;
  #mapFn;

  constructor(name, mapFn) {
    this.#name  = name;
    this.#mapFn = mapFn;
  }

  get name() { return this.#name; }

  project(world) { return this.#mapFn(world); }
}

// Beat Mania skin: high flow / medium focus vector interpretation
export const BeatManiaSkin = new SkinRuntime('beat-mania', (world) => {
  const { force, flow, chaos, focus } = world.zap.core.zap;
  const { intensity, entropy }        = world.zap.derived;
  const { field }                     = world.physics;
  const { layers, flash, distortion, pulse } = world.visual;
  const { density }                   = world.window;

  return {
    padCount:         4,
    padGlow:          layers.pad,
    ringGlow:         layers.ring,
    pulseRate:        intensity + field.momentum * 0.3,
    pulseAmount:      pulse,
    trailDensity:     density,
    chaosShake:       field.turbulence,
    distortion,
    flashAmount:      flash,
    focusLock:        focus,
    backgroundColor:  `hsl(${230 + force * 40}, 70%, ${8 + flow * 18}%)`,
    accentColor:      `hsl(${180 + focus * 60}, 90%, ${50 + intensity * 30}%)`,
    entropyFlicker:   entropy,
    t:                world.t,
  };
});
