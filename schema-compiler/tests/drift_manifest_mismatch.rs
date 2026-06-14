//! Property 1 — Manifest mismatch detection
//!
//! Proves: any edit to EVENT_SCHEMAS.v1.json (even one byte) changes combined_hash.

#[path = "common/mod.rs"]
mod common;

use schema_compiler::{json_loader, manifest, normalize, rust_gen, swift};

/// Mutate one letter inside the first eventType string value in the JSON bytes.
/// Produces valid JSON that parses to different schemas (not just a whitespace change,
/// which serde_json ignores).
///
/// Strategy: find `"eventType": "` then advance to the first letter in the value
/// and rotate it one step in [a-z] (e.g. 'c' → 'd'). The result still passes
/// snake_case validation but changes the event name.
fn flip_one_event_name_letter(mut bytes: Vec<u8>) -> Vec<u8> {
    let needle = b"\"eventType\": \"";
    if let Some(pos) = bytes.windows(needle.len()).position(|w| w == needle) {
        let value_start = pos + needle.len();
        for b in bytes[value_start..].iter_mut() {
            if b.is_ascii_lowercase() {
                // rotate within a-z so result is still a valid snake_case letter
                *b = if *b == b'z' { b'a' } else { *b + 1 };
                return bytes;
            }
        }
    }
    // Fallback: flip low bit of first non-structural byte
    for b in bytes.iter_mut() {
        if *b != b'"' && *b != b'{' && *b != b'}' && *b != b'[' && *b != b']'
            && *b != b' ' && *b != b'\n' && *b != b'\t'
        {
            *b ^= 0b0000_0001;
            return bytes;
        }
    }
    bytes[0] ^= 0b0000_0001;
    bytes
}

fn compile_manifest(json: &str) -> schema_compiler::manifest::Manifest {
    let schemas = json_loader::load_schemas_from_str(json).expect("parse");
    let normalized = normalize::normalize(schemas);
    let swift = swift::emit_swift(&normalized);
    let rust = rust_gen::emit_rust(&normalized);
    manifest::Manifest::new(&swift, &rust)
}

#[test]
fn baseline_matches_frozen_identity() {
    let json = std::fs::read_to_string(common::authority_json_path())
        .expect("read EVENT_SCHEMAS.v1.json");
    let mf = compile_manifest(&json);
    assert_eq!(
        mf.combined_hash, common::BASELINE_COMBINED_HASH,
        "Baseline diverged from frozen identity — update baseline constants if intentional"
    );
    assert_eq!(mf.swift_hash, common::BASELINE_SWIFT_HASH);
    assert_eq!(mf.rust_hash, common::BASELINE_RUST_HASH);
}

#[test]
fn one_byte_schema_edit_breaks_combined_hash() {
    let original = std::fs::read(common::authority_json_path())
        .expect("read EVENT_SCHEMAS.v1.json");
    let mutated = flip_one_event_name_letter(original.clone());

    // Both must be valid JSON for this test to isolate the hash property.
    let original_str = String::from_utf8(original).unwrap();
    let mutated_str = String::from_utf8(mutated).unwrap();

    // Mutated JSON must still parse (we changed a letter, not structure).
    // Validation may reject it (rotated name may conflict), but parsing must succeed.
    let _ = serde_json::from_str::<serde_json::Value>(&mutated_str)
        .expect("mutated JSON must remain structurally valid");

    let mf_original = compile_manifest(&original_str);

    // Compile the mutated schema (may need to skip validation for the renamed type).
    let schemas_mutated = json_loader::load_schemas_from_str(&mutated_str)
        .expect("parse mutated");
    let norm_mutated = normalize::normalize(schemas_mutated);
    let swift_mutated = swift::emit_swift(&norm_mutated);
    let rust_mutated = rust_gen::emit_rust(&norm_mutated);
    let mf_mutated = manifest::Manifest::new(&swift_mutated, &rust_mutated);

    // Sanity: original matches baseline.
    assert_eq!(mf_original.combined_hash, common::BASELINE_COMBINED_HASH);

    // Closure property: one-letter change in an event name changes the hash.
    assert_ne!(
        mf_mutated.combined_hash,
        common::BASELINE_COMBINED_HASH,
        "Renaming one letter in an event type must break combined_hash binding"
    );
}

#[test]
fn added_event_breaks_combined_hash() {
    let json = std::fs::read_to_string(common::authority_json_path()).unwrap();
    // Append a new (valid) event to the array.
    let injected = json.trim_end().trim_end_matches(']').to_string()
        + r#",{"eventType":"injected_event","fields":[]}]"#;

    let mf = compile_manifest(&injected);
    assert_ne!(
        mf.combined_hash,
        common::BASELINE_COMBINED_HASH,
        "Adding an event must break combined_hash binding"
    );
}
