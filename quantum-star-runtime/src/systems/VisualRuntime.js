// VisualRuntime: perception truth.
// Reads VisualTape events, influenced by ZapSnapshot.
// Outputs layer intensities, transient effects — consumed by SkinRuntime.
export class VisualRuntime {
  #state = {
    layers:     { pad: 0, ring: 0, trail: 0, bloom: 0 },
    pulse:      0,
    flash:      0,
    distortion: 0,
  };

  step(dt, visualEvents, zapSnap) {
    const { flow, force, chaos, focus } = zapSnap.core.zap;
    const { intensity } = zapSnap.derived;

    for (const e of visualEvents) {
      if (e.type === 'PULSE') {
        const layer = e.payload.layer;
        if (layer in this.#state.layers) {
          this.#state.layers[layer] = Math.min(1,
            this.#state.layers[layer] + e.payload.intensity * 0.5);
        }
        this.#state.pulse = Math.min(1, this.#state.pulse + e.payload.intensity * 0.6);
      } else if (e.type === 'FLASH') {
        this.#state.flash = 1;
      } else if (e.type === 'DISTORT') {
        this.#state.distortion = Math.min(1, this.#state.distortion + e.payload.amount);
      }
    }

    // Layers driven directly by zap vectors
    this.#state.layers.pad   = flow;
    this.#state.layers.ring  = force;
    this.#state.layers.trail = intensity;
    this.#state.layers.bloom = focus;

    // Transient decay
    this.#state.pulse       = Math.max(0,           this.#state.pulse       - dt * 4);
    this.#state.flash       = Math.max(0,           this.#state.flash       - dt * 10);
    this.#state.distortion  = Math.max(chaos * 0.2, this.#state.distortion  - dt * 2);

    return this.snapshot();
  }

  snapshot()         { return structuredClone(this.#state); }
  loadSnapshot(snap) { this.#state = structuredClone(snap); }
}
