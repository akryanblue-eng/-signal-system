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
/// - `machine::apply` has no wildcard arm; the compiler enforces full variant coverage.
/// - There is no other routing path in this crate.
pub fn decode_and_apply(
    json: &[u8],
    state: TravelerState,
) -> Result<TravelerState, DispatchError> {
    let event: SpatialEvent =
        serde_json::from_slice(json).map_err(|e| DispatchError::InvalidEvent(e.to_string()))?;
    Ok(machine::apply(state, &event))
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
}
