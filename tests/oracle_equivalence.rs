use signal_system::codec::encode;
use signal_system::event::Event;
use signal_system::oracle::{ledger_hash, trace_hash};

fn trace_a() -> Vec<Vec<u8>> {
    vec![
        encode(&Event::Activate { entity_id: 1 }),
        encode(&Event::Complete { entity_id: 1 }),
    ]
}

fn trace_b() -> Vec<Vec<u8>> {
    vec![
        encode(&Event::Activate { entity_id: 1 }),
        encode(&Event::Fail { entity_id: 1, code: 503 }),
        encode(&Event::Reset { entity_id: 1 }),
        encode(&Event::Activate { entity_id: 1 }),
        encode(&Event::Complete { entity_id: 1 }),
    ]
}

#[test]
fn identical_traces_produce_identical_hashes() {
    assert_eq!(trace_hash(trace_a()), trace_hash(trace_a()));
    assert_eq!(trace_hash(trace_b()), trace_hash(trace_b()));
}

#[test]
fn different_traces_produce_different_hashes() {
    assert_ne!(trace_hash(trace_a()), trace_hash(trace_b()));
}

#[test]
fn order_matters() {
    let e1 = encode(&Event::Activate { entity_id: 1 });
    let e2 = encode(&Event::Complete { entity_id: 1 });
    let forward = trace_hash([e1.clone(), e2.clone()]);
    let reversed = trace_hash([e2, e1]);
    assert_ne!(forward, reversed, "hash must be order-sensitive");
}

#[test]
fn length_prefix_prevents_concatenation_collision() {
    // [AB, C] vs [A, BC] — same raw bytes if concatenated without framing,
    // but must produce different hashes.
    let ab = b"AB".to_vec();
    let c = b"C".to_vec();
    let a = b"A".to_vec();
    let bc = b"BC".to_vec();
    assert_ne!(trace_hash([ab, c]), trace_hash([a, bc]));
}

#[test]
fn empty_trace_has_stable_hash() {
    let h1 = trace_hash(std::iter::empty());
    let h2 = trace_hash(std::iter::empty());
    assert_eq!(h1, h2);
}

#[test]
fn single_event_mutation_changes_hash() {
    let original = trace_a();
    let mut mutated = trace_a();
    // Flip one bit in the entity_id of the first event
    mutated[0][4] ^= 0x01;
    assert_ne!(trace_hash(original), trace_hash(mutated));
}

#[test]
fn ledger_hash_matches_trace_hash() {
    let trace = trace_b();
    assert_eq!(ledger_hash(&trace), trace_hash(trace.clone()));
}
