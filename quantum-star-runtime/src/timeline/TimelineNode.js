import { canonicalize } from './CausalEquivalence.js';

// Deterministic state fingerprint via canonical view — content-addressed, not time-addressed.
// hash(canonicalize(state)) — never hash(raw state) — so float ordering and key insertion
// order cannot cause divergence between node creation and later comparison.
export function stateChecksum(zapCore) {
  return JSON.stringify(canonicalize(zapCore));
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
