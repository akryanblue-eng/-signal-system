import type { LatentState } from '../types/latent';

/** A compressed species cluster extracted from a window of latent states. */
export interface SpeciesNode {
  id: string;
  centroid: LatentState;  // geometric centroid of the cluster
  confidence: number;      // [0, 1]
  memberCount: number;
}

/**
 * Deterministic geometric clustering of LatentState windows.
 * Pure function — same input always produces same output.
 * No ML, no stochastic behavior.
 */
export class ClusterEngine {
  private readonly threshold: number;

  constructor(stabilityThreshold = 0.15) {
    this.threshold = stabilityThreshold;
  }

  cluster(states: LatentState[]): SpeciesNode[] {
    if (states.length === 0) return [];

    // Simple single-pass clustering by stability proximity
    const clusters: SpeciesNode[] = [];
    let clusterIdx = 0;

    for (const state of states) {
      const existing = clusters.find(c =>
        Math.abs(c.centroid.stability - state.stability) < this.threshold &&
        Math.abs(c.centroid.energy - state.energy) < this.threshold,
      );

      if (existing) {
        // Update centroid incrementally
        const n = existing.memberCount + 1;
        existing.centroid = lerpState(existing.centroid, state, 1 / n);
        existing.memberCount = n;
        existing.confidence = Math.min(1, n / 10);
      } else {
        clusters.push({
          id: `cluster_${clusterIdx++}`,
          centroid: { ...state },
          confidence: 0.1,
          memberCount: 1,
        });
      }
    }

    return clusters;
  }
}

function lerpState(a: LatentState, b: LatentState, t: number): LatentState {
  return {
    drift_mean:       a.drift_mean       + (b.drift_mean       - a.drift_mean)       * t,
    energy:           a.energy           + (b.energy           - a.energy)           * t,
    stability:        a.stability        + (b.stability        - a.stability)        * t,
    adaptation:       a.adaptation       + (b.adaptation       - a.adaptation)       * t,
    cumulative_drift: a.cumulative_drift + (b.cumulative_drift - a.cumulative_drift) * t,
  };
}
