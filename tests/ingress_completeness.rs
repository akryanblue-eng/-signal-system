use signal_system::codec::encode;
use signal_system::divergence::{detect_if_complete, AnnotatedDivergence, DivergenceLevel};
use signal_system::event::Event;
use signal_system::index::sha256_event_hash;
use signal_system::ingress::{
    build_prefix, check_completeness, AcknowledgmentGraph, KnowledgeState, PrefixError,
    StagingBuffer,
};
use signal_system::kernel::{compile, genesis};

fn node(id: u8) -> [u8; 16] { [id; 16] }

fn sample_bytes() -> Vec<Vec<u8>> {
    vec![
        encode(&Event::Create { entity_id: 1, kind: 5 }),
        encode(&Event::Update { entity_id: 1, field: 0, value: 42 }),
        encode(&Event::Commit { entity_id: 1 }),
    ]
}

// --- StagingBuffer ---

#[test]
fn ingest_returns_true_for_new_event() {
    let mut buf = StagingBuffer::new();
    let bytes = encode(&Event::Commit { entity_id: 1 });
    assert!(buf.ingest(bytes, 1, node(1)));
}

#[test]
fn ingest_returns_false_for_duplicate() {
    let mut buf = StagingBuffer::new();
    let bytes = encode(&Event::Commit { entity_id: 1 });
    buf.ingest(bytes.clone(), 1, node(1));
    assert!(!buf.ingest(bytes, 2, node(2)));  // same bytes, different origin
}

#[test]
fn staging_buffer_deduplicates_by_canonical_hash() {
    let mut buf = StagingBuffer::new();
    let bytes = encode(&Event::Commit { entity_id: 1 });
    buf.ingest(bytes.clone(), 1, node(1));
    buf.ingest(bytes.clone(), 2, node(2));
    buf.ingest(bytes,         3, node(3));
    assert_eq!(buf.len(), 1);
}

// --- K1: Monotonicity ---

#[test]
fn merge_is_monotonic() {
    // K(B1) subset-of K(B1 union B2)
    let mut a = StagingBuffer::new();
    let bytes_a = sample_bytes();
    for b in &bytes_a[..2] {
        a.ingest(b.clone(), 1, node(1));
    }
    let size_before = a.len();

    let mut b = StagingBuffer::new();
    for byt in &bytes_a {
        b.ingest(byt.clone(), 2, node(2));
    }

    a.merge(&b);
    assert!(a.len() >= size_before, "merge must not shrink the buffer");
    assert_eq!(a.len(), bytes_a.len()); // now contains all events
}

// --- K2: Idempotence ---

#[test]
fn merge_is_idempotent() {
    // K(K(B)) = K(B): merging the same buffer twice has no effect
    let mut base = StagingBuffer::new();
    for b in sample_bytes() {
        base.ingest(b, 1, node(1));
    }
    let size_before = base.len();

    let other = {
        let mut o = StagingBuffer::new();
        for b in sample_bytes() {
            o.ingest(b, 2, node(2));
        }
        o
    };

    base.merge(&other);
    base.merge(&other); // merge again — must be no-op
    assert_eq!(base.len(), size_before);
}

// --- K3: Convergence ---

#[test]
fn two_nodes_with_same_events_have_equal_buffers() {
    // K3: once both nodes see all events, their buffers are equal
    let mut ks_a = KnowledgeState::new(node(1), [node(1), node(2)]);
    let mut ks_b = KnowledgeState::new(node(2), [node(1), node(2)]);

    for bytes in sample_bytes() {
        ks_a.ingest(bytes.clone(), 1, node(1));
        ks_b.ingest(bytes.clone(), 1, node(1));
    }

    assert!(ks_a.staging.hash_set_eq(&ks_b.staging));
}

// --- AcknowledgmentGraph ---

#[test]
fn ack_graph_tracks_per_event_per_node() {
    let mut acks = AcknowledgmentGraph::new([node(1), node(2)]);
    let hash = [0u8; 32];
    assert!(!acks.all_acknowledged(&hash));
    acks.acknowledge(hash, node(1));
    assert!(!acks.all_acknowledged(&hash)); // still missing node 2
    acks.acknowledge(hash, node(2));
    assert!(acks.all_acknowledged(&hash));  // all acknowledged
}

#[test]
fn ack_count_reflects_distinct_nodes() {
    let mut acks = AcknowledgmentGraph::new([node(1), node(2), node(3)]);
    let hash = [1u8; 32];
    assert_eq!(acks.ack_count(&hash), 0);
    acks.acknowledge(hash, node(1));
    acks.acknowledge(hash, node(1)); // duplicate — must not double-count
    assert_eq!(acks.ack_count(&hash), 1);
}

#[test]
fn ack_complete_with_zero_nodes() {
    let acks = AcknowledgmentGraph::new(std::iter::empty());
    assert!(acks.all_acknowledged(&[0u8; 32]));
}

// --- Completeness predicate ---

#[test]
fn incomplete_without_stability() {
    let acks = AcknowledgmentGraph::new(std::iter::empty());
    let hashes = vec![[1u8; 32]];
    let state = check_completeness(hashes, &acks, false);
    assert!(!state.is_complete());
}

#[test]
fn incomplete_without_acks() {
    let hash = sha256_event_hash(&encode(&Event::Commit { entity_id: 1 }));
    let acks = AcknowledgmentGraph::new([node(1)]);
    // node(1) has NOT acknowledged — incomplete even with stability
    let state = check_completeness(vec![hash], &acks, true);
    assert!(!state.is_complete());
}

#[test]
fn complete_with_stability_and_all_acks() {
    let hash = sha256_event_hash(&encode(&Event::Commit { entity_id: 1 }));
    let mut acks = AcknowledgmentGraph::new([node(1)]);
    acks.acknowledge(hash, node(1));
    let state = check_completeness(vec![hash], &acks, true);
    assert!(state.is_complete());
}

// --- build_prefix ---

#[test]
fn build_prefix_fails_when_not_stable() {
    let mut buf = StagingBuffer::new();
    buf.ingest(encode(&Event::Commit { entity_id: 1 }), 1, node(1));
    let acks = AcknowledgmentGraph::new(std::iter::empty());
    let result = build_prefix(&buf, &acks, false);
    assert!(matches!(result, Err(PrefixError::Incomplete { .. })));
}

#[test]
fn build_prefix_fails_when_unacknowledged() {
    let mut buf = StagingBuffer::new();
    buf.ingest(encode(&Event::Commit { entity_id: 1 }), 1, node(1));
    let acks = AcknowledgmentGraph::new([node(1)]); // node(1) hasn't acked
    let result = build_prefix(&buf, &acks, true);
    assert!(matches!(result, Err(PrefixError::Incomplete { unacknowledged_count: 1 })));
}

#[test]
fn build_prefix_succeeds_when_complete() {
    let mut buf = StagingBuffer::new();
    let bytes = encode(&Event::Commit { entity_id: 1 });
    let hash = sha256_event_hash(&bytes);
    buf.ingest(bytes, 1, node(1));

    let mut acks = AcknowledgmentGraph::new([node(1)]);
    acks.acknowledge(hash, node(1));

    let prefix = build_prefix(&buf, &acks, true).expect("must succeed");
    assert_eq!(prefix.events.len(), 1);
    assert!(prefix.decode_failures.is_empty());
}

#[test]
fn build_prefix_orders_events_by_cci() {
    let events: Vec<Vec<u8>> = (0u64..5)
        .rev() // deliberately reversed tick order
        .map(|i| encode(&Event::Create { entity_id: i, kind: 0 }))
        .collect();

    let mut buf = StagingBuffer::new();
    for (tick, bytes) in events.iter().enumerate() {
        buf.ingest(bytes.clone(), (4 - tick) as u64, node(1)); // tick descends
    }

    let mut acks = AcknowledgmentGraph::new([node(1)]);
    for hash in buf.event_hashes().cloned().collect::<Vec<_>>() {
        acks.acknowledge(hash, node(1));
    }

    let prefix = build_prefix(&buf, &acks, true).expect("must succeed");
    for w in prefix.events.windows(2) {
        assert!(w[0].cci < w[1].cci, "prefix must be ascending by CCI");
    }
}

#[test]
fn build_prefix_reports_decode_failures_without_blocking() {
    let valid_bytes = encode(&Event::Commit { entity_id: 1 });
    let invalid_bytes = b"garbage bytes that will fail decode".to_vec();

    let valid_hash = sha256_event_hash(&valid_bytes);
    let invalid_hash = sha256_event_hash(&invalid_bytes);

    let mut buf = StagingBuffer::new();
    buf.ingest(valid_bytes, 1, node(1));
    buf.ingest(invalid_bytes, 1, node(1));

    let mut acks = AcknowledgmentGraph::new([node(1)]);
    acks.acknowledge(valid_hash, node(1));
    // invalid_hash is not acknowledged (and also not valid, so not required)

    let prefix = build_prefix(&buf, &acks, true).expect("must succeed");
    assert_eq!(prefix.events.len(), 1);
    assert_eq!(prefix.decode_failures, vec![invalid_hash]);
}

#[test]
fn build_prefix_empty_buffer_is_valid() {
    let buf = StagingBuffer::new();
    let acks = AcknowledgmentGraph::new(std::iter::empty());
    let prefix = build_prefix(&buf, &acks, true).expect("empty is complete");
    assert!(prefix.events.is_empty());
    assert!(prefix.frontier.is_none());
    assert!(prefix.decode_failures.is_empty());
}

#[test]
fn frontier_is_max_cci_of_prefix() {
    let mut buf = StagingBuffer::new();
    let mut acks = AcknowledgmentGraph::new([node(1)]);

    for (tick, bytes) in sample_bytes().into_iter().enumerate() {
        let hash = sha256_event_hash(&bytes);
        buf.ingest(bytes, tick as u64, node(1));
        acks.acknowledge(hash, node(1));
    }

    let prefix = build_prefix(&buf, &acks, true).expect("must succeed");
    let expected_frontier = prefix.events.last().map(|e| e.cci);
    assert_eq!(prefix.frontier, expected_frontier);
}

// --- AnnotatedDivergence ---

#[test]
fn undetermined_when_either_prefix_incomplete() {
    let s = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    assert_eq!(detect_if_complete(&s, false, &s, true), AnnotatedDivergence::Undetermined);
    assert_eq!(detect_if_complete(&s, true, &s, false), AnnotatedDivergence::Undetermined);
    assert_eq!(detect_if_complete(&s, false, &s, false), AnnotatedDivergence::Undetermined);
}

#[test]
fn determined_when_both_complete_and_converged() {
    let events = vec![Event::Create { entity_id: 1, kind: 5 }];
    let a = compile(genesis(), events.clone());
    let b = compile(genesis(), events);
    let result = detect_if_complete(&a, true, &b, true);
    assert!(matches!(
        result,
        AnnotatedDivergence::Determined(ref r) if r.level == DivergenceLevel::CONVERGED
    ));
}

#[test]
fn determined_when_both_complete_and_diverged() {
    let a = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let b = compile(genesis(), [Event::Create { entity_id: 2, kind: 0 }]);
    let result = detect_if_complete(&a, true, &b, true);
    assert!(matches!(
        result,
        AnnotatedDivergence::Determined(ref r) if r.level == DivergenceLevel::FULL
    ));
}

// --- KnowledgeState integration ---

#[test]
fn knowledge_state_try_advance_succeeds_when_complete() {
    let mut ks = KnowledgeState::new(node(1), [node(1)]);
    let bytes = encode(&Event::Create { entity_id: 1, kind: 0 });
    let hash = sha256_event_hash(&bytes);
    ks.ingest(bytes, 1, node(1));
    ks.acknowledge(hash, node(1));
    let prefix = ks.try_advance(true).expect("must succeed");
    assert_eq!(prefix.events.len(), 1);
    assert!(ks.frontier.is_some());
}

#[test]
fn knowledge_state_try_advance_fails_when_incomplete() {
    let mut ks = KnowledgeState::new(node(1), [node(1)]);
    ks.ingest(encode(&Event::Create { entity_id: 1, kind: 0 }), 1, node(1));
    // no acknowledgment, not stable
    assert!(ks.try_advance(false).is_err());
}
