import { Tape } from './Tape.js';

// Rhythm truth tape. ZapRuntime reads this exclusively.
// event types: HIT | MISS | BEAT | ACCENT | GHOST
export class BeatTape extends Tape {
  constructor() { super('beat'); }

  hit(t, key, velocity = 1) { return this._append('HIT',    { key, velocity }, t); }
  miss(t, key)               { return this._append('MISS',   { key }, t); }
  beat(t, tick, bpm)         { return this._append('BEAT',   { tick, bpm }, t); }
  accent(t, tick, bpm)       { return this._append('ACCENT', { tick, bpm }, t); }
  ghost(t, key)              { return this._append('GHOST',  { key }, t); }
}
