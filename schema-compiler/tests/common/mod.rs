// Frozen manifest identity — change here only when EVENT_SCHEMAS.v1.json or generator changes intentionally.
// Updated: added UNIT_EVENT_TYPES + is_unit_event_type to rust_gen output.
pub const BASELINE_COMBINED_HASH: &str =
    "c1451a41443ae601d510ce1e667e633a836995fb760d959326eccce28ba7dc64";
pub const BASELINE_SWIFT_HASH: &str =
    "622258e225c43a88f48185a15972937e70e6249c25c135f691b37d077f60a8cc";
pub const BASELINE_RUST_HASH: &str =
    "aa696dd3f257c8215c1c7bf8e8f1e9cc4d8537fb7709ab93b6590f4447a24910";
pub const BASELINE_JSON_HASH: &str =
    "b371fe11eef627d3e3accd8c8fe4c664b30cc6fbd816c37d9b264cdb3a2d46ac";

pub fn authority_json_path() -> std::path::PathBuf {
    // Integration tests run with cwd = schema-compiler/
    std::path::PathBuf::from("EVENT_SCHEMAS.v1.json")
}
