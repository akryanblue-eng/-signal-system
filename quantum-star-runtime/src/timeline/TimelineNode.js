// Deterministic state fingerprint — content-addressed, not time-addressed.
// Identifies ZapCore uniquely so branch divergence is detectable.
function stateChecksum(zapCore) {
  const z = zapCore.zap;
  return [zapCore.t, zapCore.score, zapCore.hitCount, zapCore.comboCount,
          z.force, z.flow, z.chaos, z.focus]
    .map(v => (typeof v === 'number' ? v.toFixed(8) : String(v)))
    .join(':');
}

let _seq = 0;

// TimelineNode = immutable causal state snapshot (checkpoint).
// Stores full runtime state so any branch can resume from here in O(1).
export function createTimelineNode({ t, tapeState, zapSnap, physicsSnap, visualSnap, windowSnap }) {
  return Object.freeze({
    id:          `n${_seq++}`,
    t,
    tapeState:   Object.freeze({ ...tapeState }),
    zapSnap,
    physicsSnap,
    visualSnap,
    windowSnap,
    checksum:    stateChecksum(zapSnap.core),
  });
}
