//! Manifest Format — spec §12.
//!
//! `manifest.json` is a flat JSON object with exactly 4 keys:
//! `proof_schema_hash` (§9.2), `registry_hash` (§10), `hash_alg`
//! (always `"sha256"`, §4), and `case_count` (the number of entries in
//! `cases.json`'s `"cases"` array).
//!
//! §12 does not define a new computation of its own beyond §9.2 and
//! §10 — it's a cross-check format: "a conforming implementation should
//! independently recompute `proof_schema_hash` and `registry_hash` ...
//! and confirm they match the committed manifest exactly." This module
//! provides a small `Manifest` struct plus a `matches` helper for
//! exactly that comparison; there is no golden `cases.json`/
//! `manifest.json` fixture available in this clean-room environment
//! (none was provided, per the experiment's ground rules), so this
//! module cannot be exercised against a real committed manifest here —
//! only against self-consistency (recomputing twice agrees, and a
//! manifest built from this implementation's own outputs always
//! `matches` itself).

use crate::registry::RegistryError;
use serde_json::Value as JsonValue;

/// A `manifest.json` document per §12's 4-key shape.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Manifest {
    pub proof_schema_hash: String,
    pub registry_hash: String,
    pub hash_alg: String,
    pub case_count: i64,
}

impl Manifest {
    /// Build the manifest this implementation would produce for a given
    /// registry document and case count: `proof_schema_hash` from §9.2
    /// (constant, independent of the registry), `registry_hash` from
    /// §10 (computed from `registry_document`), `hash_alg` fixed at
    /// `"sha256"` per §4, and `case_count` as supplied by the caller
    /// (this crate has no `cases.json` parser of its own, since the
    /// corpus format, §11, is for *external* conformance testing of an
    /// implementation, not part of the deterministic core being
    /// implemented).
    pub fn build(
        registry_document: &JsonValue,
        case_count: i64,
    ) -> Result<Manifest, RegistryError> {
        Ok(Manifest {
            proof_schema_hash: crate::proof::proof_schema_hash(),
            registry_hash: crate::registry::registry_hash(registry_document)?,
            hash_alg: "sha256".to_string(),
            case_count,
        })
    }

    /// Compare this manifest field-by-field against another (e.g. a
    /// committed `manifest.json` loaded from disk) for exact equality,
    /// per §12's "confirm they match the committed manifest exactly."
    pub fn matches(&self, other: &Manifest) -> bool {
        self == other
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn build_is_deterministic() {
        let doc = json!({"version": "edge_extractor.v1", "recognizers": {}});
        let m1 = Manifest::build(&doc, 5).unwrap();
        let m2 = Manifest::build(&doc, 5).unwrap();
        assert_eq!(m1, m2);
        assert!(m1.matches(&m2));
    }

    #[test]
    fn hash_alg_is_always_sha256() {
        let doc = json!({"version": "x", "recognizers": {}});
        let m = Manifest::build(&doc, 0).unwrap();
        assert_eq!(m.hash_alg, "sha256");
    }

    #[test]
    fn different_registry_yields_different_registry_hash_but_same_proof_schema_hash() {
        let doc1 = json!({"version": "x", "recognizers": {}});
        let doc2 = json!({"version": "y", "recognizers": {}});
        let m1 = Manifest::build(&doc1, 0).unwrap();
        let m2 = Manifest::build(&doc2, 0).unwrap();
        assert_ne!(m1.registry_hash, m2.registry_hash);
        assert_eq!(m1.proof_schema_hash, m2.proof_schema_hash);
        assert!(!m1.matches(&m2));
    }

    #[test]
    fn case_count_difference_breaks_match() {
        let doc = json!({"version": "x", "recognizers": {}});
        let m1 = Manifest::build(&doc, 5).unwrap();
        let m2 = Manifest::build(&doc, 6).unwrap();
        assert!(!m1.matches(&m2));
    }
}
