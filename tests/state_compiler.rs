use signal_system::event::{EntityStatus, Event};
use signal_system::kernel::{compile, genesis, transition};

// --- Genesis ---

#[test]
fn genesis_is_deterministic() {
    assert_eq!(genesis().csp, genesis().csp);
    assert_eq!(genesis().entities.len(), 0);
}

#[test]
fn genesis_event_chain_hash_is_zero() {
    assert_eq!(genesis().event_chain_hash, [0u8; 32]);
}

// --- Create ---

#[test]
fn create_adds_entity() {
    let state = transition(genesis(), &Event::Create { entity_id: 1, kind: 42 });
    let rec = state.entities.get(&1).expect("entity 1 must exist");
    assert_eq!(rec.kind, 42);
    assert_eq!(rec.status, EntityStatus::Active);
    assert!(!rec.committed);
}

#[test]
fn create_is_idempotent_on_existing_entity() {
    let s1 = transition(genesis(), &Event::Create { entity_id: 1, kind: 10 });
    // Second Create with a different kind must not overwrite
    let s2 = transition(s1.clone(), &Event::Create { entity_id: 1, kind: 99 });
    assert_eq!(s2.entities[&1].kind, 10);
}

// --- Update ---

#[test]
fn update_sets_field_on_active_entity() {
    let s = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Update { entity_id: 1, field: 5, value: 9999 },
    ]);
    assert_eq!(s.entities[&1].fields[&5], 9999);
}

#[test]
fn update_is_noop_on_missing_entity() {
    let s = transition(genesis(), &Event::Update { entity_id: 99, field: 0, value: 1 });
    assert!(s.entities.is_empty());
}

#[test]
fn update_is_noop_on_merged_entity() {
    let s = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Create { entity_id: 2, kind: 0 },
        Event::Merge  { target_id: 1, source_id: 2 },
        Event::Update { entity_id: 2, field: 0, value: 777 }, // source is MergedInto
    ]);
    // entity 2 is MergedInto — Update must be a no-op
    assert!(!s.entities[&2].fields.contains_key(&0));
}

// --- Merge ---

#[test]
fn merge_absorbs_source_fields_into_target() {
    let s = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Create { entity_id: 2, kind: 0 },
        Event::Update { entity_id: 1, field: 0, value: 100 },
        Event::Update { entity_id: 2, field: 1, value: 200 },
        Event::Merge  { target_id: 1, source_id: 2 },
    ]);
    assert_eq!(s.entities[&1].fields[&0], 100); // target field preserved
    assert_eq!(s.entities[&1].fields[&1], 200); // source field absorbed
}

#[test]
fn merge_target_wins_on_field_conflict() {
    let s = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Create { entity_id: 2, kind: 0 },
        Event::Update { entity_id: 1, field: 0, value: 100 },
        Event::Update { entity_id: 2, field: 0, value: 999 }, // same key, different value
        Event::Merge  { target_id: 1, source_id: 2 },
    ]);
    assert_eq!(s.entities[&1].fields[&0], 100); // target wins
}

#[test]
fn merge_marks_source_merged_into() {
    let s = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Create { entity_id: 2, kind: 0 },
        Event::Merge  { target_id: 1, source_id: 2 },
    ]);
    let src = &s.entities[&2];
    assert_eq!(src.status, EntityStatus::MergedInto);
    assert_eq!(src.linked_id, 1);
    assert!(src.fields.is_empty());
}

#[test]
fn merge_is_noop_on_self() {
    let s0 = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let s1 = transition(s0.clone(), &Event::Merge { target_id: 1, source_id: 1 });
    assert_eq!(s0.entities[&1], s1.entities[&1]);
}

#[test]
fn merge_is_noop_on_missing_entity() {
    let s0 = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let s1 = transition(s0.clone(), &Event::Merge { target_id: 1, source_id: 99 });
    assert_eq!(s0.entities, s1.entities);
}

// --- Partition ---

#[test]
fn partition_creates_child_entity() {
    let s = compile(genesis(), [
        Event::Create    { entity_id: 1, kind: 5 },
        Event::Partition { entity_id: 1, new_entity_id: 2, partition_key: 0x000F },
    ]);
    assert!(s.entities.contains_key(&2));
    assert_eq!(s.entities[&2].kind, 0x000F);
    assert_eq!(s.entities[&2].linked_id, 1);
}

#[test]
fn partition_marks_origin_partitioned() {
    let s = compile(genesis(), [
        Event::Create    { entity_id: 1, kind: 0 },
        Event::Partition { entity_id: 1, new_entity_id: 2, partition_key: 0 },
    ]);
    assert_eq!(s.entities[&1].status, EntityStatus::Partitioned);
    assert_eq!(s.entities[&1].linked_id, 2);
}

#[test]
fn partition_is_noop_if_new_id_already_exists() {
    let s0 = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Create { entity_id: 2, kind: 7 },
    ]);
    let s1 = transition(s0.clone(), &Event::Partition { entity_id: 1, new_entity_id: 2, partition_key: 0 });
    assert_eq!(s0.entities[&1].status, s1.entities[&1].status);
    assert_eq!(s0.entities[&2], s1.entities[&2]);
}

#[test]
fn partition_is_noop_on_missing_origin() {
    let s0 = genesis();
    let s1 = transition(s0.clone(), &Event::Partition { entity_id: 99, new_entity_id: 100, partition_key: 0 });
    assert!(s1.entities.is_empty());
}

// --- Commit ---

#[test]
fn commit_marks_entity_committed() {
    let s = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Commit { entity_id: 1 },
    ]);
    assert!(s.entities[&1].committed);
}

#[test]
fn commit_is_idempotent() {
    let s1 = compile(genesis(), [
        Event::Create { entity_id: 1, kind: 0 },
        Event::Commit { entity_id: 1 },
    ]);
    let s2 = transition(s1.clone(), &Event::Commit { entity_id: 1 });
    // Second commit: state_hash unchanged (entities unchanged), chain advances
    assert_eq!(s1.state_hash, s2.state_hash);
    // chain hash IS different (different event applied)
    assert_ne!(s1.event_chain_hash, s2.event_chain_hash);
}

// --- Reject ---

#[test]
fn reject_does_not_change_entities() {
    let s0 = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let s1 = transition(s0.clone(), &Event::Reject { entity_id: 1, reason_code: 503 });
    assert_eq!(s0.entities, s1.entities);
}

#[test]
fn reject_does_not_change_state_hash() {
    let s0 = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let s1 = transition(s0.clone(), &Event::Reject { entity_id: 1, reason_code: 503 });
    assert_eq!(s0.state_hash, s1.state_hash);
}

#[test]
fn reject_advances_event_chain_hash() {
    let s0 = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let s1 = transition(s0.clone(), &Event::Reject { entity_id: 1, reason_code: 503 });
    assert_ne!(s0.event_chain_hash, s1.event_chain_hash);
}

#[test]
fn reject_changes_csp() {
    let s0 = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let s1 = transition(s0.clone(), &Event::Reject { entity_id: 1, reason_code: 503 });
    assert_ne!(s0.csp, s1.csp);
}

// --- Hash chain invariants ---

#[test]
fn event_chain_hash_advances_on_every_event() {
    let s0 = genesis();
    let s1 = transition(s0.clone(), &Event::Create { entity_id: 1, kind: 0 });
    let s2 = transition(s1.clone(), &Event::Reject { entity_id: 1, reason_code: 0 });
    assert_ne!(s0.event_chain_hash, s1.event_chain_hash);
    assert_ne!(s1.event_chain_hash, s2.event_chain_hash);
}

#[test]
fn event_chain_hash_is_order_sensitive() {
    let e1 = Event::Create { entity_id: 1, kind: 1 };
    let e2 = Event::Create { entity_id: 2, kind: 2 };
    let forward  = compile(genesis(), [e1.clone(), e2.clone()]);
    let reversed = compile(genesis(), [e2, e1]);
    assert_ne!(forward.event_chain_hash, reversed.event_chain_hash);
}

#[test]
fn same_events_always_produce_same_csp() {
    let events = vec![
        Event::Create    { entity_id: 1, kind: 5 },
        Event::Update    { entity_id: 1, field: 0, value: 42 },
        Event::Create    { entity_id: 2, kind: 3 },
        Event::Merge     { target_id: 1, source_id: 2 },
        Event::Reject    { entity_id: 1, reason_code: 0 },
        Event::Commit    { entity_id: 1 },
    ];
    let a = compile(genesis(), events.clone());
    let b = compile(genesis(), events);
    assert_eq!(a.csp, b.csp);
}

// --- Full lifecycle ---

#[test]
fn full_lifecycle() {
    let state = compile(genesis(), [
        Event::Create    { entity_id: 1,  kind: 10 },
        Event::Update    { entity_id: 1,  field: 0, value: 100 },
        Event::Create    { entity_id: 2,  kind: 20 },
        Event::Update    { entity_id: 2,  field: 0, value: 200 },
        Event::Merge     { target_id: 1,  source_id: 2 },
        Event::Partition { entity_id: 1,  new_entity_id: 3, partition_key: 0x0007 },
        Event::Reject    { entity_id: 3,  reason_code: 100 },
        Event::Commit    { entity_id: 1 },
    ]);

    assert_eq!(state.entities.len(), 3);
    assert!(state.entities[&1].committed);
    assert_eq!(state.entities[&2].status, EntityStatus::MergedInto);
    assert_eq!(state.entities[&3].status, EntityStatus::Active);
    assert_eq!(state.entities[&3].kind, 7); // partition_key & 0xFFFF = 7
}
