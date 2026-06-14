use serde::Serialize;
use sha2::{Digest, Sha256};

#[derive(Serialize)]
pub struct Manifest {
    pub schema_version: String,
    pub generator_version: String,
    pub swift_hash: String,
    pub rust_hash: String,
    pub combined_hash: String,
}

impl Manifest {
    pub fn new(swift: &str, rust: &str) -> Self {
        let swift_hash = sha256_hex(swift.as_bytes());
        let rust_hash = sha256_hex(rust.as_bytes());
        let combined_hash = {
            let mut h = Sha256::new();
            h.update(b"SCHEMA_COMPILER_V1\0SWIFT\0");
            h.update(swift.as_bytes());
            h.update(b"\0RUST\0");
            h.update(rust.as_bytes());
            format!("{:x}", h.finalize())
        };
        Self {
            schema_version: "EVENT_SCHEMAS.v1".into(),
            generator_version: "dsvm-schema-compiler@v1.0".into(),
            swift_hash,
            rust_hash,
            combined_hash,
        }
    }

    pub fn to_json(&self) -> String {
        serde_json::to_string_pretty(self).unwrap()
    }
}

fn sha256_hex(data: &[u8]) -> String {
    format!("{:x}", Sha256::digest(data))
}
