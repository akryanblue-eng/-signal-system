// Field-level RI-0 encoding trace.
//
// Records the exact byte sequences fed to SHA256 for each packet field.
// Two implementations that produce identical field bytes are guaranteed to
// produce identical RI-0 commits — so field comparison is sufficient for
// divergence attribution without SHA256 internals.

use dsvm_core::{encode_signals, WitnessPacket304};
use serde_json::{json, Value};
use std::collections::BTreeMap;

pub struct WitnessLog {
    pub vector_id: String,
    pub ri0_commit: String,
    pub fields: Vec<Value>,
}

impl WitnessLog {
    pub fn generate(id: &str, packet: &WitnessPacket304) -> Self {
        let commit: [u8; 32] = dsvm_core::ri0_replay(packet);

        // ---- run_id (u16 length-prefix + utf8 bytes) ----
        let run_id_bytes = packet.run_id.as_bytes();
        let run_id_lp = (run_id_bytes.len() as u16).to_be_bytes();

        // ---- prev_state (u32 length-prefix + bytes) ----
        let prev_lp = (packet.prev_state_bytes.len() as u32).to_be_bytes();

        // ---- frozen_batch (u32 length-prefix + bytes) ----
        let frozen_lp = (packet.frozen_batch_bytes.len() as u32).to_be_bytes();

        // ---- signals (dedup + sort, then u32 length-prefix + encoded bytes) ----
        let sig_encoded = encode_signals(&packet.signals);
        let sig_lp = (sig_encoded.len() as u32).to_be_bytes();

        // Reconstruct dedup result for display (last-value-wins, BTreeMap gives lex order)
        let mut deduped: BTreeMap<String, i64> = BTreeMap::new();
        for (k, v) in &packet.signals {
            deduped.insert(k.clone(), *v);
        }
        let after_dedup: Vec<Value> = deduped
            .iter()
            .map(|(k, v)| json!([k, v]))
            .collect();

        // Per-signal encoding breakdown (key bytes + i64 BE)
        let signal_steps: Vec<Value> = deduped
            .iter()
            .map(|(k, v)| {
                let kb = k.as_bytes();
                let mut enc = Vec::new();
                enc.extend_from_slice(&(kb.len() as u16).to_be_bytes());
                enc.extend_from_slice(kb);
                enc.extend_from_slice(&v.to_be_bytes());
                json!({
                    "key": k,
                    "value": v,
                    "key_length_prefix": hex::encode((kb.len() as u16).to_be_bytes()),
                    "key_bytes": hex::encode(kb),
                    "value_bytes": hex::encode(v.to_be_bytes()),
                    "encoding_hex": hex::encode(&enc),
                })
            })
            .collect();

        let fields = vec![
            json!({
                "field": "run_id",
                "length_prefix": hex::encode(run_id_lp),
                "bytes": hex::encode(run_id_bytes),
            }),
            json!({
                "field": "prev_state",
                "length_prefix": hex::encode(prev_lp),
                "bytes": hex::encode(&packet.prev_state_bytes),
            }),
            json!({
                "field": "frozen_batch",
                "length_prefix": hex::encode(frozen_lp),
                "bytes": hex::encode(&packet.frozen_batch_bytes),
            }),
            json!({
                "field": "bundle_hash",
                "bytes": hex::encode(packet.bundle_hash),
            }),
            json!({
                "field": "bundle_version",
                "bytes": hex::encode(packet.bundle_version.to_be_bytes()),
            }),
            json!({
                "field": "validator_pubkey",
                "bytes": hex::encode(packet.validator_pubkey),
            }),
            json!({
                "field": "signals",
                "raw": packet.signals.iter().map(|(k, v)| json!([k, v])).collect::<Vec<_>>(),
                "after_dedup": after_dedup,
                "signal_steps": signal_steps,
                "length_prefix": hex::encode(sig_lp),
                "bytes": hex::encode(&sig_encoded),
            }),
        ];

        Self {
            vector_id: id.to_string(),
            ri0_commit: hex::encode(commit),
            fields,
        }
    }

    pub fn to_json(&self) -> String {
        let v = json!({
            "vector_id": self.vector_id,
            "ri0_commit": self.ri0_commit,
            "fields": self.fields,
        });
        serde_json::to_string_pretty(&v).unwrap()
    }
}

pub fn load_log(path: &str) -> (String, String, Vec<Value>) {
    let src = std::fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("read {path}: {e}"));
    let v: Value = serde_json::from_str(&src)
        .unwrap_or_else(|e| panic!("parse {path}: {e}"));
    let vector_id = v["vector_id"].as_str().unwrap_or("").to_string();
    let ri0_commit = v["ri0_commit"].as_str().unwrap_or("").to_string();
    let fields = v["fields"].as_array().cloned().unwrap_or_default();
    (vector_id, ri0_commit, fields)
}
