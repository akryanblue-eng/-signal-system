import { createTimelineNode } from './TimelineNode.js';

let _branchSeq = 0;
let _edgeSeq   = 0;

// TimelineGraph: DAG of causal state snapshots.
// Nodes = checkpoints. Edges = deterministic transitions. Branches = named head pointers.
// Invariant: branches are immutable after creation — only new nodes extend the graph.
export class TimelineGraph {
  #nodes    = new Map(); // nodeId → TimelineNode
  #edges    = new Map(); // edgeId → TimelineEdge
  #branches = new Map(); // branchId → { headNodeId, fromNodeId, name }

  // Snapshot current world into a node and register it.
  createNode(t, world, tapes) {
    const node = createTimelineNode({
      t,
      tapeState: {
        beat:    { length: tapes.beat.length },
        physics: { length: tapes.physics.length },
        visual:  { length: tapes.visual.length },
        meta:    { length: tapes.meta.length },
      },
      zapSnap:     world.zap,
      physicsSnap: world.physics,
      visualSnap:  world.visual,
      windowSnap:  world.window,
    });
    this.#nodes.set(node.id, node);
    return node;
  }

  createEdge(fromId, toId, type, provenance = {}) {
    const edge = Object.freeze({
      id: `e${_edgeSeq++}`,
      from: fromId,
      to:   toId,
      type,        // 'live' | 'seek' | 'transform' | 'merge'
      provenance,
    });
    this.#edges.set(edge.id, edge);
    return edge;
  }

  // Create a named branch whose head starts at an existing node.
  createBranch(fromNodeId, name = `branch-${_branchSeq}`) {
    if (!this.#nodes.has(fromNodeId)) throw new Error(`Node ${fromNodeId} not found`);
    const id = `b${_branchSeq++}`;
    this.#branches.set(id, { headNodeId: fromNodeId, fromNodeId, name });
    return id;
  }

  // Advance a branch head to a new node, recording the transition edge.
  advanceBranch(branchId, newNodeId, edgeType = 'live', provenance = {}) {
    const branch = this.#branches.get(branchId);
    if (!branch) throw new Error(`Branch ${branchId} not found`);
    const edge = this.createEdge(branch.headNodeId, newNodeId, edgeType, provenance);
    this.#branches.set(branchId, { ...branch, headNodeId: newNodeId });
    return edge;
  }

  // Nearest checkpoint node at or before time t — O(checkpointCount), not O(eventCount).
  getNearestNodeBefore(t) {
    let nearest = null;
    for (const node of this.#nodes.values()) {
      if (node.t <= t && (!nearest || node.t > nearest.t)) nearest = node;
    }
    return nearest;
  }

  // State diff between two nodes.
  diff(nodeIdA, nodeIdB) {
    const a = this.#nodes.get(nodeIdA);
    const b = this.#nodes.get(nodeIdB);
    if (!a || !b) return null;
    const za = a.zapSnap.core, zb = b.zapSnap.core;
    return {
      tDelta:        b.t - a.t,
      checksumMatch: a.checksum === b.checksum,
      zap: {
        force: zb.zap.force - za.zap.force,
        flow:  zb.zap.flow  - za.zap.flow,
        chaos: zb.zap.chaos - za.zap.chaos,
        focus: zb.zap.focus - za.zap.focus,
      },
      score: zb.score    - za.score,
      hits:  zb.hitCount - za.hitCount,
    };
  }

  getNode(id)       { return this.#nodes.get(id); }
  getBranch(id)     { return this.#branches.get(id); }
  getBranchHead(id) {
    const b = this.#branches.get(id);
    return b ? this.#nodes.get(b.headNodeId) : null;
  }

  // Snapshot all branch IDs at this moment — returns a plain Array (not a live view).
  // Callers must take this snapshot before passing to EquivalenceGraph.build() so
  // graph mutations during construction cannot affect the result.
  getBranchIds()    { return [...this.#branches.keys()]; }

  get nodeCount()   { return this.#nodes.size; }
  get branchCount() { return this.#branches.size; }

  // Console-friendly status summary.
  status() {
    const out = {};
    for (const [id, branch] of this.#branches) {
      const head = this.#nodes.get(branch.headNodeId);
      out[id] = { name: branch.name, headT: head?.t.toFixed(2), checksum: head?.checksum };
    }
    return out;
  }
}
