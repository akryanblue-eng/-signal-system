import { describe, it, expect } from 'vitest';
import {
  dominanceScore,
  clusterBranches,
  extractDominant,
  synthesizePolicy,
  distillDominantPolicy,
} from '../DominantTimeline';
import type { BranchOutcome } from '../DominantTimeline';

const mkBranch = (env: string, finalScore: number, stability: number, drift: number): BranchOutcome => ({
  branchId: `b-${Math.random()}`, parentId: null, environment: env, finalScore, stability, drift,
});

describe('dominanceScore', () => {
  it('returns 1 for perfect outcome', () => {
    expect(dominanceScore(mkBranch('c', 1, 1, 0))).toBeCloseTo(1);
  });

  it('returns 0 for worst outcome', () => {
    expect(dominanceScore(mkBranch('c', 0, 0, 1))).toBeCloseTo(0);
  });

  it('weighs finalScore most heavily (0.5)', () => {
    const highScore = mkBranch('c', 1.0, 0.5, 0.5);
    const highStab  = mkBranch('c', 0.5, 1.0, 0.5);
    expect(dominanceScore(highScore)).toBeGreaterThan(dominanceScore(highStab));
  });
});

describe('clusterBranches', () => {
  it('groups identical env+drift+stability into one cluster', () => {
    const branches = [
      mkBranch('cinematic', 0.8, 0.7, 0.1),
      mkBranch('cinematic', 0.9, 0.7, 0.1),
    ];
    const clusters = clusterBranches(branches);
    expect(clusters.size).toBe(1);
    expect([...clusters.values()][0]).toHaveLength(2);
  });

  it('separates branches from different environments', () => {
    const branches = [
      mkBranch('cinematic', 0.8, 0.7, 0.1),
      mkBranch('chaosJam',  0.8, 0.7, 0.1),
    ];
    expect(clusterBranches(branches).size).toBe(2);
  });

  it('separates branches with different quantized drift', () => {
    const branches = [
      mkBranch('cinematic', 0.8, 0.7, 0.1),
      mkBranch('cinematic', 0.8, 0.7, 0.5), // different drift bucket
    ];
    expect(clusterBranches(branches).size).toBe(2);
  });

  it('returns empty map for empty input', () => {
    expect(clusterBranches([]).size).toBe(0);
  });
});

describe('extractDominant', () => {
  it('returns null for an empty cluster map', () => {
    expect(extractDominant(new Map())).toBeNull();
  });

  it('returns the cluster with the highest average dominance score', () => {
    const good = [mkBranch('cinematic', 0.9, 0.9, 0.05)];
    const bad  = [mkBranch('chaosJam',  0.1, 0.1, 0.9)];
    const clusters = new Map([['good', good], ['bad', bad]]);
    const dominant = extractDominant(clusters);
    expect(dominant).toEqual(good);
  });
});

describe('synthesizePolicy', () => {
  it('extracts plurality environment', () => {
    const cluster = [
      mkBranch('cinematic', 0.8, 0.7, 0.1),
      mkBranch('cinematic', 0.9, 0.8, 0.1),
      mkBranch('chaosJam',  0.6, 0.4, 0.5),
    ];
    expect(synthesizePolicy(cluster).preferredEnvironment).toBe('cinematic');
  });

  it('averages stability across cluster', () => {
    const cluster = [
      mkBranch('c', 0.8, 0.6, 0.2),
      mkBranch('c', 0.8, 0.8, 0.2),
    ];
    expect(synthesizePolicy(cluster).stabilityBias).toBeCloseTo(0.7);
  });

  it('averages drift across cluster', () => {
    const cluster = [
      mkBranch('c', 0.8, 0.7, 0.2),
      mkBranch('c', 0.8, 0.7, 0.4),
    ];
    expect(synthesizePolicy(cluster).driftTolerance).toBeCloseTo(0.3);
  });
});

describe('distillDominantPolicy', () => {
  it('returns null for empty branch list', () => {
    expect(distillDominantPolicy([])).toBeNull();
  });

  it('returns a policy for a valid branch set', () => {
    const branches = [
      mkBranch('cinematic', 0.9, 0.8, 0.1),
      mkBranch('cinematic', 0.85, 0.75, 0.15),
      mkBranch('chaosJam',  0.4, 0.3, 0.6),
    ];
    const policy = distillDominantPolicy(branches);
    expect(policy).not.toBeNull();
    expect(policy!.preferredEnvironment).toBe('cinematic');
    expect(policy!.stabilityBias).toBeGreaterThan(0);
  });
});
