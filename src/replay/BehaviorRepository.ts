import type { PerformanceState } from '../core/PerformanceState';
import type { PerformanceAction } from '../core/runtime/PerformanceAction';

// ─── Types ─────────────────────────────────────────────────────────────────────

/** Immutable record of one step — the "git commit" object for behavior. */
export interface BehaviorCommit {
  id:          string;
  parentId:    string | null;
  input:       string;
  stateBefore: PerformanceState;
  stateAfter:  PerformanceState;
  env:         string;
  policyEnv:   string;
  oracleEnv:   string;
  actions:     PerformanceAction[];
  score:       number;
}

/**
 * An alternative timeline forked from a specific commit.
 * parentCommitId is where this branch diverged.
 */
export interface Branch {
  id:             string;
  parentCommitId: string | null;
  commits:        BehaviorCommit[];
}

/**
 * Caller-supplied execution function for branch replay.
 * Receives current state + intent text, returns everything needed for a commit.
 */
export type ReplayStepFn = (
  state: PerformanceState,
  input: string,
) => {
  stateAfter: PerformanceState;
  actions:    PerformanceAction[];
  env:        string;
  policyEnv?: string;
  oracleEnv?: string;
  score:      number;
};

// ─── ID generation ─────────────────────────────────────────────────────────────

let _seq = 0;
function nextId(prefix: string): string {
  return `${prefix}-${(++_seq).toString(36)}-${Date.now().toString(36)}`;
}

// ─── Repository ────────────────────────────────────────────────────────────────

/**
 * Git-inspired store for behavior commits and branches.
 *
 * Main branch is created automatically.  Use fork() to branch from any commit,
 * then replay() to simulate forward from that divergence point.
 */
export class BehaviorRepository {
  private commits:    Map<string, BehaviorCommit> = new Map();
  private branches:   Map<string, Branch>         = new Map();
  private mainId:     string;

  constructor() {
    this.mainId = 'main';
    this.branches.set(this.mainId, { id: this.mainId, parentCommitId: null, commits: [] });
  }

  // ── Write ──────────────────────────────────────────────────────────────────

  /**
   * Record a commit on the main branch.  The commit is also indexed by ID
   * so any branch can reference it as a fork point.
   */
  record(data: Omit<BehaviorCommit, 'id'>): BehaviorCommit {
    const commit: BehaviorCommit = { ...data, id: nextId('c') };
    this.commits.set(commit.id, commit);
    this.branches.get(this.mainId)!.commits.push(commit);
    return commit;
  }

  // ── Fork ───────────────────────────────────────────────────────────────────

  /**
   * Create a new branch diverging at commitId.
   * The branch starts empty — populate it via replay().
   * Returns null when commitId is not found.
   */
  fork(commitId: string): Branch | null {
    if (!this.commits.has(commitId)) return null;
    const branch: Branch = {
      id:             nextId('branch'),
      parentCommitId: commitId,
      commits:        [],
    };
    this.branches.set(branch.id, branch);
    return branch;
  }

  // ── Replay ─────────────────────────────────────────────────────────────────

  /**
   * Drive a branch forward by running stepFn for each input string.
   * Commits are created for each step and stored in the branch + global map.
   * Returns the generated commit sequence.
   */
  replay(
    branchId:     string,
    initialState: PerformanceState,
    inputs:       string[],
    stepFn:       ReplayStepFn,
  ): BehaviorCommit[] {
    const branch = this.branches.get(branchId);
    if (!branch) return [];

    let state        = initialState;
    let prevId: string | null = branch.parentCommitId;
    const generated: BehaviorCommit[] = [];

    for (const input of inputs) {
      const result = stepFn(state, input);
      const commit: BehaviorCommit = {
        id:          nextId('c'),
        parentId:    prevId,
        input,
        stateBefore: state,
        stateAfter:  result.stateAfter,
        env:         result.env,
        policyEnv:   result.policyEnv ?? result.env,
        oracleEnv:   result.oracleEnv ?? result.env,
        actions:     result.actions,
        score:       result.score,
      };
      this.commits.set(commit.id, commit);
      branch.commits.push(commit);
      generated.push(commit);
      state  = result.stateAfter;
      prevId = commit.id;
    }

    return generated;
  }

  // ── Read ───────────────────────────────────────────────────────────────────

  getCommit(id: string):       BehaviorCommit | undefined { return this.commits.get(id); }
  getBranch(id: string):       Branch         | undefined { return this.branches.get(id); }
  getMainBranch():             Branch                     { return this.branches.get(this.mainId)!; }
  get commitCount():           number                     { return this.commits.size; }
  get branchCount():           number                     { return this.branches.size; }
  listBranches():              Branch[]                   { return [...this.branches.values()]; }
}
