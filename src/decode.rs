use crate::types::{Trace, VdceError, SUPPORTED_REDUCER_VERSION, SUPPORTED_SCHEMA_VERSION};

/// Stage 1: bytes → structured Trace + schema/version validation.
pub fn decode_and_validate(bytes: &[u8]) -> Result<Trace, VdceError> {
    let trace: Trace = serde_json::from_slice(bytes)
        .map_err(|e| VdceError::SchemaOrDecode(format!("JSON parse error: {e}")))?;

    if trace.schema_version != SUPPORTED_SCHEMA_VERSION {
        return Err(VdceError::SchemaOrDecode(format!(
            "unsupported schema_version {}: expected {}",
            trace.schema_version, SUPPORTED_SCHEMA_VERSION
        )));
    }

    if trace.reducer_version != SUPPORTED_REDUCER_VERSION {
        return Err(VdceError::SchemaOrDecode(format!(
            "unsupported reducer_version {:?}: expected {:?}",
            trace.reducer_version, SUPPORTED_REDUCER_VERSION
        )));
    }

    Ok(trace)
}
