import { Tape } from './Tape.js';

// Simulation truth tape. PhysicsRuntime reads this exclusively.
// event types: IMPULSE | COLLISION
export class PhysicsTape extends Tape {
  constructor() { super('physics'); }

  impulse(t, entityId, force, angle) {
    return this._append('IMPULSE', { entityId, force, angle }, t);
  }
  collision(t, a, b, impact) {
    return this._append('COLLISION', { a, b, impact }, t);
  }
}
