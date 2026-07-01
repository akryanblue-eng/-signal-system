// EquivalenceGraph.js
// Partition of branch endpoints under a parameterized equivalence mode.
//
// Operates over a FROZEN snapshot of branch IDs — build() captures branches at call time
// and does not observe the live graph during construction. This preserves transitivity
// validity: the edge set and components are stable because no new branch can arrive
// between edge (A,B) and edge (B,C) being computed.
//
// Comparison mode is explicit, not implicit. The same branch universe may induce
// different partitions under different modes — that divergence is itself the signal.
//
// Usage:
//   const ids = graph.getBranchIds();           // snapshot before calling build
//   const eg  = EquivalenceGraph.build(ids, graph, executor, tapes, targetT, { mode: 'canonical' });
//
// Violation taxonomy (A≡B, B≡C, but A≠C):
//   'granularity-mismatch'        — A and C are raw-identical but canonical disagrees;
//                                   canonical is operating at wrong resolution
//   'canonicalization-incomplete' — integer fields match but vectors diverge;
//                                   a state dimension is missing from the canonical view
//   'execution-divergence-fold'   — genuinely different terminal states; paths collapsed
//                                   to equivalent intermediates then diverged

import { equals, branchEvents }  from './CausalEquivalence.js';
import { makeProvenance }        from '../analysis/Provenance.js';

const CANONICALIZER_VERSION = 'v1';

export class EquivalenceGraph {

  // Build the partition. Synchronous, O(N²) edges + O(N³) transitivity check.
  // Practical for small N (up to ~30 branches). Document the bound if you scale this.
  static build(frozenBranchIds, graph, executor, tapes, targetT, options = {}) {
    const mode = options.mode ?? 'canonical';
    if (mode === 'semantic') {
      throw new Error('EquivalenceGraph: semantic mode is not yet implemented — equals.semantic returns null');
    }
    const canonicalizerVersion = options.canonicalizerVersion ?? CANONICALIZER_VERSION;

    // ── Step 1: execute all branches to targetT (frozen snapshot) ──────────────
    // Worlds are used for exact/canonical comparison and violation classification.
    // Events are used for structural comparison.
    const worlds    = new Map();
    const eventsMap = new Map();
    for (const id of frozenBranchIds) {
      try {
        worlds.set(id, executor.executeBranch(id, tapes, targetT));
      } catch (_) {
        worlds.set(id, null);
      }
      eventsMap.set(id, branchEvents(id, graph, tapes, targetT));
    }

    // Only compare branches that produced a valid world
    const live = frozenBranchIds.filter(id => worlds.get(id) !== null);

    // ── Step 2: build edge set (symmetric adjacency) ───────────────────────────
    const edgeSet = new Map(live.map(id => [id, new Set()]));

    const compare = (a, b) => {
      if (mode === 'structural') {
        const ea = eventsMap.get(a), eb = eventsMap.get(b);
        return !!(ea && eb && equals.structural(ea, eb));
      }
      const wa = worlds.get(a), wb = worlds.get(b);
      return !!(wa && wb && equals[mode](wa, wb));
    };

    for (let i = 0; i < live.length; i++) {
      for (let j = i + 1; j < live.length; j++) {
        if (compare(live[i], live[j])) {
          edgeSet.get(live[i]).add(live[j]);
          edgeSet.get(live[j]).add(live[i]);
        }
      }
    }

    // ── Step 3: connected components (BFS) ─────────────────────────────────────
    const components = [];
    const visited    = new Set();
    for (const start of live) {
      if (visited.has(start)) continue;
      const component = new Set();
      const queue     = [start];
      while (queue.length) {
        const curr = queue.shift();
        if (visited.has(curr)) continue;
        visited.add(curr);
        component.add(curr);
        for (const neighbor of edgeSet.get(curr) ?? []) {
          if (!visited.has(neighbor)) queue.push(neighbor);
        }
      }
      components.push(component);
    }

    // ── Step 4: transitivity violation scan — O(N³) ────────────────────────────
    // Scans all triples where A≡B and B≡C to check A≡C.
    // Violations are diagnostic signals, not errors — the system continues.
    const violations = [];
    for (let i = 0; i < live.length; i++) {
      for (let j = i + 1; j < live.length; j++) {
        if (!edgeSet.get(live[i]).has(live[j])) continue; // A≡B?
        for (let k = j + 1; k < live.length; k++) {
          if (!edgeSet.get(live[j]).has(live[k])) continue; // B≡C?
          if (!edgeSet.get(live[i]).has(live[k])) {         // A≠C → violation
            violations.push({
              a: live[i], b: live[j], c: live[k],
              type: classifyViolation(worlds.get(live[i]), worlds.get(live[k]), mode),
            });
          }
        }
      }
    }

    // ── Step 5: exploration pressure φ = D × log(1 + E) ──────────────────────
    // D = average replay window across live branches (structural depth)
    // E = beat-tape event density (events per second, measure of perturbation)
    // gss (single-run proxy) = equivalence compression rate under this mode
    const replayWindows = live.map(id => {
      const branch    = graph.getBranch(id);
      const startNode = graph.getNode(branch?.fromNodeId);
      return startNode ? Math.max(0, targetT - startNode.t) : 0;
    });
    const D   = replayWindows.length > 0 ? replayWindows.reduce((s, v) => s + v, 0) / replayWindows.length : 0;
    const E   = targetT > 0 ? (tapes.beat?.length ?? 0) / targetT : 0;
    const phi = D * Math.log(1 + E);
    // gss: fraction of live branches that share a component with at least one other branch.
    // 0 = all singletons (equivalence does nothing), 1 = all branches in one component.
    const gss = live.length > 0 ? 1 - components.length / live.length : 0;

    const provenance = makeProvenance({ mode, canonicalizerVersion });

    return Object.freeze({
      mode,
      canonicalizerVersion,
      provenance,    // immutable descriptor — attribute metric shifts to specific change
      targetT,
      branchCount:    frozenBranchIds.length,
      liveCount:      live.length,
      componentCount: components.length,
      phi,           // exploration pressure — used by PhaseBoundaryDetector
      gss,           // single-run stability proxy — used by SAL data collection
      worlds,        // Map<branchId, world> — exposed for ComponentStability signatures
      edgeSet,       // Map<branchId, Set<branchId>> — symmetric adjacency list
      components,    // Array<Set<branchId>> — partition of live branches
      violations,    // Array<{a, b, c, type}> — transitivity violations (diagnostic)
    });
  }
}

// Classify a transitivity violation (A≡B, B≡C, A≠C) by heuristic state comparison.
// Uses worlds for A and C regardless of primary mode — classification always works at
// the state level so all three violation types remain distinguishable.
function classifyViolation(wa, wc, mode) {
  if (!wa || !wc) return 'execution-error';

  // If raw fields are identical but the equivalence fn says they differ →
  // the canonical view is at wrong resolution or has a bug in the mode logic
  if (equals.exact(wa, wc)) return 'granularity-mismatch';

  // If integer fields match (same game outcome) but floats/vectors differ →
  // a continuous dimension escaped canonicalization
  const ca = wa.zap.core, cc = wc.zap.core;
  if (ca.score === cc.score && ca.hitCount === cc.hitCount && ca.comboCount === cc.comboCount) {
    return 'canonicalization-incomplete';
  }

  // States are genuinely different — paths converged at some intermediate then diverged
  return 'execution-divergence-fold';
}
