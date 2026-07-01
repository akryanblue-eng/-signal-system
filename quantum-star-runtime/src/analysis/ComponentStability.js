// ComponentStability.js
// Cross-run equivalence class stability measurement (Component Stability Function, CSF).
//
// A "run" is one EquivalenceGraph result at a point in time (one E-key press).
// Stability measures how consistently component signatures reappear across runs.
// Component identity is determined by CANONICAL STATE, not branch IDs — so the same
// logical cluster reappears even if branch IDs change between runs.
//
// Usage:
//   const result = csf([
//     { eg: equivGraph1, worlds: equivGraph1.worlds },
//     { eg: equivGraph2, worlds: equivGraph2.worlds },
//   ]);

import { canonicalize }   from '../timeline/CausalEquivalence.js';
import { makeProvenance } from './Provenance.js';

// Canonical component signature: hash of SORTED set of canonical branch states.
// Permutation-invariant — identity depends only on member state set, not ordering.
// Signature is derived from canonical state only — never from graph structure
// (that would create circularity: components define signatures, signatures define components).
export function componentSignature(component, worlds) {
  return [...component]
    .map(id => {
      const w = worlds.get(id);
      return w ? JSON.stringify(canonicalize(w.zap.core)) : '∅';
    })
    .sort()   // permutation invariance
    .join('|');
}

// Jaccard similarity between two sets of signatures (for drift matrix).
function jaccardSimilarity(sigsA, sigsB) {
  const setA = new Set(sigsA), setB = new Set(sigsB);
  let inter = 0;
  for (const s of setA) if (setB.has(s)) inter++;
  const union = setA.size + setB.size - inter;
  return union === 0 ? 1 : inter / union;
}

// CSF: Component Stability Function.
// runs: Array<{ eg: EquivalenceGraph result, worlds: Map<branchId, world> }>
// provenance: optional Provenance descriptor (from makeProvenance) — carried on result
// Requires ≥2 runs. Returns null if insufficient data.
export function componentStabilityFunction(runs, provenance = null) {
  if (!runs || runs.length < 2) return null;

  // Build (sig, size) lists per run
  const runSigLists = runs.map(({ eg, worlds }) =>
    eg.components.map(c => ({
      sig:  componentSignature(c, worlds ?? eg.worlds),
      size: c.size,
    }))
  );

  // Count how many runs contain each unique signature
  const sigPresence = new Map(); // sig → Set<runIndex>
  for (let r = 0; r < runSigLists.length; r++) {
    const seen = new Set();
    for (const { sig } of runSigLists[r]) {
      if (seen.has(sig)) continue;
      seen.add(sig);
      if (!sigPresence.has(sig)) sigPresence.set(sig, new Set());
      sigPresence.get(sig).add(r);
    }
  }

  const totalRuns = runs.length;
  const componentStabilities = [...sigPresence.entries()].map(([sig, presenceSet]) => ({
    signature:      sig,
    stability:      presenceSet.size / totalRuns,
    runCount:       presenceSet.size,
    // runPresenceMap[i] = true if this component's signature appeared in run i
    runPresenceMap: runs.map((_, i) => presenceSet.has(i)),
  }));

  const gss = componentStabilities.length > 0
    ? componentStabilities.reduce((s, c) => s + c.stability, 0) / componentStabilities.length
    : 0;

  // Emergent: present in later runs but not run 0 (may signal hidden state discovery)
  // Vanished: present in run 0 but not all later runs (may signal partition instability)
  const r1Sigs  = new Set(runSigLists[0]?.map(c => c.sig) ?? []);
  const vanished = componentStabilities.filter(c =>  r1Sigs.has(c.signature) && c.runCount < totalRuns);
  const emergent = componentStabilities.filter(c => !r1Sigs.has(c.signature));

  // Drift matrix: Jaccard similarity of component signature sets between all run pairs
  const sigsByRun  = runSigLists.map(list => list.map(c => c.sig));
  const driftMatrix = sigsByRun.map(sigsA =>
    sigsByRun.map(sigsB => +jaccardSimilarity(sigsA, sigsB).toFixed(4))
  );

  return Object.freeze({
    provenance:     provenance ?? makeProvenance({ mode: runs[0]?.eg?.mode }),
    totalRuns,
    uniqueComponents:     sigPresence.size,
    globalStabilityScore: +gss.toFixed(6),
    componentStabilities,
    emergentCount:  emergent.length,
    vanishedCount:  vanished.length,
    emergent,
    vanished,
    driftMatrix,    // N×N Jaccard similarity — visualize to see partition rigidity
  });
}
