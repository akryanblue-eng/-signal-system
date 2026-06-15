import { Tape } from './Tape.js';

// Render hint tape. VisualRuntime reads this exclusively.
// event types: PULSE | FLASH | DISTORT
export class VisualTape extends Tape {
  constructor() { super('visual'); }

  pulse(t, layer, intensity) { return this._append('PULSE',   { layer, intensity }, t); }
  flash(t, colorHint = null) { return this._append('FLASH',   { colorHint }, t); }
  distort(t, amount)         { return this._append('DISTORT', { amount }, t); }
}
