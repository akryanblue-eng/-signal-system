//! ProofV1 Schema — spec §9.
//!
//! A `ProofV1` object is a JSON object with exactly 7 required keys
//! (§9's table). §9.1 defines fail-closed verifier semantics. §9.2
//! defines the `schema_descriptor` and `proof_schema_hash`.
//!
//! For `verify_proof_schema`'s `{"obj": <any JSON value>}` argument
//! (§11.1), the candidate can be *any* JSON value (object, array,
//! primitive) -- so we accept a `serde_json::Value` here purely as a
//! generic "arbitrary JSON" parse/representation type (not as a
//! canonical-JSON encoder; canon_json.rs is the hand-rolled encoder used
//! for actual hashing). This is consistent with the experiment's ground
//! rules: serde_json::Value is generic JSON infrastructure, and none of
//! the *validation logic* below is delegated to a third-party schema
//! validator -- every rule in §9.1's bullet list is checked by hand.

use crate::canon_json::{canon_json, Value as CanonValue};
use serde_json::Value as JsonValue;
use sha2::{Digest, Sha256};

/// The exact 7 required keys of a ProofV1 object, per §9's table, in the
/// order the table lists them (this order is NOT itself normative --
/// §9.2 requires the descriptor's `required_fields` to be independently
/// sorted -- but we keep this list as the source of truth for "exactly
/// these 7 keys, no others").
pub const REQUIRED_FIELDS: [&str; 7] = [
    "spec_version",
    "hash_alg_id",
    "snapshot_mode",
    "snapshot_id",
    "extractor_version",
    "result",
    "proof_payload",
];

const SNAPSHOT_MODES: [&str; 2] = ["git_tree", "manifest"];
const RESULTS: [&str; 2] = ["FAIL", "PASS"];

/// Verify that `candidate` is a valid `ProofV1` instance per §9.1's
/// fail-closed rules. Returns `true` iff *all* of the following hold:
/// - candidate is a JSON object (not array, not primitive)
/// - its key set is EXACTLY the 7 required keys (no missing, no extra)
/// - every field satisfies its type/value constraint from §9's table
pub fn verify_proof_schema(candidate: &JsonValue) -> bool {
    let obj = match candidate.as_object() {
        Some(o) => o,
        None => return false,
    };

    // Key set must be EXACTLY the 7 required keys: no missing, no extra.
    if obj.len() != REQUIRED_FIELDS.len() {
        return false;
    }
    for key in obj.keys() {
        if !REQUIRED_FIELDS.contains(&key.as_str()) {
            return false; // unknown/extra key
        }
    }
    for required in REQUIRED_FIELDS.iter() {
        if !obj.contains_key(*required) {
            return false; // missing required key
        }
    }

    // Per-field type/value constraints.
    if !is_exact_string(&obj["spec_version"], "nic.proof.v1") {
        return false;
    }
    if !is_exact_string(&obj["hash_alg_id"], "sha256") {
        return false;
    }
    if !is_string_in(&obj["snapshot_mode"], &SNAPSHOT_MODES) {
        return false;
    }
    if !is_non_empty_string(&obj["snapshot_id"]) {
        return false;
    }
    if !is_non_empty_string(&obj["extractor_version"]) {
        return false;
    }
    if !is_string_in(&obj["result"], &RESULTS) {
        return false;
    }
    // proof_payload: any well-formed JSON object; not further
    // constrained. A serde_json::Value that we've already parsed is by
    // construction well-formed JSON, so we only need to check it's an
    // object (not array/primitive) -- see QUESTIONS.md Q9.
    if !obj["proof_payload"].is_object() {
        return false;
    }

    true
}

fn is_exact_string(v: &JsonValue, expected: &str) -> bool {
    matches!(v, JsonValue::String(s) if s == expected)
}

fn is_string_in(v: &JsonValue, allowed: &[&str]) -> bool {
    matches!(v, JsonValue::String(s) if allowed.contains(&s.as_str()))
}

fn is_non_empty_string(v: &JsonValue) -> bool {
    matches!(v, JsonValue::String(s) if !s.is_empty())
}

/// Build the §9.2 `schema_descriptor` value.
fn schema_descriptor() -> CanonValue {
    let mut required_fields_sorted = REQUIRED_FIELDS.to_vec();
    required_fields_sorted.sort();
    let mut snapshot_modes_sorted = SNAPSHOT_MODES.to_vec();
    snapshot_modes_sorted.sort();
    let mut results_sorted = RESULTS.to_vec();
    results_sorted.sort();

    CanonValue::obj(vec![
        ("spec_version", CanonValue::str("nic.proof.v1")),
        ("hash_alg_id", CanonValue::str("sha256")),
        (
            "required_fields",
            CanonValue::arr(
                required_fields_sorted
                    .into_iter()
                    .map(CanonValue::str)
                    .collect(),
            ),
        ),
        (
            "snapshot_modes",
            CanonValue::arr(
                snapshot_modes_sorted
                    .into_iter()
                    .map(CanonValue::str)
                    .collect(),
            ),
        ),
        (
            "results",
            CanonValue::arr(results_sorted.into_iter().map(CanonValue::str).collect()),
        ),
    ])
}

/// Compute `proof_schema_hash` per §9.2:
/// `sha256(canon_json(schema_descriptor))`, hex-encoded.
pub fn proof_schema_hash() -> String {
    let descriptor = schema_descriptor();
    let bytes = canon_json(&descriptor);
    let digest = Sha256::digest(&bytes);
    hex_encode(&digest)
}

fn hex_encode(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{:02x}", b));
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn valid_proof() -> JsonValue {
        json!({
            "spec_version": "nic.proof.v1",
            "hash_alg_id": "sha256",
            "snapshot_mode": "git_tree",
            "snapshot_id": "abc123",
            "extractor_version": "deadbeef",
            "result": "PASS",
            "proof_payload": {}
        })
    }

    #[test]
    fn valid_proof_passes() {
        assert!(verify_proof_schema(&valid_proof()));
    }

    #[test]
    fn valid_proof_with_fail_result_passes() {
        let mut p = valid_proof();
        p["result"] = json!("FAIL");
        assert!(verify_proof_schema(&p));
    }

    #[test]
    fn valid_proof_with_manifest_snapshot_mode_passes() {
        let mut p = valid_proof();
        p["snapshot_mode"] = json!("manifest");
        assert!(verify_proof_schema(&p));
    }

    #[test]
    fn non_object_candidate_fails() {
        assert!(!verify_proof_schema(&json!([1, 2, 3])));
        assert!(!verify_proof_schema(&json!("a string")));
        assert!(!verify_proof_schema(&json!(42)));
        assert!(!verify_proof_schema(&json!(null)));
        assert!(!verify_proof_schema(&json!(true)));
    }

    #[test]
    fn missing_required_field_fails() {
        let mut p = valid_proof();
        p.as_object_mut().unwrap().remove("snapshot_id");
        assert!(!verify_proof_schema(&p));
    }

    #[test]
    fn extra_unknown_field_fails() {
        let mut p = valid_proof();
        p.as_object_mut()
            .unwrap()
            .insert("extra_field".to_string(), json!("oops"));
        assert!(!verify_proof_schema(&p));
    }

    #[test]
    fn wrong_spec_version_fails() {
        let mut p = valid_proof();
        p["spec_version"] = json!("nic.proof.v2");
        assert!(!verify_proof_schema(&p));
    }

    #[test]
    fn wrong_hash_alg_id_fails() {
        let mut p = valid_proof();
        p["hash_alg_id"] = json!("sha512");
        assert!(!verify_proof_schema(&p));
    }

    #[test]
    fn invalid_snapshot_mode_fails() {
        let mut p = valid_proof();
        p["snapshot_mode"] = json!("something_else");
        assert!(!verify_proof_schema(&p));
    }

    #[test]
    fn empty_snapshot_id_fails() {
        let mut p = valid_proof();
        p["snapshot_id"] = json!("");
        assert!(!verify_proof_schema(&p));
    }

    #[test]
    fn empty_extractor_version_fails() {
        let mut p = valid_proof();
        p["extractor_version"] = json!("");
        assert!(!verify_proof_schema(&p));
    }

    #[test]
    fn result_diagnostic_fails() {
        // DIAGNOSTIC is explicitly never a value of `result` per §9.3.
        let mut p = valid_proof();
        p["result"] = json!("DIAGNOSTIC");
        assert!(!verify_proof_schema(&p));
    }

    #[test]
    fn wrong_type_for_string_field_fails() {
        let mut p = valid_proof();
        p["snapshot_id"] = json!(123);
        assert!(!verify_proof_schema(&p));
    }

    #[test]
    fn proof_payload_must_be_object_not_array_or_primitive() {
        let mut p = valid_proof();
        p["proof_payload"] = json!([1, 2, 3]);
        assert!(!verify_proof_schema(&p));

        let mut p2 = valid_proof();
        p2["proof_payload"] = json!("a string");
        assert!(!verify_proof_schema(&p2));
    }

    #[test]
    fn proof_payload_arbitrary_object_contents_ok() {
        let mut p = valid_proof();
        p["proof_payload"] = json!({"nested": {"a": [1,2,3]}, "x": true});
        assert!(verify_proof_schema(&p));
    }

    #[test]
    fn proof_schema_hash_is_deterministic_and_64_hex_chars() {
        let h1 = proof_schema_hash();
        let h2 = proof_schema_hash();
        assert_eq!(h1, h2);
        assert_eq!(h1.len(), 64);
        assert!(h1
            .chars()
            .all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase()));
    }

    #[test]
    fn proof_schema_hash_matches_hand_built_descriptor_json() {
        // Hand-construct the exact expected canon_json string per §9.2's
        // descriptor shape and sorting rules, independently of the
        // schema_descriptor() function, to cross-check the hash.
        let expected_json = r#"{"hash_alg_id":"sha256","required_fields":["extractor_version","hash_alg_id","proof_payload","result","snapshot_id","snapshot_mode","spec_version"],"results":["FAIL","PASS"],"snapshot_modes":["git_tree","manifest"],"spec_version":"nic.proof.v1"}"#;
        let digest = Sha256::digest(expected_json.as_bytes());
        let expected_hash = hex_encode(&digest);
        assert_eq!(proof_schema_hash(), expected_hash);
    }
}
