use signal_system::codec::encode;
use signal_system::event::Event;
use signal_system::kernel::{compile, genesis, transition};
use signal_system::oracle::{
    chain_advance, compute_csp, entity_map_hash, ledger_hash, state_value_hash, states_converged,
    trace_hash,
};

// --- trace_hash ---

#[test]
fn identical_traces_produce_identical_hashes() {
    let trace: Vec<Vec<u8>> = vec![
        encode(&Event::Create { entity_id: 1, kind: 5 }),
        encode(&Event::Commit { entity_id: 1 }),
    ];
    assert_eq!(trace_hash(trace.clone()), trace_hash(trace));
}

#[test]
fn different_traces_produce_different_hashes() {
    let a: Vec<Vec<u8>> = vec![encode(&Event::Commit { entity_id: 1 })];
    let b: Vec<Vec<u8>> = vec![encode(&Event::Commit { entity_id: 2 })];
    assert_ne!(trace_hash(a), trace_hash(b));
}

#[test]
fn trace_hash_is_order_sensitive() {
    let e1 = encode(&Event::Create { entity_id: 1, kind: 0 });
    let e2 = encode(&Event::Create { entity_id: 2, kind: 0 });
    assert_ne!(trace_hash([e1.clone(), e2.clone()]), trace_hash([e2, e1]));
}

#[test]
fn length_prefix_prevents_concatenation_collision() {
    let ab = b"AB".to_vec();
    let c  = b"C".to_vec();
    let a  = b"A".to_vec();
    let bc = b"BC".to_vec();
    assert_ne!(trace_hash([ab, c]), trace_hash([a, bc]));
}

#[test]
fn empty_trace_has_stable_hash() {
    assert_eq!(trace_hash(std::iter::empty()), trace_hash(std::iter::empty()));
}

#[test]
fn single_bit_mutation_changes_trace_hash() {
    let original: Vec<Vec<u8>> = vec![encode(&Event::Create { entity_id: 1, kind: 5 })];
    let mut mutated = original.clone();
    mutated[0][4] ^= 0x01;
    assert_ne!(trace_hash(original), trace_hash(mutated));
}

#[test]
fn ledger_hash_matches_trace_hash() {
    let trace: Vec<Vec<u8>> = vec![
        encode(&Event::Create { entity_id: 1, kind: 0 }),
        encode(&Event::Reject { entity_id: 1, reason_code: 99 }),
    ];
    assert_eq!(ledger_hash(&trace), trace_hash(trace.clone()));
}

// --- chain_advance ---

#[test]
fn chain_advance_is_deterministic() {
    let start = [0u8; 32];
    let bytes = encode(&Event::Commit { entity_id: 1 });
    assert_eq!(chain_advance(&start, &bytes), chain_advance(&start, &bytes));
}

#[test]
fn chain_advance_is_sensitive_to_chain_state() {
    let a = [0u8; 32];
    let b = [1u8; 32];
    let bytes = encode(&Event::Commit { entity_id: 1 });
    assert_ne!(chain_advance(&a, &bytes), chain_advance(&b, &bytes));
}

#[test]
fn chain_advance_is_sensitive_to_event_bytes() {
    let start = [0u8; 32];
    let e1 = encode(&Event::Commit { entity_id: 1 });
    let e2 = encode(&Event::Commit { entity_id: 2 });
    assert_ne!(chain_advance(&start, &e1), chain_advance(&start, &e2));
}

// --- state_value_hash / entity_map_hash ---

#[test]
fn state_value_hash_is_deterministic() {
    let bytes = b"same input";
    assert_eq!(state_value_hash(bytes), state_value_hash(bytes));
}

#[test]
fn entity_map_hash_changes_after_create() {
    let s0 = genesis();
    let s1 = transition(s0.clone(), &Event::Create { entity_id: 1, kind: 0 });
    let h0 = entity_map_hash(&s0.entities);
    let h1 = entity_map_hash(&s1.entities);
    assert_ne!(h0, h1);
}

#[test]
fn entity_map_hash_unchanged_after_reject() {
    let s0 = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let s1 = transition(s0.clone(), &Event::Reject { entity_id: 1, reason_code: 0 });
    assert_eq!(entity_map_hash(&s0.entities), entity_map_hash(&s1.entities));
}

// --- compute_csp ---

#[test]
fn csp_is_deterministic() {
    let sh = [1u8; 32];
    let ch = [2u8; 32];
    assert_eq!(compute_csp(&sh, &ch), compute_csp(&sh, &ch));
}

#[test]
fn csp_differs_when_state_hash_differs() {
    let ch = [0u8; 32];
    assert_ne!(compute_csp(&[1u8; 32], &ch), compute_csp(&[2u8; 32], &ch));
}

#[test]
fn csp_differs_when_event_chain_hash_differs() {
    let sh = [0u8; 32];
    assert_ne!(compute_csp(&sh, &[1u8; 32]), compute_csp(&sh, &[2u8; 32]));
}

// --- states_converged ---

#[test]
fn converged_true_for_same_events() {
    let events = vec![
        Event::Create { entity_id: 1, kind: 5 },
        Event::Update { entity_id: 1, field: 0, value: 42 },
        Event::Commit { entity_id: 1 },
    ];
    let a = compile(genesis(), events.clone());
    let b = compile(genesis(), events);
    assert!(states_converged(&a, &b));
}

#[test]
fn converged_false_after_divergent_events() {
    let e_common = Event::Create { entity_id: 1, kind: 0 };
    let a = compile(genesis(), [e_common.clone(), Event::Commit { entity_id: 1 }]);
    let b = compile(genesis(), [e_common,         Event::Reject { entity_id: 1, reason_code: 0 }]);
    assert!(!states_converged(&a, &b));
}

#[test]
fn reject_breaks_convergence_even_with_same_entities() {
    let s0 = compile(genesis(), [Event::Create { entity_id: 1, kind: 0 }]);
    let s1 = transition(s0.clone(), &Event::Reject { entity_id: 1, reason_code: 0 });
    // entity maps are equal but event chains differ → not converged
    assert_eq!(s0.entities, s1.entities);
    assert!(!states_converged(&s0, &s1));
}

#[test]
fn genesis_converges_with_itself() {
    assert!(states_converged(&genesis(), &genesis()));
}
