use serde::Serialize;

/// Encode `value` as compact (non-pretty) JSON bytes.
///
/// Rules that guarantee determinism across invocations:
///   - Compact output (`to_vec`, never `to_string_pretty`).
///   - No `HashMap` in any certificate struct; all fields are defined on fixed
///     Rust structs so serde serializes them in definition order.
///   - Float values are not present in the certificate struct, avoiding any
///     platform-dependent float-to-string edge cases.
pub fn canonical_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>, serde_json::Error> {
    serde_json::to_vec(value)
}
