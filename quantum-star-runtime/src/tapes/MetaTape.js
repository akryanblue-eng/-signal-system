import { Tape } from './Tape.js';

// System/editor truth tape. Carries seek, speed, snapshot, mode transitions.
// event types: SEEK | SPEED | SNAPSHOT | MODE
export class MetaTape extends Tape {
  constructor() { super('meta'); }

  seek(t, targetT)      { return this._append('SEEK',     { targetT }, t); }
  speedChange(t, speed) { return this._append('SPEED',    { speed }, t); }
  snapshot(t, label)    { return this._append('SNAPSHOT', { label }, t); }
  modeChange(t, mode)   { return this._append('MODE',     { mode }, t); }
}
