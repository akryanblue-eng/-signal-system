import { MultiTapeBus } from '../core/MultiTapeBus.js';

// BranchExecutor: runs a branch as an independent execution context.
// Each execution uses a fresh MultiTapeBus loaded from the branch's start checkpoint.
// Does NOT touch the live bus — branches are isolated, read-only, deterministic.
export class BranchExecutor {
  #graph;

  constructor(graph) { this.#graph = graph; }

  // Execute branchId from its start checkpoint to targetT.
  // Returns the world snapshot at targetT.
  executeBranch(branchId, tapes, targetT, frameDt = 1 / 60) {
    const branch    = this.#graph.getBranch(branchId);
    const startNode = this.#graph.getNode(branch?.fromNodeId);
    if (!startNode) throw new Error(`No start node for branch ${branchId}`);

    const replayBus = new MultiTapeBus();
    replayBus.loadSnapshot(startNode);   // O(1) checkpoint load

    let tCursor = startNode.t;
    let world   = null;
    while (tCursor < targetT) {
      const dt = Math.min(frameDt, targetT - tCursor);
      world    = replayBus.stepReplay(dt, tCursor, tapes);
      tCursor += dt;
    }
    return world;
  }

  // Run two branches to the same time and return a state comparison.
  // Proves: divergence is detectable and bounded by checkpoint distance.
  compareBranches(branchIdA, branchIdB, tapes, targetT) {
    const worldA = this.executeBranch(branchIdA, tapes, targetT);
    const worldB = this.executeBranch(branchIdB, tapes, targetT);
    if (!worldA || !worldB) return null;

    const za = worldA.zap.core, zb = worldB.zap.core;
    return {
      atTime:    targetT,
      branches:  { a: branchIdA, b: branchIdB },
      identical: za.score === zb.score && za.hitCount === zb.hitCount,
      zap: {
        force: { a: za.zap.force, b: zb.zap.force, delta: zb.zap.force - za.zap.force },
        flow:  { a: za.zap.flow,  b: zb.zap.flow,  delta: zb.zap.flow  - za.zap.flow  },
        chaos: { a: za.zap.chaos, b: zb.zap.chaos, delta: zb.zap.chaos - za.zap.chaos },
        focus: { a: za.zap.focus, b: zb.zap.focus, delta: zb.zap.focus - za.zap.focus },
      },
      score: { a: za.score,    b: zb.score,    delta: zb.score    - za.score    },
      hits:  { a: za.hitCount, b: zb.hitCount, delta: zb.hitCount - za.hitCount },
    };
  }
}
