// Frozen manifest identity — change here only when EVENT_SCHEMAS.v1.json changes intentionally.
pub const BASELINE_COMBINED_HASH: &str =
    "c1fc1cf91d33d026eba2d5e6c271e3d1d75c706f0bc24e038e66462800b10930";
pub const BASELINE_SWIFT_HASH: &str =
    "f5e98d3a64deded40f17ee72c9d177e58e135a25eb87e58604ac07863b9fb796";
pub const BASELINE_RUST_HASH: &str =
    "aaa01e860da945b03c08410ef4fa85d0dc0da8cb1e799c3457271c171e5678d1";

pub fn authority_json_path() -> std::path::PathBuf {
    // Integration tests run with cwd = schema-compiler/
    std::path::PathBuf::from("EVENT_SCHEMAS.v1.json")
}
