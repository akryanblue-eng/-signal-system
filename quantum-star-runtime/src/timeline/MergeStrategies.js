// v1: comparison and ordering strategies (read-only branches).
// v2 will add write-enabled merge: combine tape segments into a new writable branch.

export const MergeStrategies = {
  // Canonical: merge events from two beat tape segments by time order.
  // Ties broken by tape priority (beat always dominates).
  canonical(beatEventsA, beatEventsB) {
    const tagged = [
      ...beatEventsA.map(e => ({ ...e, _src: 'a' })),
      ...beatEventsB.map(e => ({ ...e, _src: 'b' })),
    ];
    return tagged.sort((x, y) => x.t - y.t || (x._src === 'a' ? -1 : 1));
  },

  // latestWins: for same type at same t, the higher-seq event wins.
  latestWins(eventsA, eventsB) {
    const map = new Map();
    for (const e of [...eventsA, ...eventsB].sort((a, b) => a.t - b.t)) {
      const key = `${e.type}:${e.t.toFixed(6)}`;
      if (!map.has(key) || e.seq > map.get(key).seq) map.set(key, e);
    }
    return [...map.values()].sort((a, b) => a.t - b.t);
  },

  // fieldBlend: interpolate two ZapSnap zap vectors (preview of Zap v2).
  fieldBlend(zapSnapA, zapSnapB, alpha = 0.5) {
    const a = zapSnapA.core.zap, b = zapSnapB.core.zap;
    return {
      force: a.force * (1 - alpha) + b.force * alpha,
      flow:  a.flow  * (1 - alpha) + b.flow  * alpha,
      chaos: a.chaos * (1 - alpha) + b.chaos * alpha,
      focus: a.focus * (1 - alpha) + b.focus * alpha,
    };
  },
};
