//! Property 3 — Bijectivity
//!
//! Proves: the mapping eventType_string → QSEvent variant is bijective.
//!
//! Checks:
//!   (a) authority set == generated set (no drift, no extras)
//!   (b) generated set has no duplicates
//!   (c) event_type() arms are unique (one arm per variant, no two arms return same string)
//!   (d) the generated EVENT_TYPES array is lexicographically sorted (binary search precondition)

#[path = "common/mod.rs"]
mod common;

use schema_compiler::{json_loader, normalize, rust_gen};
use std::collections::BTreeSet;

fn generated_event_types(json: &str) -> Vec<String> {
    let schemas = json_loader::load_schemas_from_str(json).unwrap();
    let normalized = normalize::normalize(schemas);
    let rust_src = rust_gen::emit_rust(&normalized);

    // Extract EVENT_TYPES string literals from the generated source.
    let start = rust_src
        .find("pub const EVENT_TYPES: &[&str] = &[")
        .expect("EVENT_TYPES block not found");
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

fn authority_event_types(json: &str) -> BTreeSet<String> {
    let schemas: Vec<schema_compiler::schema::Schema> =
        serde_json::from_str(json).unwrap();
    schemas.into_iter().map(|s| s.eventType).collect()
}

#[test]
fn generated_set_equals_authority_set() {
    let json = std::fs::read_to_string(common::authority_json_path()).unwrap();
    let authority: BTreeSet<String> = authority_event_types(&json);
    let generated: BTreeSet<String> = generated_event_types(&json).into_iter().collect();

    assert_eq!(
        generated, authority,
        "Generated EVENT_TYPES set must equal authority set exactly"
    );
}

#[test]
fn generated_set_has_no_duplicates() {
    let json = std::fs::read_to_string(common::authority_json_path()).unwrap();
    let list = generated_event_types(&json);
    let set: BTreeSet<&String> = list.iter().collect();

    assert_eq!(
        list.len(),
        set.len(),
        "Generated EVENT_TYPES must have no duplicates (found {} entries, {} unique)",
        list.len(),
        set.len()
    );
}

#[test]
fn generated_event_types_are_sorted() {
    // Precondition for is_known_event_type binary_search to be correct.
    let json = std::fs::read_to_string(common::authority_json_path()).unwrap();
    let list = generated_event_types(&json);

    let mut sorted = list.clone();
    sorted.sort();

    assert_eq!(
        list, sorted,
        "EVENT_TYPES must be lexicographically sorted for binary_search to work"
    );
}

#[test]
fn event_type_arms_are_unique_in_generated_source() {
    // Parse the match arms from `event_type()` in the generated Rust source
    // and assert each return value appears exactly once.
    let json = std::fs::read_to_string(common::authority_json_path()).unwrap();
    let schemas = json_loader::load_schemas_from_str(&json).unwrap();
    let normalized = normalize::normalize(schemas);
    let rust_src = rust_gen::emit_rust(&normalized);

    // Extract return values from lines like: `=> "some_event_type",`
    let return_values: Vec<&str> = rust_src
        .lines()
        .filter_map(|line| {
            let t = line.trim();
            if t.starts_with("QSEvent::") && t.contains("=> \"") {
                let start = t.find("=> \"")? + 4;
                let end = t[start..].find('"')? + start;
                Some(&t[start..end])
            } else {
                None
            }
        })
        .collect();

    assert!(!return_values.is_empty(), "No event_type() arms found in generated source");

    let unique: BTreeSet<&&str> = return_values.iter().collect();
    assert_eq!(
        return_values.len(),
        unique.len(),
        "event_type() arms must all return distinct strings (bijectivity violated)"
    );
}
