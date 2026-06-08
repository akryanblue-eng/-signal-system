use signal_system::divergence::{detect, DivergenceLevel, Mismatch};
use signal_system::event::{CompiledState, EntityRecord, EntityStatus, Event};
use signal_system::kernel::{compile, genesis, transition};
use std::collections::BTreeMap;

// --- Convergence ---

#[test]
fn genesis_states_converge() {
    let report = detect(&genesis(), &genesis());
    assert_eq!(report.level, DivergenceLevel::CONVERGED);
    assert!(report.mismatches.is_empty());
}

#[test]
fn identical_event_sequences_converge() {
    let events = vec![
        Event::Create { entity_id: 1, kind: 5 },
        Event::Update { entity_id: 1, field: 0, value: 42 },
        Event::Commit { entity_id: 1 },
    ];
    let report = detect(
        &compile(genesis(), events.clone()),
        &compile(genesis(), events),
    );
    assert_eq!(report.level, DivergenceLevel::CONVERGED);
    assert!(report.mismatches.is_empty());
}

// --- ChainOnly divergence ---

#[test]
fn reject_produces_chain_only_divergence() {
    let base = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let with_reject = transition(base.clone(), &Event::Reject { entity_id: 1, reason_code: 0 });
    let report = detect(&base, &with_reject);
    assert_eq!(report.level, DivergenceLevel::CHAIN_ONLY);
}

#[test]
fn chain_only_reports_event_chain_mismatch_only() {
    let base = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let with_reject = transition(base.clone(), &Event::Reject { entity_id: 1, reason_code: 0 });
    let report = detect(&base, &with_reject);
    assert!(report.mismatches.iter().any(|m| matches!(m, Mismatch::EventChainHash { .. })));
    assert!(!report.mismatches.iter().any(|m| matches!(m, Mismatch::StateHash { .. })));
    assert!(!report.mismatches.iter().any(|m| matches!(m, Mismatch::EntityPresence { .. })));
}

// --- Semantic divergence (same chain, different state — transition nondeterminism class) ---

#[test]
fn semantic_level_for_same_chain_different_state() {
    // States with equal event_chain_hash but different state_hash.
    // In correct operation this is impossible; detecting it is critical for CI.
    let base = genesis();
    let fabricated = CompiledState {
        entities: {
            let mut m = BTreeMap::new();
            m.insert(99, EntityRecord::new(7));
            m
        },
        state_hash: [0xAA; 32],
        event_chain_hash: base.event_chain_hash, // same chain
        csp: [0xBB; 32],
    };
    let report = detect(&base, &fabricated);
    assert_eq!(report.level, DivergenceLevel::SEMANTIC);
    assert!(!report.level.is_converged());
}

// --- Full divergence ---

#[test]
fn different_entities_produce_full_divergence() {
    let a = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let b = compile(genesis(), [Event::Create { entity_id: 2, kind: 0 }]);
    assert_eq!(detect(&a, &b).level, DivergenceLevel::FULL);
}

// --- Entity presence mismatches ---

#[test]
fn entity_presence_mismatch_is_reported() {
    let a = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let b = compile(genesis(), [Event::Create { entity_id: 2, kind: 0 }]);
    let report = detect(&a, &b);
    let ep = report.mismatches.iter().find_map(|m| match m {
        Mismatch::EntityPresence { only_in_a, only_in_b } => Some((only_in_a.clone(), only_in_b.clone())),
        _ => None,
    });
    let (oia, oib) = ep.expect("EntityPresence mismatch must be present");
    assert_eq!(oia, vec![1u64]);
    assert_eq!(oib, vec![2u64]);
}

#[test]
fn no_entity_presence_mismatch_when_ids_are_equal() {
    let a = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Update { entity_id: 1, field: 0, value: 1 },
    ]);
    let b = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Update { entity_id: 1, field: 0, value: 2 },
    ]);
    let report = detect(&a, &b);
    assert!(!report.mismatches.iter().any(|m| matches!(m, Mismatch::EntityPresence { .. })));
}

// --- Field value mismatches ---

#[test]
fn field_value_mismatch_is_reported() {
    let a = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Update { entity_id: 1, field: 3, value: 100 },
    ]);
    let b = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Update { entity_id: 1, field: 3, value: 999 },
    ]);
    let report = detect(&a, &b);
    let fv = report.mismatches.iter().find_map(|m| match m {
        Mismatch::FieldValue { entity_id, field, value_a, value_b } =>
            Some((*entity_id, *field, *value_a, *value_b)),
        _ => None,
    });
    let (eid, f, va, vb) = fv.expect("FieldValue mismatch must be present");
    assert_eq!(eid, 1);
    assert_eq!(f, 3);
    assert_eq!(va, Some(100));
    assert_eq!(vb, Some(999));
}

#[test]
fn absent_field_reported_as_none() {
    let a = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Update { entity_id: 1, field: 5, value: 777 },
    ]);
    let b = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        // field 5 never set
    ]);
    let report = detect(&a, &b);
    let fv = report.mismatches.iter().find_map(|m| match m {
        Mismatch::FieldValue { field: 5, value_a, value_b, .. } => Some((*value_a, *value_b)),
        _ => None,
    });
    let (va, vb) = fv.expect("FieldValue mismatch for field 5 must be present");
    assert_eq!(va, Some(777));
    assert_eq!(vb, None);
}

// --- Entity status mismatches ---

#[test]
fn entity_status_mismatch_is_reported() {
    let a = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Create { entity_id: 2, kind: 0 },
        Event::Merge  { target_id: 1, source_id: 2 },
    ]);
    let b = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Create { entity_id: 2, kind: 0 },
    ]);
    let report = detect(&a, &b);
    let sm = report.mismatches.iter().find_map(|m| match m {
        Mismatch::EntityStatus { entity_id, status_a, status_b } =>
            Some((*entity_id, *status_a, *status_b)),
        _ => None,
    });
    let (eid, sa, sb) = sm.expect("EntityStatus mismatch must be present");
    assert_eq!(eid, 2);
    assert_eq!(sa, EntityStatus::MergedInto);
    assert_eq!(sb, EntityStatus::Active);
}

// --- Commit bit mismatches ---

#[test]
fn commit_bit_mismatch_is_reported() {
    let a = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Commit { entity_id: 1 },
    ]);
    let b = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
    ]);
    let report = detect(&a, &b);
    let cm = report.mismatches.iter().find_map(|m| match m {
        Mismatch::CommitBit { entity_id, committed_a, committed_b } =>
            Some((*entity_id, *committed_a, *committed_b)),
        _ => None,
    });
    let (eid, ca, cb) = cm.expect("CommitBit mismatch must be present");
    assert_eq!(eid, 1);
    assert!(ca);
    assert!(!cb);
}

// --- Lattice operations ---

#[test]
fn lattice_partial_order() {
    // Linear chains: Converged ≤ ChainOnly ≤ Full
    assert!(DivergenceLevel::CONVERGED  < DivergenceLevel::CHAIN_ONLY);
    assert!(DivergenceLevel::CHAIN_ONLY < DivergenceLevel::FULL);
    assert!(DivergenceLevel::CONVERGED  < DivergenceLevel::FULL);
    // Linear chains: Converged ≤ Semantic ≤ Full
    assert!(DivergenceLevel::CONVERGED < DivergenceLevel::SEMANTIC);
    assert!(DivergenceLevel::SEMANTIC  < DivergenceLevel::FULL);
    // ChainOnly and Semantic are incomparable
    assert!(DivergenceLevel::CHAIN_ONLY.partial_cmp(&DivergenceLevel::SEMANTIC).is_none());
    assert!(DivergenceLevel::SEMANTIC.partial_cmp(&DivergenceLevel::CHAIN_ONLY).is_none());
}

#[test]
fn join_is_least_upper_bound() {
    assert_eq!(DivergenceLevel::CHAIN_ONLY.join(DivergenceLevel::SEMANTIC),   DivergenceLevel::FULL);
    assert_eq!(DivergenceLevel::CONVERGED.join(DivergenceLevel::CHAIN_ONLY),  DivergenceLevel::CHAIN_ONLY);
    assert_eq!(DivergenceLevel::CONVERGED.join(DivergenceLevel::SEMANTIC),    DivergenceLevel::SEMANTIC);
    assert_eq!(DivergenceLevel::FULL.join(DivergenceLevel::CONVERGED),        DivergenceLevel::FULL);
    assert_eq!(DivergenceLevel::FULL.join(DivergenceLevel::FULL),             DivergenceLevel::FULL);
}

#[test]
fn meet_is_greatest_lower_bound() {
    assert_eq!(DivergenceLevel::CHAIN_ONLY.meet(DivergenceLevel::SEMANTIC),   DivergenceLevel::CONVERGED);
    assert_eq!(DivergenceLevel::FULL.meet(DivergenceLevel::CHAIN_ONLY),       DivergenceLevel::CHAIN_ONLY);
    assert_eq!(DivergenceLevel::FULL.meet(DivergenceLevel::SEMANTIC),         DivergenceLevel::SEMANTIC);
    assert_eq!(DivergenceLevel::CONVERGED.meet(DivergenceLevel::FULL),        DivergenceLevel::CONVERGED);
    assert_eq!(DivergenceLevel::CONVERGED.meet(DivergenceLevel::CONVERGED),   DivergenceLevel::CONVERGED);
}

#[test]
fn is_converged_only_for_converged_level() {
    assert!( DivergenceLevel::CONVERGED.is_converged());
    assert!(!DivergenceLevel::CHAIN_ONLY.is_converged());
    assert!(!DivergenceLevel::SEMANTIC.is_converged());
    assert!(!DivergenceLevel::FULL.is_converged());
}

#[test]
fn join_is_idempotent() {
    for level in [
        DivergenceLevel::CONVERGED,
        DivergenceLevel::CHAIN_ONLY,
        DivergenceLevel::SEMANTIC,
        DivergenceLevel::FULL,
    ] {
        assert_eq!(level.join(level), level);
        assert_eq!(level.meet(level), level);
    }
}
