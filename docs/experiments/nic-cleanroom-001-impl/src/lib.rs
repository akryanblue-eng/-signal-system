//! NIC v1.1 deterministic core — clean-room implementation.
//!
//! See `docs/nic-v1.1-spec.md` for the normative specification this
//! crate implements. Each module corresponds to one section of the spec:
//!
//! - [`canon_json`] — §3 Canonical JSON Encoding
//! - [`path`] — §6 Canonical Path Pipeline
//! - [`glob`] — §5 Glob Language
//! - [`url`] — §7 ExternalResource URL Canonicalization
//! - [`hashdomain`] — §8 Hash Domain (edge_id, set_hash, witness_hash, UNKNOWN check)
//! - [`proof`] — §9 ProofV1 Schema (verifier + schema_descriptor/proof_schema_hash)
//! - [`registry`] — §10 EdgeExtractor.v1 Registry and registry_hash
//! - [`manifest`] — §12 Manifest Format (construction/verification helper)

pub mod canon_json;
pub mod glob;
pub mod hashdomain;
pub mod manifest;
pub mod path;
pub mod proof;
pub mod registry;
pub mod url;
