use crate::schema::{Field, Schema};
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

pub fn validate(schemas: &[Schema]) -> Result<(), ValidationError> {
    for schema in schemas {
        validate_event_type(&schema.eventType)?;
        validate_fields(&schema.fields, &schema.eventType)?;
    }
    Ok(())
}

fn validate_event_type(event_type: &str) -> Result<(), ValidationError> {
    if event_type.is_empty() {
        return Err(ValidationError("eventType cannot be empty".into()));
    }
    if !event_type.chars().all(|c| c.is_ascii_lowercase() || c == '_') {
        return Err(ValidationError(format!(
            "eventType must be snake_case: {event_type}"
        )));
    }
    if event_type.starts_with('_') || event_type.ends_with('_') {
        return Err(ValidationError(format!(
            "eventType cannot start/end with _: {event_type}"
        )));
    }
    Ok(())
}

fn validate_fields(fields: &[Field], event_type: &str) -> Result<(), ValidationError> {
    let mut seen: HashSet<&str> = HashSet::new();
    for field in fields {
        if !seen.insert(field.name.as_str()) {
            return Err(ValidationError(format!(
                "Duplicate field name '{}' in {event_type}",
                field.name
            )));
        }
        if field.name == "eventType" {
            return Err(ValidationError(format!(
                "Field name 'eventType' is reserved in {event_type}"
            )));
        }
        match field.r#type.as_str() {
            "string" | "int" | "bool" => {}
            other => {
                return Err(ValidationError(format!(
                    "Unknown type '{other}' for field '{}' in {event_type}",
                    field.name
                )));
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::schema::{Field, Schema};

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
    }

    #[test]
    fn test_duplicate_field_names() {
        let schema = Schema::new(
            "event".into(),
            vec![
                Field::new("nodeId".into(), "string".into()),
                Field::new("nodeId".into(), "string".into()),
            ],
        );
        assert!(validate_fields(&schema.fields, "event").is_err());
    }

    #[test]
    fn test_unknown_type() {
        let schema = Schema::new(
            "event".into(),
            vec![Field::new("x".into(), "float".into())],
        );
        assert!(validate_fields(&schema.fields, "event").is_err());
    }
}
