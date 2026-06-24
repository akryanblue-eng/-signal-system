//! EdgeExtractor.v1 Registry and `registry_hash` — spec §10.
//!
//! The registry is a single frozen JSON document:
//! ```json
//! {
//!   "version": "edge_extractor.v1",
//!   "recognizers": {
//!     "<RECOGNIZER_ID>": {
//!       "input_domain": "<string>",
//!       "match_rule": "<string>",
//!       "edge_type": "<string>"
//!     },
//!     ...
//!   }
//! }
//! ```
//! `registry_hash` = `sha256(canon_json(<the entire registry document,
//! exactly as loaded>))`, hex-encoded.
//!
//! Because "exactly as loaded" implies we must hash whatever JSON
//! document was actually given to us -- not a re-typed, schema-shaped
//! Rust struct that might silently normalize or drop fields the spec
//! doesn't anticipate -- this module loads the registry as a generic
//! `serde_json::Value` (parsing only; serde_json's *serializer* is never
//! used for the actual hash bytes) and converts it to our own
//! `canon_json::Value` model for canonical encoding, by hand, field by
//! field. This preserves "exactly as loaded" fidelity (including any
//! extra/unexpected fields a real registry document might contain)
//! while still routing the actual canonical-JSON byte production through
//! our own §3 implementation rather than any third-party canonicalizer.

use crate::canon_json::{canon_json, Value as CanonValue};
use serde_json::Value as JsonValue;
use sha2::{Digest, Sha256};

/// Error raised when a registry document cannot be converted to our
/// canonical JSON value model (i.e. it isn't representable -- contains
/// a non-integer/non-finite number, which §3 explicitly leaves
/// undefined, or some other JSON shape canon_json has no rule for).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RegistryError(pub String);

impl std::fmt::Display for RegistryError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for RegistryError {}

/// Convert an arbitrary `serde_json::Value` (as produced by parsing a
/// loaded JSON document) into our hand-rolled `canon_json::Value` model,
/// preserving structure exactly. This is a faithful, lossless transcription
/// for every JSON shape canon_json (§3) actually defines: null, bool,
/// integer, string, array, object. A non-integer or non-finite number
/// has no defined canon_json encoding per §3's own text ("are not
/// defined") -- rather than silently truncating/rounding such a number,
/// we reject with an error (see QUESTIONS.md).
pub fn json_to_canon(value: &JsonValue) -> Result<CanonValue, RegistryError> {
    match value {
        JsonValue::Null => Ok(CanonValue::Null),
        JsonValue::Bool(b) => Ok(CanonValue::Bool(*b)),
        JsonValue::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(CanonValue::Int(i))
            } else {
                Err(RegistryError(format!(
                    "number {} is not representable as an integer (canon_json defines no encoding for non-integer/non-finite numbers per §3)",
                    n
                )))
            }
        }
        JsonValue::String(s) => Ok(CanonValue::Str(s.clone())),
        JsonValue::Array(items) => {
            let converted: Result<Vec<CanonValue>, RegistryError> =
                items.iter().map(json_to_canon).collect();
            Ok(CanonValue::Arr(converted?))
        }
        JsonValue::Object(map) => {
            let mut pairs = Vec::with_capacity(map.len());
            for (k, v) in map.iter() {
                pairs.push((k.clone(), json_to_canon(v)?));
            }
            Ok(CanonValue::Obj(pairs))
        }
    }
}

/// Compute `registry_hash` for a registry document, given as an already
/// -parsed `serde_json::Value` representing "the entire registry
/// document, exactly as loaded" (§10). Returns the hex-encoded SHA-256
/// digest of `canon_json(document)`.
pub fn registry_hash(document: &JsonValue) -> Result<String, RegistryError> {
    let canon_value = json_to_canon(document)?;
    let bytes = canon_json(&canon_value);
    let digest = Sha256::digest(&bytes);
    Ok(hex_encode(&digest))
}

/// Convenience: compute `registry_hash` directly from a raw JSON text
/// string (e.g. the literal contents of a registry file on disk).
/// Parsing uses `serde_json` purely as a generic JSON *parser* (not as
/// the canonicalizer -- see module docs).
pub fn registry_hash_from_str(json_text: &str) -> Result<String, RegistryError> {
    let parsed: JsonValue = serde_json::from_str(json_text)
        .map_err(|e| RegistryError(format!("invalid JSON: {}", e)))?;
    registry_hash(&parsed)
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

    #[test]
    fn registry_hash_deterministic() {
        let doc = json!({
            "version": "edge_extractor.v1",
            "recognizers": {
                "PY_IMPORT": {
                    "input_domain": "python_source",
                    "match_rule": "import_statement",
                    "edge_type": "IMPORTS"
                }
            }
        });
        let h1 = registry_hash(&doc).unwrap();
        let h2 = registry_hash(&doc).unwrap();
        assert_eq!(h1, h2);
        assert_eq!(h1.len(), 64);
    }

    #[test]
    fn registry_hash_matches_hand_built_canon_json() {
        let doc = json!({
            "version": "edge_extractor.v1",
            "recognizers": {
                "PY_IMPORT": {
                    "input_domain": "python_source",
                    "match_rule": "import_statement",
                    "edge_type": "IMPORTS"
                }
            }
        });
        // Hand-sort all keys at every level per §3:
        // top-level: "recognizers", "version" (r < v)
        // recognizers object: just "PY_IMPORT"
        // inner object: "edge_type", "input_domain", "match_rule"
        let expected = r#"{"recognizers":{"PY_IMPORT":{"edge_type":"IMPORTS","input_domain":"python_source","match_rule":"import_statement"}},"version":"edge_extractor.v1"}"#;
        let digest = Sha256::digest(expected.as_bytes());
        let expected_hash = hex_encode(&digest);
        assert_eq!(registry_hash(&doc).unwrap(), expected_hash);
    }

    #[test]
    fn registry_hash_changes_if_any_field_changes() {
        let doc1 = json!({
            "version": "edge_extractor.v1",
            "recognizers": {
                "A": {"input_domain": "x", "match_rule": "y", "edge_type": "Z"}
            }
        });
        let doc2 = json!({
            "version": "edge_extractor.v1",
            "recognizers": {
                "A": {"input_domain": "x", "match_rule": "y", "edge_type": "DIFFERENT"}
            }
        });
        assert_ne!(registry_hash(&doc1).unwrap(), registry_hash(&doc2).unwrap());
    }

    #[test]
    fn registry_hash_changes_if_recognizer_set_changes() {
        let doc1 = json!({
            "version": "edge_extractor.v1",
            "recognizers": {
                "A": {"input_domain": "x", "match_rule": "y", "edge_type": "Z"}
            }
        });
        let doc2 = json!({
            "version": "edge_extractor.v1",
            "recognizers": {
                "A": {"input_domain": "x", "match_rule": "y", "edge_type": "Z"},
                "B": {"input_domain": "x2", "match_rule": "y2", "edge_type": "Z2"}
            }
        });
        assert_ne!(registry_hash(&doc1).unwrap(), registry_hash(&doc2).unwrap());
    }

    #[test]
    fn registry_hash_from_str_matches_value_based() {
        let text = r#"{"version":"edge_extractor.v1","recognizers":{}}"#;
        let from_str = registry_hash_from_str(text).unwrap();
        let value: JsonValue = serde_json::from_str(text).unwrap();
        let from_value = registry_hash(&value).unwrap();
        assert_eq!(from_str, from_value);
    }

    #[test]
    fn non_integer_number_in_registry_rejected() {
        let doc = json!({"version": "x", "recognizers": {}, "weird_float_field": 1.5});
        let result = registry_hash(&doc);
        assert!(result.is_err());
    }

    #[test]
    fn decimal_point_literal_rejected_even_when_integer_valued() {
        // Confirmed via this test: serde_json's Number::as_i64() returns
        // None for a JSON literal written with a decimal point (e.g.
        // "1.0"), even though its mathematical value is an integer --
        // serde_json tracks "was this written as a float" at parse time
        // and as_i64() respects that distinction. So a registry document
        // containing "1.0" is rejected by json_to_canon, consistent with
        // the chosen "fail loudly on anything not unambiguously an
        // integer" policy (see QUESTIONS.md Q10).
        let doc_text = r#"{"version":"x","recognizers":{},"n":1.0}"#;
        let result = registry_hash_from_str(doc_text);
        assert!(result.is_err(), "1.0 should not be treated as integer 1");
    }

    #[test]
    fn empty_recognizers_map() {
        let doc = json!({"version": "edge_extractor.v1", "recognizers": {}});
        let expected = r#"{"recognizers":{},"version":"edge_extractor.v1"}"#;
        let digest = Sha256::digest(expected.as_bytes());
        let expected_hash = hex_encode(&digest);
        assert_eq!(registry_hash(&doc).unwrap(), expected_hash);
    }
}
