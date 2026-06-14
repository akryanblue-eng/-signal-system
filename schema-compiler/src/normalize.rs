use crate::schema::EventSchema;

/// Idempotent normalization pass.
/// `load_schemas_from_str` already normalizes, so this is a no-op on already-loaded
/// schemas — but keeping it explicit in the pipeline makes the contract visible.
pub fn normalize(mut schemas: Vec<EventSchema>) -> Vec<EventSchema> {
    schemas.sort_by(|a, b| a.event_type.cmp(&b.event_type));
    schemas.into_iter().map(|s| s.normalized()).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::schema::{EventSchema, Field, ScalarType};

    fn string_field(name: &str) -> Field {
        Field { name: name.into(), ty: ScalarType::String, required: true }
    }

    #[test]
    fn test_normalization_sorts_schemas_and_fields() {
        let schemas = vec![
            EventSchema {
                event_type: "z_event".into(),
                description: None,
                fields: vec![string_field("z_field"), string_field("a_field")],
            },
            EventSchema {
                event_type: "a_event".into(),
                description: None,
                fields: vec![string_field("b")],
            },
        ];

        let normalized = normalize(schemas);

        assert_eq!(normalized[0].event_type, "a_event");
        assert_eq!(normalized[1].event_type, "z_event");
        assert_eq!(normalized[1].fields[0].name, "a_field");
        assert_eq!(normalized[1].fields[1].name, "z_field");
    }

    #[test]
    fn test_normalization_is_idempotent() {
        let schemas = vec![EventSchema {
            event_type: "enter_node".into(),
            description: None,
            fields: vec![string_field("nodeId")],
        }];
        let once = normalize(schemas.clone());
        let twice = normalize(once.clone());
        assert_eq!(once, twice);
    }
}
