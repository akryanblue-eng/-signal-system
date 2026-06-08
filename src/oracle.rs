/// CI trace equivalence oracle.
///
/// Two execution runs are identical iff their ordered canonical byte traces
/// produce identical hashes here. This is the external falsification surface:
/// CI injects adversarial conditions and then asserts hash equality.
///
/// Length-prefixed framing prevents hash collisions from byte concatenation
/// (i.e., [AB, C] ≠ [A, BC] even though raw concatenation would be identical).

pub fn trace_hash(traces: impl IntoIterator<Item = Vec<u8>>) -> [u8; 32] {
    let mut hasher = blake3::Hasher::new();
    for bytes in traces {
        // 4-byte LE length prefix before each frame
        hasher.update(&(bytes.len() as u32).to_le_bytes());
        hasher.update(&bytes);
    }
    *hasher.finalize().as_bytes()
}

/// Convenience: hash a ledger's full ordered trace directly.
pub fn ledger_hash(ordered_bytes: &[Vec<u8>]) -> [u8; 32] {
    trace_hash(ordered_bytes.iter().cloned())
}
