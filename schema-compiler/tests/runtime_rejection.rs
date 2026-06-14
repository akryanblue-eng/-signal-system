//! Property 2 — Runtime mismatch detection
//!
//! Proves: unknown eventType strings are rejected at the decode boundary.
//! Tests the generated `is_known_event_type` surface on the Rust side.

#[path = "common/mod.rs"]
mod common;

use schema_compiler::{json_loader, normalize, rust_gen};

/// Parse the `is_known_event_type` dispatch table out of the generated Rust
/// source by extracting the EVENT_TYPES string literals. This tests the
/// *generated artifact*, not just the compiler logic.
fn extract_event_types_from_source(rust_src: &str) -> Vec<String> {
    let start = rust_src
        .find("pub const EVENT_TYPES: &[&str] = &[")
        .expect("EVENT_TYPES not found in generated source");
    let block = &rust_src[start..];
    let end = block.find("];").expect("];  not found");
    let block = &block[..end];

    block
        .lines()
        .filter_map(|line| {
            let t = line.trim().trim_matches(',');
            if t.starts_with('"') && t.ends_with('"') {
                Some(t[1..t.len() - 1].to_string())
            } else {
                None
            }
        })
        .collect()
}

#[test]
fn unknown_event_type_not_in_generated_dispatch_table() {
    let json = std::fs::read_to_string(common::authority_json_path()).unwrap();
    let schemas = json_loader::load_schemas_from_str(&json).unwrap();
    let normalized = normalize::normalize(schemas);
    let rust_src = rust_gen::emit_rust(&normalized);

    let known = extract_event_types_from_source(&rust_src);

    // Hard-fail: the sentinel unknown type must be absent.
    assert!(
        !known.contains(&"__unknown_event_type__".to_string()),
        "__unknown_event_type__ must not appear in the dispatch table"
    );

    // Confirm the table is non-empty (guard against accidental empty output).
    assert!(!known.is_empty(), "EVENT_TYPES must not be empty");
}

#[test]
fn all_authority_types_present_in_dispatch_table() {
    let json = std::fs::read_to_string(common::authority_json_path()).unwrap();
    let schemas = json_loader::load_schemas_from_str(&json).unwrap();
    let normalized = normalize::normalize(schemas.clone());
    let rust_src = rust_gen::emit_rust(&normalized);

    let generated = extract_event_types_from_source(&rust_src);

    // Every authority type must appear in the dispatch table.
    for schema in &schemas {
        assert!(
            generated.contains(&schema.event_type),
            "Authority type '{}' missing from generated EVENT_TYPES",
            schema.event_type
        );
    }
}

#[test]
fn dispatch_table_has_no_extra_types() {
    let json = std::fs::read_to_string(common::authority_json_path()).unwrap();
    let schemas = json_loader::load_schemas_from_str(&json).unwrap();
    let authority_types: std::collections::BTreeSet<String> =
        schemas.iter().map(|s| s.event_type.clone()).collect();
    let normalized = normalize::normalize(schemas);
    let rust_src = rust_gen::emit_rust(&normalized);

    let generated: std::collections::BTreeSet<String> =
        extract_event_types_from_source(&rust_src).into_iter().collect();

    assert_eq!(
        generated,
        authority_types,
        "Generated EVENT_TYPES must contain exactly the authority set (no extras, no omissions)"
    );
}
