export class TimelineClock {
  #cursor = 0;
  #speed = 1;
  #running = false;
  #lastTick = 0;

  get cursor()    { return this.#cursor; }
  get isRunning() { return this.#running; }

  play() {
    if (this.#running) return;
    this.#running = true;
    this.#lastTick = performance.now();
  }

  pause() { this.#running = false; }

  seek(t) { this.#cursor = Math.max(0, t); }

  setSpeed(s) { this.#speed = Math.max(0.1, s); }

  // Returns dt in seconds. Only TimelineClock advances the cursor — nothing else.
  tick() {
    if (!this.#running) return 0;
    const now = performance.now();
    const dt = ((now - this.#lastTick) / 1000) * this.#speed;
    this.#lastTick = now;
    this.#cursor += dt;
    return dt;
  }
}
