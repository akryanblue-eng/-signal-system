use crate::canonical::canonical_bytes;
use crate::types::{ReplayOkParts, VdceError, SUPPORTED_REDUCER_VERSION, SUPPORTED_SCHEMA_VERSION};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// Certification report.
///
/// Fields are in alphabetical order so that serde_json (which serializes struct
/// fields in definition order) always produces a canonical key sequence.
/// `certificate_hash` is `None` ("null") in the hash preimage and `Some(hex)`
/// in the final output — this is the frozen null-field rule.
#[derive(Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Certificate {
    pub certificate_hash: Option<String>,
    pub reducer_version: String,
    pub schema_version: u32,
    pub status: String,
    pub steps_replayed: usize,
}

/// Build a deterministic certificate from a successful replay.
///
/// Cert = SHA-256( canonical_bytes( preimage_with_hash_null ) )
pub fn certify(ok_parts: &ReplayOkParts) -> Result<Certificate, VdceError> {
    let preimage = Certificate {
        certificate_hash: None,
        reducer_version: SUPPORTED_REDUCER_VERSION.to_string(),
        schema_version: SUPPORTED_SCHEMA_VERSION,
        status: "ok".to_string(),
        steps_replayed: ok_parts.steps_replayed,
    };

    let preimage_bytes = canonical_bytes(&preimage)
        .map_err(|e| VdceError::ExecutionError {
            step_id: 0,
            reason: format!("canonical encoding error: {e}"),
        })?;

    let hash_hex = hex::encode(Sha256::digest(&preimage_bytes));

    Ok(Certificate {
        certificate_hash: Some(hash_hex),
        reducer_version: SUPPORTED_REDUCER_VERSION.to_string(),
        schema_version: SUPPORTED_SCHEMA_VERSION,
        status: "ok".to_string(),
        steps_replayed: ok_parts.steps_replayed,
    })
}
