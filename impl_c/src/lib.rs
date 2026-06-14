// RI-0 core — public library surface for dsvm-core.
// Canonical encoding must match Python (impl_a) and Go (impl_b) exactly.

use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

pub struct WitnessPacket304 {
    pub run_id: String,
    pub prev_state_bytes: Vec<u8>,
    pub frozen_batch_bytes: Vec<u8>,
    pub bundle_hash: [u8; 32],
    pub bundle_version: u32,
    pub validator_pubkey: [u8; 32],
    pub signals: Vec<(String, i64)>,
}

pub fn encode_signals(signals: &[(String, i64)]) -> Vec<u8> {
    let mut deduped: BTreeMap<String, i64> = BTreeMap::new();
    for (key, value) in signals {
        deduped.insert(key.clone(), *value);
    }
    let mut out = Vec::new();
    for (key, value) in &deduped {
        let key_bytes = key.as_bytes();
        out.extend_from_slice(&(key_bytes.len() as u16).to_be_bytes());
        out.extend_from_slice(key_bytes);
        out.extend_from_slice(&(*value as i64).to_be_bytes());
    }
    out
}

pub fn ri0_replay(p: &WitnessPacket304) -> [u8; 32] {
    let mut h = Sha256::new();
    let run_id_bytes = p.run_id.as_bytes();
    h.update((run_id_bytes.len() as u16).to_be_bytes());
    h.update(run_id_bytes);
    h.update((p.prev_state_bytes.len() as u32).to_be_bytes());
    h.update(&p.prev_state_bytes);
    h.update((p.frozen_batch_bytes.len() as u32).to_be_bytes());
    h.update(&p.frozen_batch_bytes);
    h.update(p.bundle_hash);
    h.update(p.bundle_version.to_be_bytes());
    h.update(p.validator_pubkey);
    let sig_bytes = encode_signals(&p.signals);
    h.update((sig_bytes.len() as u32).to_be_bytes());
    h.update(&sig_bytes);
    h.finalize().into()
}
