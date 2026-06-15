// PhysicsRuntime: simulation truth.
// Reads PhysicsTape events, optionally influenced by ZapSnapshot (one-directional).
// Does NOT write back to Zap — no lateral mutation.
export class PhysicsRuntime {
  #state = {
    field: { momentum: 0, turbulence: 0, pressure: 0 },
  };

  step(dt, physicsEvents, zapSnap) {
    const { force, chaos } = zapSnap.core.zap;
    const { intensity } = zapSnap.derived;

    for (const e of physicsEvents) {
      if (e.type === 'IMPULSE') {
        this.#state.field.momentum = Math.min(1,
          this.#state.field.momentum + e.payload.force * 0.3);
      }
    }

    // Field lerps toward zap-driven targets — downstream read, not mutation
    const lerpRate = dt * 3;
    const targetMomentum   = force * 0.6 + intensity * 0.4;
    const targetTurbulence = chaos;
    const targetPressure   = intensity;

    this.#state.field.momentum   += (targetMomentum   - this.#state.field.momentum)   * lerpRate;
    this.#state.field.turbulence += (targetTurbulence - this.#state.field.turbulence) * lerpRate * 2;
    this.#state.field.pressure   += (targetPressure   - this.#state.field.pressure)   * lerpRate;

    return this.snapshot();
  }

  snapshot()           { return structuredClone(this.#state); }
  loadSnapshot(snap)   { this.#state = structuredClone(snap); }
}
