// Oracle evidence ledger — machine-readable baseline.
//
// Row 1   | Valid input -> deterministic reduction | state_hash STABLE | frontier STABLE | prefix_hash STABLE
// Row 1b  | Invalid input -> non-admission         | state_hash STABLE | frontier STABLE | prefix_hash STABLE
// Row 2A  | Readiness boundary (schedule-sensitive)| frontier FROZEN   | readiness STABLE
// Row 2B  | Interleaving invariance (commutativity)| ingestion order   | ack order       | K-merge order
//
// Row 1 / Row 1b / Row 2A / Row 2B are frozen; do not modify existing tests in this file.
// Row 3 (monotonicity / drift) is the next target.

use signal_system::codec::{decode, encode};
use signal_system::event::Event;
use signal_system::index::{sha256_event_hash, Cci};
use signal_system::ingress::{ExecutionPrefix, KnowledgeState, StagingBuffer};
use signal_system::kernel::{compile, genesis};

fn node(id: u8) -> [u8; 16] { [id; 16] }

// --- KernelSnapshot ---

#[derive(Debug, PartialEq, Eq)]
struct KernelSnapshot {
    state_hash:  [u8; 32],
    frontier:    Option<Cci>,
    prefix_hash: [u8; 32],
}

// Derive a KernelSnapshot from an ExecutionPrefix.
//
// state_hash  : compiled from genesis through the ordered prefix events.
// frontier    : max CCI in the prefix (None iff empty).
// prefix_hash : SHA-256 of the concatenated canonical bytes in CCI order.
//               Digest rather than structural equality; order-sensitive.
fn snapshot(prefix: &ExecutionPrefix) -> KernelSnapshot {
    let events: Vec<Event> = prefix.events.iter()
        .map(|ie| decode(&ie.canonical_bytes).expect("prefix contains only valid events"))
        .collect();
    let compiled = compile(genesis(), events);

    let mut combined: Vec<u8> = Vec::new();
    for ie in &prefix.events {
        combined.extend_from_slice(&ie.canonical_bytes);
    }
    let prefix_hash = sha256_event_hash(&combined);

    KernelSnapshot { state_hash: compiled.state_hash, frontier: prefix.frontier, prefix_hash }
}

// Convenience: build a fully-acknowledged KnowledgeState from raw event bytes.
fn ks_complete(event_bytes: &[Vec<u8>]) -> KnowledgeState {
    let mut ks = KnowledgeState::new(node(1), [node(1)]);
    for (tick, bytes) in event_bytes.iter().enumerate() {
        let hash = sha256_event_hash(bytes);
        ks.ingest(bytes.clone(), tick as u64, node(1));
        ks.acknowledge(hash, node(1));
    }
    ks
}

// -----------------------------------------------------------------------
// Row 1: Valid input -> deterministic reduction
// -----------------------------------------------------------------------

#[test]
fn row1_identical_events_produce_identical_snapshot() {
    let bytes = vec![
        encode(&Event::Create { entity_id: 1, kind: 5 }),
        encode(&Event::Update { entity_id: 1, field: 0, value: 42 }),
        encode(&Event::Commit { entity_id: 1 }),
    ];
    let snap_a = snapshot(&ks_complete(&bytes).try_advance(true).expect("must succeed"));
    let snap_b = snapshot(&ks_complete(&bytes).try_advance(true).expect("must succeed"));
    assert_eq!(snap_a, snap_b);
}

#[test]
fn row1_different_event_sequences_produce_different_snapshots() {
    let bytes_a = vec![encode(&Event::Create { entity_id: 1, kind: 5 })];
    let bytes_b = vec![encode(&Event::Create { entity_id: 2, kind: 5 })];
    let snap_a = snapshot(&ks_complete(&bytes_a).try_advance(true).expect("must succeed"));
    let snap_b = snapshot(&ks_complete(&bytes_b).try_advance(true).expect("must succeed"));
    assert_ne!(snap_a, snap_b);
}

#[test]
fn row1_snapshot_is_stable_across_repeated_advance() {
    let bytes = vec![encode(&Event::Create { entity_id: 1, kind: 0 })];
    let mut ks = ks_complete(&bytes);
    let snap_first  = snapshot(&ks.try_advance(true).expect("first advance must succeed"));
    let snap_second = snapshot(&ks.try_advance(true).expect("second advance must succeed"));
    assert_eq!(snap_first, snap_second,
        "snapshot must be stable: re-deriving the same prefix yields the same digest");
}

#[test]
fn row1_event_order_is_reflected_in_prefix_hash() {
    // Two different insertion orders for the same tick-1 and tick-2 events.
    // CCI ordering normalizes them — prefix_hash must be identical regardless of arrival order.
    let e1 = encode(&Event::Create { entity_id: 1, kind: 0 });
    let e2 = encode(&Event::Create { entity_id: 2, kind: 0 });

    let mut ks_ab = KnowledgeState::new(node(1), [node(1)]);
    let h1 = sha256_event_hash(&e1);
    let h2 = sha256_event_hash(&e2);
    ks_ab.ingest(e1.clone(), 1, node(1));
    ks_ab.ingest(e2.clone(), 2, node(1));
    ks_ab.acknowledge(h1, node(1));
    ks_ab.acknowledge(h2, node(1));

    let mut ks_ba = KnowledgeState::new(node(1), [node(1)]);
    ks_ba.ingest(e2.clone(), 2, node(1));
    ks_ba.ingest(e1.clone(), 1, node(1));
    ks_ba.acknowledge(h1, node(1));
    ks_ba.acknowledge(h2, node(1));

    let snap_ab = snapshot(&ks_ab.try_advance(true).expect("must succeed"));
    let snap_ba = snapshot(&ks_ba.try_advance(true).expect("must succeed"));
    assert_eq!(snap_ab, snap_ba,
        "CCI ordering must normalize arrival order: snapshots must converge");
}

// -----------------------------------------------------------------------
// Row 1b: Invalid input -> non-admission
// -----------------------------------------------------------------------

// Core property: invalid bytes do not mutate state_hash, frontier, or prefix_hash.
#[test]
fn row1b_invalid_bytes_do_not_mutate_snapshot() {
    let valid  = encode(&Event::Commit { entity_id: 1 });
    let invalid = b"garbage bytes - fail pass 0 decode".to_vec();
    let valid_hash = sha256_event_hash(&valid);

    let mut ks_clean = KnowledgeState::new(node(1), [node(1)]);
    ks_clean.ingest(valid.clone(), 1, node(1));
    ks_clean.acknowledge(valid_hash, node(1));
    let snap_clean = snapshot(&ks_clean.try_advance(true).expect("must succeed"));

    let mut ks_dirty = KnowledgeState::new(node(1), [node(1)]);
    ks_dirty.ingest(valid, 1, node(1));
    ks_dirty.ingest(invalid, 2, node(1)); // invalid — not acknowledged
    ks_dirty.acknowledge(valid_hash, node(1));
    let snap_dirty = snapshot(&ks_dirty.try_advance(true).expect("invalid bytes must not block"));

    assert_eq!(snap_clean, snap_dirty,
        "state_hash, frontier, and prefix_hash must be identical: invalid bytes are non-admitted");
}

// State mutation is absent: injecting invalid bytes after a successful advance
// must not change the snapshot on the next advance.
#[test]
fn row1b_state_mutation_absent_after_invalid_inject() {
    let valid = encode(&Event::Create { entity_id: 1, kind: 0 });
    let valid_hash = sha256_event_hash(&valid);

    let mut ks = KnowledgeState::new(node(1), [node(1)]);
    ks.ingest(valid, 1, node(1));
    ks.acknowledge(valid_hash, node(1));

    let snap_before = snapshot(&ks.try_advance(true).expect("must succeed"));

    ks.ingest(b"invalid payload - must not be admitted".to_vec(), 99, node(1));

    let snap_after = snapshot(&ks.try_advance(true).expect("must still succeed"));

    assert_eq!(snap_before, snap_after,
        "state mutation must be absent: invalid bytes injected after advance do not alter state");
}

// Frontier mutation is absent.
#[test]
fn row1b_frontier_mutation_absent() {
    let valid = encode(&Event::Create { entity_id: 1, kind: 0 });
    let valid_hash = sha256_event_hash(&valid);

    let mut ks = KnowledgeState::new(node(1), [node(1)]);
    ks.ingest(valid, 1, node(1));
    ks.acknowledge(valid_hash, node(1));

    let frontier_before = ks.try_advance(true).expect("must succeed").frontier;

    ks.ingest(b"frontier must not move from invalid".to_vec(), 9999, node(1));

    let frontier_after = ks.try_advance(true).expect("must still succeed").frontier;

    assert_eq!(frontier_before, frontier_after,
        "frontier mutation must be absent: invalid bytes with higher tick must not advance frontier");
}

// Decode failures are non-blocking and accurately reported.
#[test]
fn row1b_decode_failures_reported_without_blocking() {
    let valid   = encode(&Event::Commit { entity_id: 1 });
    let invalid = b"non-decodable payload".to_vec();
    let valid_hash   = sha256_event_hash(&valid);
    let invalid_hash = sha256_event_hash(&invalid);

    let mut ks = KnowledgeState::new(node(1), [node(1)]);
    ks.ingest(valid, 1, node(1));
    ks.ingest(invalid, 2, node(1));
    ks.acknowledge(valid_hash, node(1));

    let prefix = ks.try_advance(true).expect("must succeed despite invalid entry");

    assert_eq!(prefix.events.len(), 1, "only the valid event must be admitted");
    assert!(prefix.decode_failures.contains(&invalid_hash),
        "invalid hash must be reported in decode_failures");
}

// Invalid bytes are excluded from the C predicate: they cannot block admission.
// (The C predicate is evaluated over valid entries only.)
#[test]
fn row1b_c_predicate_ignores_invalid_entries() {
    let valid   = encode(&Event::Commit { entity_id: 1 });
    let invalid = b"not a valid event".to_vec();
    let valid_hash = sha256_event_hash(&valid);
    // invalid_hash is never acknowledged — but that must not cause Incomplete

    let mut ks = KnowledgeState::new(node(1), [node(1)]);
    ks.ingest(valid, 1, node(1));
    ks.ingest(invalid, 2, node(1));
    ks.acknowledge(valid_hash, node(1));

    assert!(ks.try_advance(true).is_ok(),
        "C predicate must evaluate only valid entries; unacknowledged invalid hash must not block");
}

// -----------------------------------------------------------------------
// Row 2A: Readiness Boundary (schedule-sensitive)
// -----------------------------------------------------------------------
//
// Property: while C = bot (stable=false OR partial acks), the observable
// state — frontier, readiness — is frozen.
//
// "Readiness" = try_advance(stable).is_ok().
// Invariant form: assert_eq!(ready_before, ready_after) when preconditions
// have not changed — not assert!(!ready), which bakes in an assumed initial value.
//
// Verified:
//   frontier FROZEN  : failed advance must not mutate ks.frontier
//   readiness STABLE : same preconditions -> same readiness result (deterministic probe)
//   condition boundary: readiness flips exactly when last blocking condition is resolved

// stable=false prevents advance regardless of ack completeness.
#[test]
fn row2a_unstable_flag_prevents_advance() {
    let bytes = encode(&Event::Create { entity_id: 1, kind: 0 });
    let hash  = sha256_event_hash(&bytes);

    let mut ks = KnowledgeState::new(node(1), [node(1)]);
    ks.ingest(bytes, 1, node(1));
    ks.acknowledge(hash, node(1)); // fully acked

    let frontier_before = ks.frontier;
    let ready_before    = ks.try_advance(false).is_ok();

    // stable=false must block even when all nodes have acked
    assert!(!ready_before, "stable=false must prevent advance regardless of ack state");
    assert_eq!(frontier_before, ks.frontier, "frontier must be frozen");
}

// stable=true + partial acks prevents advance.
#[test]
fn row2a_partial_acks_prevent_advance() {
    let bytes = encode(&Event::Create { entity_id: 1, kind: 0 });
    let hash  = sha256_event_hash(&bytes);

    let mut ks = KnowledgeState::new(node(1), [node(1), node(2)]);
    ks.ingest(bytes, 1, node(1));
    ks.acknowledge(hash, node(1)); // node(2) has not acked

    let frontier_before = ks.frontier;
    let ready_before    = ks.try_advance(true).is_ok();

    assert!(!ready_before, "partial acks must prevent advance");
    assert_eq!(frontier_before, ks.frontier, "frontier must be frozen");
}

// Readiness is deterministic: identical preconditions -> identical result across probes.
#[test]
fn row2a_readiness_is_deterministic_under_repeated_probe() {
    let bytes = encode(&Event::Create { entity_id: 1, kind: 0 });
    let hash  = sha256_event_hash(&bytes);

    let mut ks = KnowledgeState::new(node(1), [node(1), node(2)]);
    ks.ingest(bytes, 1, node(1));
    ks.acknowledge(hash, node(1));

    let r0 = ks.try_advance(true).is_ok();
    let r1 = ks.try_advance(true).is_ok();
    let r2 = ks.try_advance(true).is_ok();

    assert_eq!(r0, r1, "readiness must be stable across probes");
    assert_eq!(r1, r2, "readiness must be stable across probes");
}

// stable=false is stable under repeated probe (same invariant, different flag).
#[test]
fn row2a_unstable_readiness_is_deterministic_under_repeated_probe() {
    let bytes = encode(&Event::Create { entity_id: 1, kind: 0 });
    let hash  = sha256_event_hash(&bytes);

    let mut ks = KnowledgeState::new(node(1), [node(1)]);
    ks.ingest(bytes, 1, node(1));
    ks.acknowledge(hash, node(1));

    let r0 = ks.try_advance(false).is_ok();
    let r1 = ks.try_advance(false).is_ok();

    assert_eq!(r0, r1, "readiness under stable=false must be stable across probes");
}

// Readiness flips exactly at the condition boundary: the last ack resolves C = bot.
#[test]
fn row2a_readiness_flips_at_condition_boundary() {
    let bytes = encode(&Event::Create { entity_id: 1, kind: 0 });
    let hash  = sha256_event_hash(&bytes);

    let mut ks = KnowledgeState::new(node(1), [node(1), node(2)]);
    ks.ingest(bytes, 1, node(1));
    ks.acknowledge(hash, node(1));

    let ready_before = ks.try_advance(true).is_ok(); // node(2) not yet acked

    ks.acknowledge(hash, node(2)); // last ack — C transitions to top

    let ready_after = ks.try_advance(true).is_ok();

    assert!(!ready_before, "must not be ready before last ack");
    assert!( ready_after,  "must be ready immediately after last ack");
}

// 3-node progression: 0 -> 1 -> 2 -> 3 acks.
// At each partial step: not ready, frontier frozen.
// Readiness captured before each step — not assumed.
#[test]
fn row2a_three_node_progression_freezes_until_complete() {
    let bytes = encode(&Event::Create { entity_id: 1, kind: 0 });
    let hash  = sha256_event_hash(&bytes);

    let mut ks = KnowledgeState::new(node(1), [node(1), node(2), node(3)]);
    ks.ingest(bytes, 1, node(1));

    let ready_0    = ks.try_advance(true).is_ok();
    let frontier_0 = ks.frontier;

    ks.acknowledge(hash, node(1));
    let ready_1    = ks.try_advance(true).is_ok();
    let frontier_1 = ks.frontier;

    ks.acknowledge(hash, node(2));
    let ready_2    = ks.try_advance(true).is_ok();
    let frontier_2 = ks.frontier;

    ks.acknowledge(hash, node(3));
    let ready_3 = ks.try_advance(true).is_ok();

    assert!(!ready_0, "0/3 acks: must not be ready");
    assert!(!ready_1, "1/3 acks: must not be ready");
    assert!(!ready_2, "2/3 acks: must not be ready");
    assert!( ready_3, "3/3 acks: must be ready");

    assert_eq!(frontier_0, frontier_1, "frontier frozen at 0->1 acks");
    assert_eq!(frontier_1, frontier_2, "frontier frozen at 1->2 acks");
    assert!(ks.frontier.is_some(), "frontier set after full advance");
}

// stable=false overrides full ack state; stable=true with same acks succeeds.
// Tests the caller-controlled stability window contract.
#[test]
fn row2a_stable_flag_is_the_caller_contract() {
    let bytes = encode(&Event::Create { entity_id: 1, kind: 0 });
    let hash  = sha256_event_hash(&bytes);

    let mut ks = KnowledgeState::new(node(1), [node(1)]);
    ks.ingest(bytes, 1, node(1));
    ks.acknowledge(hash, node(1));

    let ready_unstable = ks.try_advance(false).is_ok();
    assert!(!ready_unstable, "stable=false must prevent advance even with full acks");
    assert!(ks.frontier.is_none(), "frontier must remain None");

    let ready_stable = ks.try_advance(true).is_ok();
    assert!(ready_stable, "stable=true with full acks must succeed");
    assert!(ks.frontier.is_some(), "frontier must be set after stable advance");
}

// After a successful advance, new events with partial acks must not move the snapshot forward.
// Frontier must remain at the post-first-advance value, not regress or advance.
#[test]
fn row2a_snapshot_frozen_on_partial_acks_after_prior_advance() {
    let e1 = encode(&Event::Create { entity_id: 1, kind: 0 });
    let h1 = sha256_event_hash(&e1);

    let mut ks = KnowledgeState::new(node(1), [node(1), node(2)]);
    ks.ingest(e1, 1, node(1));
    ks.acknowledge(h1, node(1));
    ks.acknowledge(h1, node(2));

    let prefix_first = ks.try_advance(true).expect("first advance must succeed");
    let snap_first   = snapshot(&prefix_first);
    let frontier_after_first = ks.frontier;

    // New event arrives — only node(1) acks it
    let e2 = encode(&Event::Update { entity_id: 1, field: 0, value: 99 });
    let h2 = sha256_event_hash(&e2);
    ks.ingest(e2, 2, node(1));
    ks.acknowledge(h2, node(1)); // node(2) has not acked e2

    // Advance must fail: e2 is not fully acknowledged
    let result = ks.try_advance(true);
    assert!(result.is_err(), "partial acks on new event must block advance");

    // Frontier must not have moved from the value set by the first advance
    assert_eq!(frontier_after_first, ks.frontier,
        "frontier must remain at post-first-advance value while new events are unacknowledged");

    // Once node(2) acks e2, advance succeeds and snapshot changes
    ks.acknowledge(h2, node(2));
    let prefix_second = ks.try_advance(true).expect("second advance must succeed");
    let snap_second   = snapshot(&prefix_second);

    assert_ne!(snap_first, snap_second,
        "snapshot must advance once new event is fully acknowledged");
}

// -----------------------------------------------------------------------
// Row 2B: Interleaving Invariance (commutativity — algebra layer)
// -----------------------------------------------------------------------
//
// Property: for any permutation of ingestion order and ack order over the
// same event set, snapshot(trace_A) == snapshot(trace_B) once C = top.
//
// Failure taxonomy — which KernelSnapshot field diverges:
//   state_hash  : reduction is non-commutative (kernel bug)
//   frontier    : CCI ordering is evaluation-order-sensitive (index bug)
//   prefix_hash : accumulation is non-commutative (ingress bug)
//
// Note on node_id origins: CCI = [tick | node_id | event_hash].
// Traces must use the same (tick, origin_node) per event for CCI equality.
// "Interleaving" here is ingestion arrival order and ack sequence — not origin.
//
// Verified:
//   ingestion order COMMUTES : same (tick, origin), different arrival -> same snapshot
//   ack order COMMUTES       : same events, different ack sequence    -> same snapshot
//   K-merge COMMUTES         : merge(A, B) hash-set-eq merge(B, A)
//   cross-node paths CONVERGE: different propagation routes           -> same snapshot

// --- Smoking gun: 2-trace minimal convergence ---
//
// Traces differ in BOTH ingestion arrival order AND per-node ack sequence.
// If any commutativity invariant is violated, exactly one KernelSnapshot field diverges,
// identifying the violation class without diff-chasing.
#[test]
fn row2b_smoking_gun_two_trace_convergence() {
    let e1 = encode(&Event::Create { entity_id: 1, kind: 5 });
    let e2 = encode(&Event::Update { entity_id: 1, field: 0, value: 42 });
    let e3 = encode(&Event::Commit { entity_id: 1 });
    let h1 = sha256_event_hash(&e1);
    let h2 = sha256_event_hash(&e2);
    let h3 = sha256_event_hash(&e3);

    // Trace A: events arrive e1->e2->e3, node(1) acks before node(2) on every event.
    let mut ks_a = KnowledgeState::new(node(1), [node(1), node(2)]);
    ks_a.ingest(e1.clone(), 1, node(1));
    ks_a.ingest(e2.clone(), 2, node(1));
    ks_a.ingest(e3.clone(), 3, node(1));
    ks_a.acknowledge(h1, node(1)); ks_a.acknowledge(h1, node(2));
    ks_a.acknowledge(h2, node(1)); ks_a.acknowledge(h2, node(2));
    ks_a.acknowledge(h3, node(1)); ks_a.acknowledge(h3, node(2));

    // Trace B: events arrive e3->e1->e2, node(2) acks before node(1), events acked in reverse order.
    // Same (tick, origin_node) per event — CCI is identical to trace A.
    let mut ks_b = KnowledgeState::new(node(1), [node(1), node(2)]);
    ks_b.ingest(e3.clone(), 3, node(1));
    ks_b.ingest(e1.clone(), 1, node(1));
    ks_b.ingest(e2.clone(), 2, node(1));
    ks_b.acknowledge(h3, node(2)); ks_b.acknowledge(h3, node(1));
    ks_b.acknowledge(h1, node(2)); ks_b.acknowledge(h1, node(1));
    ks_b.acknowledge(h2, node(2)); ks_b.acknowledge(h2, node(1));

    let snap_a = snapshot(&ks_a.try_advance(true).expect("trace A must advance"));
    let snap_b = snapshot(&ks_b.try_advance(true).expect("trace B must advance"));

    assert_eq!(snap_a, snap_b,
        "commutativity violation: different ingestion/ack orders must produce identical snapshot");
}

// Ingestion arrival order commutes: same (tick, origin) per event, different arrival sequence.
#[test]
fn row2b_ingestion_order_does_not_affect_snapshot() {
    let e1 = encode(&Event::Create { entity_id: 1, kind: 5 });
    let e2 = encode(&Event::Update { entity_id: 1, field: 0, value: 42 });
    let e3 = encode(&Event::Commit { entity_id: 1 });
    let h1 = sha256_event_hash(&e1);
    let h2 = sha256_event_hash(&e2);
    let h3 = sha256_event_hash(&e3);

    // Forward: e1(t=1), e2(t=2), e3(t=3)
    let mut ks_fwd = KnowledgeState::new(node(1), [node(1)]);
    for (bytes, tick, hash) in [(&e1, 1u64, &h1), (&e2, 2, &h2), (&e3, 3, &h3)] {
        ks_fwd.ingest(bytes.clone(), tick, node(1));
        ks_fwd.acknowledge(*hash, node(1));
    }
    // Reverse: e3(t=3), e2(t=2), e1(t=1)
    let mut ks_rev = KnowledgeState::new(node(1), [node(1)]);
    for (bytes, tick, hash) in [(&e3, 3u64, &h3), (&e2, 2, &h2), (&e1, 1, &h1)] {
        ks_rev.ingest(bytes.clone(), tick, node(1));
        ks_rev.acknowledge(*hash, node(1));
    }
    // Mixed: e2(t=2), e1(t=1), e3(t=3)
    let mut ks_mix = KnowledgeState::new(node(1), [node(1)]);
    for (bytes, tick, hash) in [(&e2, 2u64, &h2), (&e1, 1, &h1), (&e3, 3, &h3)] {
        ks_mix.ingest(bytes.clone(), tick, node(1));
        ks_mix.acknowledge(*hash, node(1));
    }

    let snap_f = snapshot(&ks_fwd.try_advance(true).expect("forward must succeed"));
    let snap_r = snapshot(&ks_rev.try_advance(true).expect("reverse must succeed"));
    let snap_m = snapshot(&ks_mix.try_advance(true).expect("mixed must succeed"));

    assert_eq!(snap_f, snap_r, "ingestion order forward vs reverse must not affect snapshot");
    assert_eq!(snap_f, snap_m, "ingestion order forward vs mixed must not affect snapshot");
}

// Ack sequence commutes: same events, same ingestion order, different per-node ack sequence.
#[test]
fn row2b_ack_order_does_not_affect_snapshot() {
    let e1 = encode(&Event::Create { entity_id: 1, kind: 5 });
    let e2 = encode(&Event::Commit { entity_id: 1 });
    let h1 = sha256_event_hash(&e1);
    let h2 = sha256_event_hash(&e2);

    let ingest = |ks: &mut KnowledgeState| {
        ks.ingest(e1.clone(), 1, node(1));
        ks.ingest(e2.clone(), 2, node(1));
    };

    // Ack order A: n1 then n2, event order e1 then e2
    let mut ks_a = KnowledgeState::new(node(1), [node(1), node(2)]);
    ingest(&mut ks_a);
    ks_a.acknowledge(h1, node(1)); ks_a.acknowledge(h1, node(2));
    ks_a.acknowledge(h2, node(1)); ks_a.acknowledge(h2, node(2));

    // Ack order B: n2 then n1, event order e2 then e1 — fully reversed
    let mut ks_b = KnowledgeState::new(node(1), [node(1), node(2)]);
    ingest(&mut ks_b);
    ks_b.acknowledge(h2, node(2)); ks_b.acknowledge(h2, node(1));
    ks_b.acknowledge(h1, node(2)); ks_b.acknowledge(h1, node(1));

    // Ack order C: interleaved — n1/e1, n2/e2, n1/e2, n2/e1
    let mut ks_c = KnowledgeState::new(node(1), [node(1), node(2)]);
    ingest(&mut ks_c);
    ks_c.acknowledge(h1, node(1)); ks_c.acknowledge(h2, node(2));
    ks_c.acknowledge(h2, node(1)); ks_c.acknowledge(h1, node(2));

    let snap_a = snapshot(&ks_a.try_advance(true).expect("must succeed"));
    let snap_b = snapshot(&ks_b.try_advance(true).expect("must succeed"));
    let snap_c = snapshot(&ks_c.try_advance(true).expect("must succeed"));

    assert_eq!(snap_a, snap_b, "ack order A vs B must not affect snapshot");
    assert_eq!(snap_a, snap_c, "ack order A vs C must not affect snapshot");
}

// K-merge is commutative: merge(A, B) and merge(B, A) produce hash-equal buffers.
// (Hash-set equality is the right invariant: entry metadata differs by which buffer "won",
//  but the event identity — the hash — is identical regardless of merge order.)
#[test]
fn row2b_k_merge_is_commutative() {
    let e1 = encode(&Event::Create { entity_id: 1, kind: 5 });
    let e2 = encode(&Event::Update { entity_id: 1, field: 0, value: 42 });
    let e3 = encode(&Event::Commit { entity_id: 1 });

    let make_a = || {
        let mut b = StagingBuffer::new();
        b.ingest(e1.clone(), 1, node(1));
        b.ingest(e2.clone(), 2, node(1));
        b
    };
    let make_b = || {
        let mut b = StagingBuffer::new();
        b.ingest(e2.clone(), 2, node(2));
        b.ingest(e3.clone(), 3, node(2));
        b
    };

    let mut merged_ab = make_a(); merged_ab.merge(&make_b());
    let mut merged_ba = make_b(); merged_ba.merge(&make_a());

    assert!(merged_ab.hash_set_eq(&merged_ba),
        "K-merge commutativity violation: merge(A,B) must equal merge(B,A) by event-hash set");
}

// Cross-node propagation paths converge: two nodes accumulate the same events
// via opposite paths (node A sends e1 to B; node B sends e2 to A).
// Both must produce identical snapshots once C = top.
#[test]
fn row2b_cross_node_propagation_paths_converge() {
    let e1 = encode(&Event::Create { entity_id: 1, kind: 5 });
    let e2 = encode(&Event::Update { entity_id: 1, field: 0, value: 42 });
    let h1 = sha256_event_hash(&e1);
    let h2 = sha256_event_hash(&e2);

    // Node A: originates e1, receives e2 from node B
    let mut ks_a = KnowledgeState::new(node(1), [node(1), node(2)]);
    ks_a.ingest(e1.clone(), 1, node(1));
    ks_a.ingest(e2.clone(), 2, node(2)); // propagated from node(2)
    ks_a.acknowledge(h1, node(1)); ks_a.acknowledge(h1, node(2));
    ks_a.acknowledge(h2, node(2)); ks_a.acknowledge(h2, node(1));

    // Node B: originates e2, receives e1 from node A — opposite propagation path
    let mut ks_b = KnowledgeState::new(node(2), [node(1), node(2)]);
    ks_b.ingest(e2.clone(), 2, node(2));
    ks_b.ingest(e1.clone(), 1, node(1)); // propagated from node(1)
    ks_b.acknowledge(h2, node(2)); ks_b.acknowledge(h2, node(1));
    ks_b.acknowledge(h1, node(1)); ks_b.acknowledge(h1, node(2));

    let snap_a = snapshot(&ks_a.try_advance(true).expect("node A must advance"));
    let snap_b = snapshot(&ks_b.try_advance(true).expect("node B must advance"));

    assert_eq!(snap_a, snap_b,
        "commutativity violation: different cross-node propagation paths must converge");
}
