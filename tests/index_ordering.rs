use signal_system::codec::encode;
use signal_system::event::Event;
use signal_system::index::{merge_ordered, order, sha256_event_hash, Cci, IndexedEvent};

fn node(id: u8) -> [u8; 16] {
    [id; 16]
}

fn indexed(event: &Event, tick: u64, node_id: [u8; 16]) -> IndexedEvent {
    IndexedEvent::derive(encode(event), tick, node_id)
}

// --- CCI derivation ---

#[test]
fn cci_is_purely_derived() {
    let bytes = encode(&Event::Create { entity_id: 1, kind: 0 });
    let h = sha256_event_hash(&bytes);
    assert_eq!(Cci::compute(100, node(1), h), Cci::compute(100, node(1), h));
}

#[test]
fn cci_components_round_trip() {
    let tick = 0xDEADBEEF_CAFEBABE_u64;
    let node_id = [0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,
                   0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F,0x10];
    let hash = sha256_event_hash(b"round trip");
    let cci = Cci::compute(tick, node_id, hash);
    assert_eq!(cci.tick(), tick);
    assert_eq!(cci.node_id(), node_id);
    assert_eq!(cci.event_hash(), hash);
}

#[test]
fn cci_tick_dominates_ordering() {
    let e = Event::Create { entity_id: 1, kind: 0 };
    // early has a high node_id, late has a low node_id — tick wins regardless
    let early = indexed(&e, 1, node(0xFF));
    let late  = indexed(&e, 2, node(0x00));
    assert!(early.cci < late.cci, "lower tick must always sort before higher tick");
}

#[test]
fn cci_node_id_breaks_tick_tie() {
    let e = Event::Create { entity_id: 1, kind: 0 };
    let a = indexed(&e, 100, node(0x01));
    let b = indexed(&e, 100, node(0x02));
    assert!(a.cci < b.cci, "lower node_id must sort before higher node_id on equal tick");
}

#[test]
fn cci_event_hash_breaks_remaining_tie() {
    // Different events → different SHA-256 → different CCI even with same tick + node
    let e1 = Event::Create { entity_id: 1, kind: 0 };
    let e2 = Event::Create { entity_id: 2, kind: 0 };
    let a = indexed(&e1, 100, node(1));
    let b = indexed(&e2, 100, node(1));
    assert_ne!(a.cci, b.cci);
}

#[test]
fn cci_does_not_depend_on_call_time() {
    // Structural proof: same inputs separated by wall-clock time produce identical CCI.
    let bytes = encode(&Event::Create { entity_id: 1, kind: 0 });
    let h = sha256_event_hash(&bytes);
    let cci1 = Cci::compute(42, node(7), h);
    std::thread::sleep(std::time::Duration::from_millis(1));
    let cci2 = Cci::compute(42, node(7), h);
    assert_eq!(cci1, cci2);
}

#[test]
fn sha256_hash_is_stable() {
    let bytes = encode(&Event::Reject { entity_id: 9, reason_code: 500 });
    assert_eq!(sha256_event_hash(&bytes), sha256_event_hash(&bytes));
}

#[test]
fn sha256_hash_differs_for_different_events() {
    let a = sha256_event_hash(&encode(&Event::Commit { entity_id: 1 }));
    let b = sha256_event_hash(&encode(&Event::Commit { entity_id: 2 }));
    assert_ne!(a, b);
}

// --- order() ---

#[test]
fn order_empty() {
    assert!(order(std::iter::empty()).is_empty());
}

#[test]
fn order_single_event() {
    let e = indexed(&Event::Commit { entity_id: 1 }, 1, node(0));
    let out = order([e.clone()]);
    assert_eq!(out.len(), 1);
    assert_eq!(out[0].cci, e.cci);
}

#[test]
fn order_produces_strictly_ascending_cci() {
    let events = vec![
        indexed(&Event::Create { entity_id: 3, kind: 0 }, 3, node(0)),
        indexed(&Event::Create { entity_id: 1, kind: 0 }, 1, node(0)),
        indexed(&Event::Create { entity_id: 2, kind: 0 }, 2, node(0)),
    ];
    let out = order(events);
    for w in out.windows(2) {
        assert!(w[0].cci < w[1].cci);
    }
}

#[test]
fn order_is_deterministic_regardless_of_input_order() {
    let events: Vec<IndexedEvent> = (0..5u64)
        .map(|i| indexed(&Event::Create { entity_id: i, kind: 0 }, i, node(0)))
        .collect();
    let forward  = order(events.clone());
    let reversed = order(events.iter().rev().cloned().collect::<Vec<_>>());
    let ccis_f: Vec<_> = forward.iter().map(|e| e.cci).collect();
    let ccis_r: Vec<_> = reversed.iter().map(|e| e.cci).collect();
    assert_eq!(ccis_f, ccis_r);
}

#[test]
fn order_preserves_all_events() {
    let n = 10usize;
    let events: Vec<IndexedEvent> = (0..n as u64)
        .map(|i| indexed(&Event::Reject { entity_id: i, reason_code: 0 }, i % 3, node((i % 4) as u8)))
        .collect();
    assert_eq!(order(events).len(), n);
}

#[test]
fn order_independent_of_arrival_chaos() {
    // Events arrive in adversarial order (reversed tick, mixed nodes)
    let mut chaotic: Vec<IndexedEvent> = (0..8u64)
        .map(|i| indexed(&Event::Update { entity_id: i, field: 0, value: i }, 7 - i, node((i % 3) as u8)))
        .collect();
    let ordered = order(chaotic.clone());
    // Shuffle and re-order
    chaotic.reverse();
    let reordered = order(chaotic);
    let c1: Vec<_> = ordered.iter().map(|e| e.cci).collect();
    let c2: Vec<_> = reordered.iter().map(|e| e.cci).collect();
    assert_eq!(c1, c2);
}

// --- merge_ordered() — partition stability ---

#[test]
fn merge_ordered_satisfies_partition_stability() {
    // order(A ∪ B) = merge_ordered(order(A), order(B)) for any partition A, B
    let all: Vec<IndexedEvent> = (0..10u64)
        .map(|i| indexed(&Event::Create { entity_id: i, kind: 0 }, i, node(0)))
        .collect();
    let (a, b): (Vec<_>, Vec<_>) = all.iter().cloned().partition(|e| e.tick % 2 == 0);
    let full   = order(all.clone());
    let merged = merge_ordered(order(a), order(b));
    let c_full:   Vec<_> = full.iter().map(|e| e.cci).collect();
    let c_merged: Vec<_> = merged.iter().map(|e| e.cci).collect();
    assert_eq!(c_full, c_merged);
}

#[test]
fn merge_result_independent_of_partition_choice() {
    let all: Vec<IndexedEvent> = (0..8u64)
        .map(|i| indexed(&Event::Update { entity_id: i, field: 0, value: i }, i, node(0)))
        .collect();
    let (p1a, p1b): (Vec<_>, Vec<_>) = all.iter().cloned().partition(|e| e.tick < 4);
    let (p2a, p2b): (Vec<_>, Vec<_>) = all.iter().cloned().partition(|e| e.tick % 3 == 0);
    let m1: Vec<_> = merge_ordered(order(p1a), order(p1b)).into_iter().map(|e| e.cci).collect();
    let m2: Vec<_> = merge_ordered(order(p2a), order(p2b)).into_iter().map(|e| e.cci).collect();
    assert_eq!(m1, m2);
}

#[test]
fn merge_with_empty_right_is_identity() {
    let events: Vec<IndexedEvent> = (0..4u64)
        .map(|i| indexed(&Event::Commit { entity_id: i }, i, node(0)))
        .collect();
    let expected: Vec<_> = order(events.clone()).into_iter().map(|e| e.cci).collect();
    let got: Vec<_> = merge_ordered(order(events), vec![]).into_iter().map(|e| e.cci).collect();
    assert_eq!(expected, got);
}

#[test]
fn merge_with_empty_left_is_identity() {
    let events: Vec<IndexedEvent> = (0..4u64)
        .map(|i| indexed(&Event::Commit { entity_id: i }, i, node(0)))
        .collect();
    let expected: Vec<_> = order(events.clone()).into_iter().map(|e| e.cci).collect();
    let got: Vec<_> = merge_ordered(vec![], order(events)).into_iter().map(|e| e.cci).collect();
    assert_eq!(expected, got);
}

#[test]
fn merge_both_empty_is_empty() {
    assert!(merge_ordered(vec![], vec![]).is_empty());
}
