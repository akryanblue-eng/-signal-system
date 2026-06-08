/// CI trace equivalence oracle and hash chain primitives.
use crate::codec::{encode_compiled_state, encode_entity_map};
use crate::event::CompiledState;
use std::collections::BTreeMap;

/// Ordered trace hash with length-prefix framing.
/// [AB, C] ≠ [A, BC] even though raw concatenation would collide.
pub fn trace_hash(traces: impl IntoIterator<Item = Vec<u8>>) -> [u8; 32] {
    let mut hasher = blake3::Hasher::new();
    for bytes in traces {
        hasher.update(&(bytes.len() as u32).to_le_bytes());
        hasher.update(&bytes);
    }
    *hasher.finalize().as_bytes()
}

/// Convenience: hash a ledger's full ordered trace.
pub fn ledger_hash(ordered_bytes: &[Vec<u8>]) -> [u8; 32] {
    trace_hash(ordered_bytes.iter().cloned())
}

/// Advance the event chain hash by one event's canonical bytes.
/// Length-prefixed so that the boundary between chain state and payload is unambiguous.
pub fn chain_advance(current: &[u8; 32], event_bytes: &[u8]) -> [u8; 32] {
    let mut h = blake3::Hasher::new();
    h.update(current);
    h.update(&(event_bytes.len() as u32).to_le_bytes());
    h.update(event_bytes);
    *h.finalize().as_bytes()
}

/// Hash the canonical entity map encoding to produce state_hash.
pub fn state_value_hash(entity_bytes: &[u8]) -> [u8; 32] {
    *blake3::hash(entity_bytes).as_bytes()
}

/// Combine state_hash and event_chain_hash into the canonical state proof (CSP).
pub fn compute_csp(state_hash: &[u8; 32], event_chain_hash: &[u8; 32]) -> [u8; 32] {
    let mut h = blake3::Hasher::new();
    h.update(state_hash);
    h.update(event_chain_hash);
    *h.finalize().as_bytes()
}

/// Two states are converged iff their full canonical encodings are byte-equal.
/// Per spec §6: equality is byte equality of encoded state, not structural equality.
pub fn states_converged(a: &CompiledState, b: &CompiledState) -> bool {
    encode_compiled_state(a) == encode_compiled_state(b)
}

/// Convenience: compute state_hash directly from an entity map reference.
pub fn entity_map_hash(entities: &BTreeMap<u64, crate::event::EntityRecord>) -> [u8; 32] {
    state_value_hash(&encode_entity_map(entities))
}
