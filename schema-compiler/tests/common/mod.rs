// Frozen manifest identity — change here only when EVENT_SCHEMAS.v1.json changes intentionally.
pub const BASELINE_COMBINED_HASH: &str =
    "772a0ccc18861627c4f4bc6611134ba017b27e7c21b50f4236a7eaf2a25314d7";
pub const BASELINE_SWIFT_HASH: &str =
    "622258e225c43a88f48185a15972937e70e6249c25c135f691b37d077f60a8cc";
pub const BASELINE_RUST_HASH: &str =
    "aaa01e860da945b03c08410ef4fa85d0dc0da8cb1e799c3457271c171e5678d1";
pub const BASELINE_JSON_HASH: &str =
    "b371fe11eef627d3e3accd8c8fe4c664b30cc6fbd816c37d9b264cdb3a2d46ac";

pub fn authority_json_path() -> std::path::PathBuf {
    // Integration tests run with cwd = schema-compiler/
    std::path::PathBuf::from("EVENT_SCHEMAS.v1.json")
}
