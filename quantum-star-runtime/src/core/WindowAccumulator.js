// Option A: event replay reconstruction — seek-safe, perfectly deterministic.
// On seek: reset and replay BeatTape from (t - WINDOW_SIZE → t) to rebuild.
// Option B (ring buffer snapshot) once the runtime stabilizes.

const WINDOW_SIZE = 2; // seconds

export class WindowAccumulator {
  update(beatTape, t) {
    const tStart = Math.max(0, t - WINDOW_SIZE);
    const window = beatTape.slice(tStart, t);

    const hits   = window.filter(e => e.type === 'HIT').length;
    const misses = window.filter(e => e.type === 'MISS').length;
    const beats  = window.filter(e => e.type === 'BEAT' || e.type === 'ACCENT').length;
    const total  = hits + misses;

    return {
      density:       (hits + misses + beats) / WINDOW_SIZE,
      entropy:       total > 0 ? misses / total : 0,
      dominantVoice: hits > misses ? 'hit' : total === 0 ? 'idle' : 'miss',
    };
  }
}
