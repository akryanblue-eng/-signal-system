// CausalEquivalence.js
// Canonical state equivalence for replay verification.
//
// Canonicalization = projection into comparison space.
// Raw state is NEVER mutated — canonical view is always derived.
// Separating these preserves reversibility in the debugging model.
//
// Three orthogonal axes — each answers exactly one question, never reused outside its domain:
//
//   exact      → bit-identical raw field comparison (debugging, regression)
//   canonical  → normalized state equivalence (replay verification)
//   structural → event type + tape shape (execution path comparison)
//   semantic   → causal trace equivalence (explicitly deferred — undefined until
//                causal invertibility is formally specified; returns null, not false)

const STATE_PRECISION  = 8; // toFixed(8) — sub-ms stability for state vectors
const TIMING_PRECISION = 2; // toFixed(2) — 10ms floor, rhythm-preserving, drift-immune

// Pure projection of zapCore into comparison space.
// Keys in strict alphabetical order; floats normalized to STATE_PRECISION.
// Raw zapCore is unchanged — this produces a derived view, not a mutation.
export function canonicalize(zapCore) {
  const z = zapCore.zap;
  // Key order enforced: comboCount < hitCount < score < t < zap
  // zap sub-keys:       chaos < flow < focus < force
  return {
    comboCount: zapCore.comboCount,
    hitCount:   zapCore.hitCount,
    score:      zapCore.score,
    t:          +zapCore.t.toFixed(STATE_PRECISION),
    zap: {
      chaos: +z.chaos.toFixed(STATE_PRECISION),
      flow:  +z.flow.toFixed(STATE_PRECISION),
      focus: +z.focus.toFixed(STATE_PRECISION),
      force: +z.force.toFixed(STATE_PRECISION),
    },
  };
}

// Relative-timing fingerprint of an event sequence.
// Retains causal shape only — drops absolute t, seq, velocity, id, key.
// relDt is relative to previous event of the same type; null for the first.
function causalFingerprint(events) {
  const lastByType = {};
  return events.map(e => {
    const prev  = lastByType[e.type];
    const relDt = prev !== undefined
      ? +(e.t - prev).toFixed(TIMING_PRECISION)
      : null;
    lastByType[e.type] = e.t;
    // Fixed key order: relDt < tape < type
    return { relDt, tape: e.tape ?? 'beat', type: e.type };
  });
}

export const equals = {
  // exact: raw field comparison — bit-identical check for debugging and regression.
  // Will detect float drift between replay sessions; intentionally strict.
  // Do NOT use for general replay verification — use canonical instead.
  exact(worldA, worldB) {
    const a = worldA.zap.core, b = worldB.zap.core;
    return a.t         === b.t         &&
           a.score     === b.score     &&
           a.hitCount  === b.hitCount  &&
           a.comboCount=== b.comboCount&&
           a.zap.force === b.zap.force &&
           a.zap.flow  === b.zap.flow  &&
           a.zap.chaos === b.zap.chaos &&
           a.zap.focus === b.zap.focus;
  },

  // canonical: canonicalized state equivalence — for replay verification.
  // Safe across: float drift, JS key insertion-order variance, metadata differences.
  // Explicitly scoped: "canonical state equivalence for replay verification."
  // Does NOT claim to define causal sameness.
  canonical(worldA, worldB) {
    return JSON.stringify(canonicalize(worldA.zap.core))
        === JSON.stringify(canonicalize(worldB.zap.core));
  },

  // structural: event type + tape sequence only.
  // Ignores all state values and timing magnitudes; verifies execution path shape matches.
  structural(eventsA, eventsB) {
    if (eventsA.length !== eventsB.length) return false;
    const fpA = causalFingerprint(eventsA);
    const fpB = causalFingerprint(eventsB);
    return fpA.every((a, i) => a.type === fpB[i].type && a.tape === fpB[i].tape);
  },

  // semantic: causal trace comparison — explicitly deferred.
  // Requires formal specification of causal invertibility before implementation.
  // Returns null (not false) — the question is undefined, not answered negatively.
  semantic(_a, _b) { return null; },
};

// Extract beat tape events for a branch's execution window with tape provenance attached.
// Used to feed structural comparison with branch-scoped event slices.
export function branchEvents(branchId, graph, tapes, targetT) {
  const branch    = graph.getBranch(branchId);
  const startNode = graph.getNode(branch?.fromNodeId);
  if (!startNode) return [];
  return tapes.beat.slice(startNode.t, targetT).map(e => ({ ...e, tape: 'beat' }));
}
