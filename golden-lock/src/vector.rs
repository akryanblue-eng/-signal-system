use dsvm_core::WitnessPacket304;
use serde::Deserialize;
use sha2::{Digest, Sha256};

#[derive(Debug, Deserialize)]
pub struct GoldenVector {
    pub id: String,
    #[serde(default)]
    pub description: String,
    pub run_id: String,
    pub prev_state_hex: String,
    pub frozen_batch_hex: String,
    // bundle_hash: provide hex OR a preimage string (SHA256'd at load time)
    #[serde(default)]
    pub bundle_hash_hex: String,
    #[serde(default)]
    pub bundle_hash_preimage: String,
    pub bundle_version: u32,
    // validator_pubkey: same pattern
    #[serde(default)]
    pub validator_pubkey_hex: String,
    #[serde(default)]
    pub validator_pubkey_preimage: String,
    // signals as [key, value] pairs; duplicates intentionally allowed (dedup is RI-0 logic)
    pub signals: Vec<(String, i64)>,
}

impl GoldenVector {
    pub fn to_witness(&self) -> WitnessPacket304 {
        WitnessPacket304 {
            run_id: self.run_id.clone(),
            prev_state_bytes: hex::decode(&self.prev_state_hex)
                .expect("invalid prev_state_hex"),
            frozen_batch_bytes: hex::decode(&self.frozen_batch_hex)
                .expect("invalid frozen_batch_hex"),
            bundle_hash: self.resolve_bundle_hash(),
            bundle_version: self.bundle_version,
            validator_pubkey: self.resolve_validator_pubkey(),
            signals: self.signals.clone(),
        }
    }

    fn resolve_bundle_hash(&self) -> [u8; 32] {
        if !self.bundle_hash_preimage.is_empty() {
            Sha256::digest(self.bundle_hash_preimage.as_bytes()).into()
        } else {
            hex_to_32(&self.bundle_hash_hex, "bundle_hash_hex")
        }
    }

    fn resolve_validator_pubkey(&self) -> [u8; 32] {
        if !self.validator_pubkey_preimage.is_empty() {
            Sha256::digest(self.validator_pubkey_preimage.as_bytes()).into()
        } else {
            hex_to_32(&self.validator_pubkey_hex, "validator_pubkey_hex")
        }
    }
}

fn hex_to_32(s: &str, field: &str) -> [u8; 32] {
    let bytes = hex::decode(s).unwrap_or_else(|e| panic!("invalid {field}: {e}"));
    assert_eq!(bytes.len(), 32, "{field} must be 32 bytes (64 hex chars)");
    bytes.try_into().unwrap()
}

pub fn load_vectors_from_dir(dir: &str) -> Vec<GoldenVector> {
    let mut vectors: Vec<GoldenVector> = std::fs::read_dir(dir)
        .unwrap_or_else(|e| panic!("cannot read vectors dir '{dir}': {e}"))
        .filter_map(|entry| {
            let entry = entry.ok()?;
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) == Some("json") {
                let src = std::fs::read_to_string(&path)
                    .unwrap_or_else(|e| panic!("read {}: {e}", path.display()));
                // Skip registry/manifest files (no "id" field = not a vector)
                let v: serde_json::Value = serde_json::from_str(&src)
                    .unwrap_or_else(|e| panic!("parse {}: {e}", path.display()));
                if v.get("id").is_none() {
                    return None;
                }
                Some(serde_json::from_value::<GoldenVector>(v)
                    .unwrap_or_else(|e| panic!("parse vector {}: {e}", path.display())))
            } else {
                None
            }
        })
        .collect();
    // Deterministic order: sort by vector ID
    vectors.sort_by(|a, b| a.id.cmp(&b.id));
    vectors
}
