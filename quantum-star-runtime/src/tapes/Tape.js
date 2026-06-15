// Base append-only event ledger.
// seq === array index invariant: since(seq) is O(1) slice — no sorting ever.
// Subclasses add domain-specific append helpers.
export class Tape {
  #events = [];
  #name;

  constructor(name) { this.#name = name; }

  get name()   { return this.#name; }
  get length() { return this.#events.length; }

  _append(type, payload, t) {
    const event = Object.freeze({
      seq: this.#events.length,
      t,
      type,
      payload: Object.freeze({ ...payload }),
    });
    this.#events.push(event);
    return event;
  }

  // O(1) slice from seq — live mode (process new events only)
  since(seq) { return this.#events.slice(seq); }

  // Time-range filter — replay mode (deterministic window)
  slice(tStart, tEnd) {
    return this.#events.filter(e => e.t >= tStart && e.t < tEnd);
  }

  reset() { this.#events.length = 0; }

  [Symbol.iterator]() { return this.#events[Symbol.iterator](); }
}
