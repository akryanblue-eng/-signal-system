// Oracle evidence ledger — machine-readable baseline.
//
// Row 1   | Valid input -> deterministic reduction | state_hash STABLE | frontier STABLE | prefix_hash STABLE
// Row 1b  | Invalid input -> non-admission         | state_hash STABLE | frontier STABLE | prefix_hash STABLE
//
// Row 2A (readiness boundary — schedule-sensitive) is the next target.
// Row 1 / Row 1b are frozen; do not modify existing tests in this file.

use signal_system::codec::{decode, encode};
use signal_system::event::Event;
use signal_system::index::{sha256_event_hash, Cci};
use signal_system::ingress::{ExecutionPrefix, KnowledgeState};
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
