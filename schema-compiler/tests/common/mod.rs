// Frozen manifest identity — change here only when EVENT_SCHEMAS.v1.json changes intentionally.
pub const BASELINE_COMBINED_HASH: &str =
    "bcb62388d527c52f2bd9bcea352ccafc3a7e72813865bcb50f8cc61073c43dd4";
pub const BASELINE_SWIFT_HASH: &str =
    "f661a03a563ab8dbd013ec5cc3576a3e216112af8edb6c67e95aeb06e4f39f35";
pub const BASELINE_RUST_HASH: &str =
    "aaa01e860da945b03c08410ef4fa85d0dc0da8cb1e799c3457271c171e5678d1";

pub fn authority_json_path() -> std::path::PathBuf {
    // Integration tests run with cwd = schema-compiler/
    std::path::PathBuf::from("EVENT_SCHEMAS.v1.json")
}
