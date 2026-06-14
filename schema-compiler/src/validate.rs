use crate::schema::EventSchema;
use std::collections::HashSet;
use std::error::Error;
use std::fmt;

#[derive(Debug)]
pub struct ValidationError(pub String);

impl fmt::Display for ValidationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl Error for ValidationError {}

pub fn validate(schemas: &[EventSchema]) -> Result<(), ValidationError> {
    let mut seen_types: HashSet<&str> = HashSet::new();
    for schema in schemas {
        validate_event_type(&schema.event_type)?;
        if !seen_types.insert(schema.event_type.as_str()) {
            return Err(ValidationError(format!(
                "Duplicate event_type: {}",
                schema.event_type
            )));
        }
        validate_fields(schema)?;
    }
    Ok(())
}

fn validate_event_type(event_type: &str) -> Result<(), ValidationError> {
    if event_type.is_empty() {
        return Err(ValidationError("event_type cannot be empty".into()));
    }
    if !event_type.chars().all(|c| c.is_ascii_lowercase() || c == '_') {
        return Err(ValidationError(format!(
            "event_type must be snake_case: {event_type}"
        )));
    }
    if event_type.starts_with('_') || event_type.ends_with('_') {
        return Err(ValidationError(format!(
            "event_type cannot start/end with _: {event_type}"
        )));
    }
    Ok(())
}

fn validate_fields(schema: &EventSchema) -> Result<(), ValidationError> {
    let mut seen: HashSet<&str> = HashSet::new();
    for field in &schema.fields {
        if field.name.is_empty() {
            return Err(ValidationError(format!(
                "Empty field name in {}",
                schema.event_type
            )));
        }
        if field.name == "eventType" || field.name == "event_type" {
            return Err(ValidationError(format!(
                "Field name '{}' is reserved in {}",
                field.name, schema.event_type
            )));
        }
        if !seen.insert(field.name.as_str()) {
            return Err(ValidationError(format!(
                "Duplicate field name '{}' in {}",
                field.name, schema.event_type
            )));
        }
    }
    Ok(())
    // Note: ScalarType is a closed enum — unknown types are impossible;
    // serde rejects them at parse time before validate() is ever called.
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::schema::{EventSchema, Field, ScalarType};

    fn schema(event_type: &str, fields: Vec<Field>) -> EventSchema {
        EventSchema { event_type: event_type.into(), description: None, fields }
    }

    fn string_field(name: &str) -> Field {
        Field { name: name.into(), ty: ScalarType::String, required: true }
    }

    #[test]
    fn test_valid_event_type() {
        assert!(validate_event_type("enter_node").is_ok());
        assert!(validate_event_type("choose_ascension").is_ok());
    }

    #[test]
    fn test_invalid_event_type() {
        assert!(validate_event_type("EnterNode").is_err());
        assert!(validate_event_type("enter-node").is_err());
        assert!(validate_event_type("_event").is_err());
        assert!(validate_event_type("event_").is_err());
        assert!(validate_event_type("").is_err());
    }

    #[test]
    fn test_duplicate_event_types() {
        let schemas = vec![
            schema("enter_node", vec![]),
            schema("enter_node", vec![]),
        ];
        assert!(validate(&schemas).is_err());
    }

    #[test]
    fn test_duplicate_field_names() {
        let s = schema("event", vec![string_field("nodeId"), string_field("nodeId")]);
        assert!(validate_fields(&s).is_err());
    }

    #[test]
    fn test_reserved_field_name() {
        let s = schema("event", vec![string_field("eventType")]);
        assert!(validate_fields(&s).is_err());
    }
}
