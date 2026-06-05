// ─── Types ─────────────────────────────────────────────────────────────────────

/**
 * Compressed outcome descriptor for a single behavioral branch.
 * Built from BehaviorCommit sequences — callers extract what they care about.
 */
export interface BranchOutcome {
  branchId:    string;
  parentId:    string | null;
  environment: string;
  finalScore:  number; // [0, 1] outcome quality
  stability:   number; // [0, 1] average stability over branch
  drift:       number; // [0, 1] average drift over branch
}

/** Synthesized behavioral directive extracted from a dominant cluster. */
export interface DominantPolicy {
  preferredEnvironment: string;
  stabilityBias:        number; // [0, 1] — average stability of dominant cluster
  driftTolerance:       number; // [0, 1] — average drift tolerance of dominant cluster
}

// ─── Scoring ───────────────────────────────────────────────────────────────────

/**
 * Composite quality score for a branch outcome.
 * Mirrors MetaPolicy logic: high score + stability + low drift.
 */
export function dominanceScore(b: BranchOutcome): number {
  return b.finalScore * 0.5 + b.stability * 0.3 + (1 - b.drift) * 0.2;
}

// ─── Clustering ────────────────────────────────────────────────────────────────

function quantize(x: number): number {
  return Math.floor(x * 10) / 10;
}

/**
 * Group branches by environment + quantized (drift, stability).
 * Coarse quantization (0.1 buckets) clusters behaviorally similar branches.
 */
export function clusterBranches(
  branches: BranchOutcome[],
): Map<string, BranchOutcome[]> {
  const clusters = new Map<string, BranchOutcome[]>();
  for (const b of branches) {
    const key = `${b.environment}:${quantize(b.drift)}:${quantize(b.stability)}`;
    const group = clusters.get(key) ?? [];
    group.push(b);
    clusters.set(key, group);
  }
  return clusters;
}

/**
 * Return the cluster with the highest average dominanceScore.
 * Returns null when no branches exist.
 */
export function extractDominant(
  clusters: Map<string, BranchOutcome[]>,
): BranchOutcome[] | null {
  let best:      BranchOutcome[] | null = null;
  let bestScore  = -Infinity;
  for (const group of clusters.values()) {
    const avg = group.reduce((s, b) => s + dominanceScore(b), 0) / group.length;
    if (avg > bestScore) {
      bestScore = avg;
      best      = group;
    }
  }
  return best;
}

/**
 * Compress a dominant cluster into an actionable policy directive.
 * `preferredEnvironment` is the plurality environment across the cluster.
 */
export function synthesizePolicy(cluster: BranchOutcome[]): DominantPolicy {
  const envCounts: Record<string, number> = {};
  for (const b of cluster) {
    envCounts[b.environment] = (envCounts[b.environment] ?? 0) + 1;
  }
  const dominantEnv = (Object.entries(envCounts)
    .sort((a, b) => b[1] - a[1])[0]!)[0];

  const n = cluster.length;
  return {
    preferredEnvironment: dominantEnv,
    stabilityBias:        cluster.reduce((s, b) => s + b.stability, 0) / n,
    driftTolerance:       cluster.reduce((s, b) => s + b.drift, 0) / n,
  };
}

/**
 * One-shot entry point: cluster → extract dominant → synthesize.
 * Returns null when there are no branches or all clusters are tied.
 */
export function distillDominantPolicy(
  branches: BranchOutcome[],
): DominantPolicy | null {
  if (branches.length === 0) return null;
  const clusters = clusterBranches(branches);
  const dominant = extractDominant(clusters);
  return dominant ? synthesizePolicy(dominant) : null;
}
