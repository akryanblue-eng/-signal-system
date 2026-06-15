// Append-only ordered event log. Events are frozen on creation.
// seq === array index, so since(seq) is O(1) slice.
export class EventTape {
  #events = [];

  append(type, payload, t) {
    const event = Object.freeze({ seq: this.#events.length, t, type, payload: Object.freeze(payload) });
    this.#events.push(event);
    return event;
  }

  // All events with seq >= seq (live mode: new events since last frame)
  since(seq) {
    return this.#events.slice(seq);
  }

  // Events in half-open range [tStart, tEnd) (replay mode: scrub window)
  slice(tStart, tEnd) {
    return this.#events.filter(e => e.t >= tStart && e.t < tEnd);
  }

  get length() { return this.#events.length; }

  [Symbol.iterator]() { return this.#events[Symbol.iterator](); }
}
