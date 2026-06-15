use crate::event::SpatialEvent;
use crate::machine;
use crate::state::TravelerState;
use std::fmt;

/// Dispatch errors. Unknown event_type strings are caught at the decode boundary
/// before any state mutation occurs.
#[derive(Debug)]
pub enum DispatchError {
    /// serde rejected the JSON: unknown event_type or missing required field.
    InvalidEvent(String),
}

impl fmt::Display for DispatchError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DispatchError::InvalidEvent(msg) => write!(f, "invalid event: {msg}"),
        }
    }
}

impl std::error::Error for DispatchError {}

/// Single ingress: JSON bytes → typed SpatialEvent → exhaustive match → new state.
///
/// Routing invariants:
/// - Unknown event_type values fail at serde decode (before this function returns `Ok`).
/// - Unknown payload fields on struct variants are rejected by deny_unknown_fields.
/// - Unknown payload fields on unit variants (no payload) are rejected by pre-validation.
/// - `machine::apply` has no wildcard arm; the compiler enforces full variant coverage.
/// - There is no other routing path in this crate.
pub fn decode_and_apply(
    json: &[u8],
    state: TravelerState,
) -> Result<TravelerState, DispatchError> {
    // Pre-validate unit variants: serde's deny_unknown_fields does not enforce field
    // rejection on unit variants in internally-tagged enums, so we do it explicitly.
    reject_stray_fields_on_unit_variants(json)?;
    let event: SpatialEvent =
        serde_json::from_slice(json).map_err(|e| DispatchError::InvalidEvent(e.to_string()))?;
    Ok(machine::apply(state, &event))
}

/// Unit variants have no payload. Any field beyond event_type is a stray field.
/// UNIT_EVENT_TYPES is generated from EVENT_SCHEMAS.v1 by schema-compiler — no manual list here.
fn reject_stray_fields_on_unit_variants(json: &[u8]) -> Result<(), DispatchError> {
    let v: serde_json::Value = serde_json::from_slice(json)
        .map_err(|e| DispatchError::InvalidEvent(e.to_string()))?;
    let obj = v.as_object().ok_or_else(|| {
        DispatchError::InvalidEvent("event must be a JSON object".into())
    })?;
    if let Some(et) = obj.get("event_type").and_then(|v| v.as_str()) {
        if crate::schema_derived::is_unit_event_type(et) && obj.len() > 1 {
            let stray: Vec<&str> = obj.keys()
                .filter(|k| *k != "event_type")
                .map(|k| k.as_str())
                .collect();
            return Err(DispatchError::InvalidEvent(format!(
                "unit event '{et}' must have no payload fields; found: {stray:?}"
            )));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_event_mutates_state() {
        let state = TravelerState::default();
        let json = br#"{"event_type":"enter_node","nodeId":"n1"}"#;
        let next = decode_and_apply(json, state).unwrap();
        assert!(next.visited_nodes.contains("n1"));
    }

    #[test]
    fn unknown_event_type_rejected_before_dispatch() {
        let state = TravelerState::default();
        let json = br#"{"event_type":"__unknown__","nodeId":"x"}"#;
        let err = decode_and_apply(json, state).unwrap_err();
        let msg = err.to_string();
        assert!(
            msg.contains("unknown variant") || msg.contains("__unknown__") || msg.contains("invalid event"),
            "expected rejection message, got: {msg}"
        );
    }

    #[test]
    fn missing_required_field_rejected_at_decode() {
        let state = TravelerState::default();
        // enter_node requires nodeId
        let json = br#"{"event_type":"enter_node"}"#;
        assert!(decode_and_apply(json, state).is_err());
    }

    #[test]
    fn all_schema_event_types_accepted() {
        let cases: &[&[u8]] = &[
            br#"{"event_type":"enter_node","nodeId":"n"}"#,
            br#"{"event_type":"discover_artifact","artifactId":"a"}"#,
            br#"{"event_type":"reveal_lore","loreId":"l"}"#,
            br#"{"event_type":"choose_ascension"}"#,
            br#"{"event_type":"choose_creation"}"#,
            br#"{"event_type":"node_completed","nodeId":"n"}"#,
            br#"{"event_type":"portal_unlocked","portalId":"p"}"#,
        ];
        for json in cases {
            assert!(
                decode_and_apply(json, TravelerState::default()).is_ok(),
                "failed for: {}",
                std::str::from_utf8(json).unwrap()
            );
        }
    }

    #[test]
    fn unknown_payload_field_rejected_at_decode() {
        // deny_unknown_fields: extra fields in payload must not silently pass through.
        let state = TravelerState::default();
        let json = br#"{"event_type":"enter_node","nodeId":"n1","injection":"ignored"}"#;
        assert!(
            decode_and_apply(json, state).is_err(),
            "extra payload field must be rejected, not silently dropped"
        );
    }

    #[test]
    fn unknown_payload_field_on_unit_variant_rejected() {
        // choose_ascension has no payload fields — any extra field must fail.
        let state = TravelerState::default();
        let json = br#"{"event_type":"choose_ascension","nodeId":"stray"}"#;
        assert!(
            decode_and_apply(json, state).is_err(),
            "stray field on unit variant must be rejected"
        );
    }
}
