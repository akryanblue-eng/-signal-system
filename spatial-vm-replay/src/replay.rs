use crate::event::SpatialEvent;
use crate::machine;
use crate::state::TravelerState;
use sha2::{Digest, Sha256};

pub struct ReplayResult {
    /// Per-step commits: commits[0] = C0 (initial state), commits[n] = state after event n-1.
    pub commits: Vec<[u8; 32]>,
    /// Sequence commit: binds the full commit chain to a single hash.
    pub seq_commit: [u8; 32],
}

/// Checkpoint interval for sparse replay. Every 256th step is recorded.
/// Step 0 (initial state) is always recorded regardless.
pub const CHECKPOINT_INTERVAL: u64 = 256;

/// Pure checkpoint policy: returns true when step should produce a commit.
/// Deterministic and test-only-callable — no side effects.
pub fn should_checkpoint(step: u64) -> bool {
    step == 0 || step % CHECKPOINT_INTERVAL == 0
}

/// Replay events over initial state, producing a commit for each step including C0.
/// C0 = initial_state.canonical_commit() (before any event).
/// C_n = state_after_event_n.canonical_commit().
/// seq_commit = SHA256("DSVM0:SEQ:v1\0" || u32-BE(len) || C0 || C1 || ... || Cn).
pub fn replay(initial: TravelerState, events: &[SpatialEvent]) -> ReplayResult {
    let mut commits: Vec<[u8; 32]> = Vec::with_capacity(events.len() + 1);
    commits.push(initial.canonical_commit()); // C0

    let mut state = initial;
    for event in events {
        state = machine::apply(state, event);
        commits.push(state.canonical_commit());
    }

    let sc = seq_commit(&commits);
    ReplayResult { commits, seq_commit: sc }
}

/// Sparse replay: only records commits at checkpoint steps (every CHECKPOINT_INTERVAL steps).
/// C0 is always recorded. seq_commit covers only checkpoint commits, not all steps.
/// Use for long event streams where per-step commit storage is prohibitive.
pub fn replay_sparse(initial: TravelerState, events: &[SpatialEvent]) -> ReplayResult {
    let mut commits: Vec<[u8; 32]> = Vec::new();
    commits.push(initial.canonical_commit()); // C0 always recorded (step 0)

    let mut state = initial;
    for (i, event) in events.iter().enumerate() {
        state = machine::apply(state, event);
        let step = (i + 1) as u64;
        if should_checkpoint(step) {
            commits.push(state.canonical_commit());
        }
    }

    // Always include final state if not already a checkpoint step
    let final_step = events.len() as u64;
    if final_step > 0 && !should_checkpoint(final_step) {
        commits.push(state.canonical_commit());
    }

    let sc = seq_commit(&commits);
    ReplayResult { commits, seq_commit: sc }
}

/// Deterministic sequence commit over a commit chain.
/// Length-prefixed so an empty chain and a chain with one all-zero commit differ.
pub fn seq_commit(commits: &[[u8; 32]]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(b"DSVM0:SEQ:v1\0");
    h.update((commits.len() as u32).to_be_bytes());
    for c in commits {
        h.update(c);
    }
    h.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::event::SpatialEvent;

    #[test]
    fn empty_replay_produces_one_commit() {
        let r = replay(TravelerState::default(), &[]);
        assert_eq!(r.commits.len(), 1); // only C0
    }

    #[test]
    fn replay_is_deterministic() {
        let events = vec![
            SpatialEvent::EnterNode { node_id: "A".into() },
            SpatialEvent::EnterNode { node_id: "B".into() },
        ];
        let r1 = replay(TravelerState::default(), &events);
        let r2 = replay(TravelerState::default(), &events);
        assert_eq!(r1.seq_commit, r2.seq_commit);
        assert_eq!(r1.commits, r2.commits);
    }

    #[test]
    fn seq_commit_captures_history_not_just_final_state() {
        // A then B vs B then A — same final state, different histories → different seq_commits
        let ab = replay(TravelerState::default(), &[
            SpatialEvent::EnterNode { node_id: "A".into() },
            SpatialEvent::EnterNode { node_id: "B".into() },
        ]);
        let ba = replay(TravelerState::default(), &[
            SpatialEvent::EnterNode { node_id: "B".into() },
            SpatialEvent::EnterNode { node_id: "A".into() },
        ]);

        // Final commits are identical (BTreeSet is order-invariant)
        assert_eq!(ab.commits.last(), ba.commits.last());
        // But seq_commits differ (intermediate commits differ)
        assert_ne!(ab.seq_commit, ba.seq_commit);
    }

    #[test]
    fn empty_seq_differs_from_nonempty() {
        let empty = replay(TravelerState::default(), &[]);
        let one = replay(TravelerState::default(), &[
            SpatialEvent::EnterNode { node_id: "A".into() },
        ]);
        assert_ne!(empty.seq_commit, one.seq_commit);
    }

    // --- checkpoint policy tests ---

    #[test]
    fn checkpoint_policy_always_records_step_zero() {
        assert!(should_checkpoint(0));
    }

    #[test]
    fn checkpoint_policy_records_at_interval_multiples() {
        assert!(should_checkpoint(CHECKPOINT_INTERVAL));
        assert!(should_checkpoint(CHECKPOINT_INTERVAL * 2));
        assert!(should_checkpoint(CHECKPOINT_INTERVAL * 10));
    }

    #[test]
    fn checkpoint_policy_skips_non_multiples() {
        assert!(!should_checkpoint(1));
        assert!(!should_checkpoint(CHECKPOINT_INTERVAL - 1));
        assert!(!should_checkpoint(CHECKPOINT_INTERVAL + 1));
    }

    #[test]
    fn sparse_replay_always_includes_c0_and_final() {
        let events: Vec<SpatialEvent> = (0..5)
            .map(|i| SpatialEvent::EnterNode { node_id: format!("n{i}") })
            .collect();
        let r = replay_sparse(TravelerState::default(), &events);
        // 5 events, no checkpoints hit (all < 256), so C0 + final = 2 commits
        assert_eq!(r.commits.len(), 2);
    }

    #[test]
    fn sparse_replay_equals_full_replay_on_short_traces() {
        // For traces shorter than CHECKPOINT_INTERVAL, sparse records C0 + final.
        // Full replay records every step. seq_commits will differ (different chain lengths).
        // But final state (last commit) must be identical.
        let events = vec![
            SpatialEvent::EnterNode { node_id: "A".into() },
            SpatialEvent::ChooseAscension,
        ];
        let full = replay(TravelerState::default(), &events);
        let sparse = replay_sparse(TravelerState::default(), &events);
        assert_eq!(full.commits.last(), sparse.commits.last());
    }

    #[test]
    fn sparse_replay_is_deterministic() {
        let events = vec![
            SpatialEvent::EnterNode { node_id: "X".into() },
            SpatialEvent::DiscoverArtifact { artifact_id: "Y".into() },
        ];
        let r1 = replay_sparse(TravelerState::default(), &events);
        let r2 = replay_sparse(TravelerState::default(), &events);
        assert_eq!(r1.seq_commit, r2.seq_commit);
    }
}
