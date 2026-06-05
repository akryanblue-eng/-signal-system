import { describe, it, expect } from 'vitest';
import { BehaviorRepository } from '../BehaviorRepository';
import { DEFAULT_PERFORMANCE_STATE } from '../../core/PerformanceState';
import { performanceReducer } from '../../core/runtime/performanceReducer';
import type { ReplayStepFn } from '../BehaviorRepository';

const s = DEFAULT_PERFORMANCE_STATE;

// Minimal step function for tests — applies a CHAOS_SPIKE and returns state
const chaosStep: ReplayStepFn = (state, _input) => {
  const stateAfter = performanceReducer(state, { type: 'CHAOS_SPIKE', amount: 0.1 });
  return { stateAfter, actions: [{ type: 'CHAOS_SPIKE', amount: 0.1 }], env: 'cinematic', score: 0.6 };
};

describe('BehaviorRepository — record & read', () => {
  it('starts with one main branch and no commits', () => {
    const repo = new BehaviorRepository();
    expect(repo.branchCount).toBe(1);
    expect(repo.commitCount).toBe(0);
  });

  it('record() adds a commit to the main branch', () => {
    const repo = new BehaviorRepository();
    repo.record({
      parentId: null, input: 'test',
      stateBefore: s, stateAfter: s,
      env: 'cinematic', policyEnv: 'cinematic', oracleEnv: 'cinematic',
      actions: [], score: 0.5,
    });
    expect(repo.commitCount).toBe(1);
    expect(repo.getMainBranch().commits).toHaveLength(1);
  });

  it('record() assigns unique IDs to consecutive commits', () => {
    const repo = new BehaviorRepository();
    const c1 = repo.record({ parentId: null, input: 'a', stateBefore: s, stateAfter: s, env: 'c', policyEnv: 'c', oracleEnv: 'c', actions: [], score: 0.5 });
    const c2 = repo.record({ parentId: c1.id, input: 'b', stateBefore: s, stateAfter: s, env: 'c', policyEnv: 'c', oracleEnv: 'c', actions: [], score: 0.5 });
    expect(c1.id).not.toBe(c2.id);
  });

  it('getCommit() retrieves a commit by ID', () => {
    const repo = new BehaviorRepository();
    const c = repo.record({ parentId: null, input: 'x', stateBefore: s, stateAfter: s, env: 'c', policyEnv: 'c', oracleEnv: 'c', actions: [], score: 0.5 });
    expect(repo.getCommit(c.id)).toEqual(c);
  });

  it('getCommit() returns undefined for unknown IDs', () => {
    expect(new BehaviorRepository().getCommit('nonexistent')).toBeUndefined();
  });
});

describe('BehaviorRepository — fork', () => {
  it('fork() from known commit creates a new branch', () => {
    const repo = new BehaviorRepository();
    const c = repo.record({ parentId: null, input: 'root', stateBefore: s, stateAfter: s, env: 'c', policyEnv: 'c', oracleEnv: 'c', actions: [], score: 0.5 });
    const branch = repo.fork(c.id);
    expect(branch).not.toBeNull();
    expect(repo.branchCount).toBe(2);
    expect(branch!.parentCommitId).toBe(c.id);
    expect(branch!.commits).toHaveLength(0);
  });

  it('fork() returns null for an unknown commit ID', () => {
    expect(new BehaviorRepository().fork('unknown')).toBeNull();
  });

  it('fork() from different commits creates independent branches', () => {
    const repo = new BehaviorRepository();
    const c1 = repo.record({ parentId: null, input: 'a', stateBefore: s, stateAfter: s, env: 'c', policyEnv: 'c', oracleEnv: 'c', actions: [], score: 0.5 });
    const c2 = repo.record({ parentId: c1.id, input: 'b', stateBefore: s, stateAfter: s, env: 'c', policyEnv: 'c', oracleEnv: 'c', actions: [], score: 0.5 });
    const b1 = repo.fork(c1.id)!;
    const b2 = repo.fork(c2.id)!;
    expect(b1.id).not.toBe(b2.id);
    expect(b1.parentCommitId).toBe(c1.id);
    expect(b2.parentCommitId).toBe(c2.id);
  });
});

describe('BehaviorRepository — replay', () => {
  it('replay() on unknown branch returns empty array', () => {
    const repo = new BehaviorRepository();
    expect(repo.replay('unknown', s, ['a'], chaosStep)).toHaveLength(0);
  });

  it('replay() creates one commit per input', () => {
    const repo = new BehaviorRepository();
    const c = repo.record({ parentId: null, input: 'root', stateBefore: s, stateAfter: s, env: 'c', policyEnv: 'c', oracleEnv: 'c', actions: [], score: 0.5 });
    const branch = repo.fork(c.id)!;
    const commits = repo.replay(branch.id, s, ['a', 'b', 'c'], chaosStep);
    expect(commits).toHaveLength(3);
    expect(branch.commits).toHaveLength(3);
  });

  it('replay() threads state through each step (chaos accumulates)', () => {
    const repo = new BehaviorRepository();
    const c = repo.record({ parentId: null, input: 'r', stateBefore: s, stateAfter: s, env: 'c', policyEnv: 'c', oracleEnv: 'c', actions: [], score: 0.5 });
    const branch = repo.fork(c.id)!;
    const commits = repo.replay(branch.id, s, ['x', 'y', 'z'], chaosStep);
    // chaos should increase each step
    expect(commits[1]!.stateBefore.chaos).toBeGreaterThan(commits[0]!.stateBefore.chaos);
  });

  it('replay() commits are retrievable by ID from global store', () => {
    const repo = new BehaviorRepository();
    const c = repo.record({ parentId: null, input: 'r', stateBefore: s, stateAfter: s, env: 'c', policyEnv: 'c', oracleEnv: 'c', actions: [], score: 0.5 });
    const branch = repo.fork(c.id)!;
    const commits = repo.replay(branch.id, s, ['a'], chaosStep);
    expect(repo.getCommit(commits[0]!.id)).toBeDefined();
  });

  it('replay() parentId chain links commits correctly', () => {
    const repo = new BehaviorRepository();
    const root = repo.record({ parentId: null, input: 'r', stateBefore: s, stateAfter: s, env: 'c', policyEnv: 'c', oracleEnv: 'c', actions: [], score: 0.5 });
    const branch = repo.fork(root.id)!;
    const commits = repo.replay(branch.id, s, ['a', 'b'], chaosStep);
    expect(commits[0]!.parentId).toBe(root.id);
    expect(commits[1]!.parentId).toBe(commits[0]!.id);
  });
});
