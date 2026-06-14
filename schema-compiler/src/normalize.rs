use crate::schema::Schema;

pub fn normalize(mut schemas: Vec<Schema>) -> Vec<Schema> {
    schemas.sort_by(|a, b| a.eventType.cmp(&b.eventType));

    for schema in schemas.iter_mut() {
        schema.fields.sort_by(|a, b| a.name.cmp(&b.name));
        for (i, field) in schema.fields.iter_mut().enumerate() {
            field.index = Some(i as u32);
        }
    }

    schemas
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::schema::{Field, Schema};

    #[test]
    fn test_normalization_sorts_schemas_and_fields() {
        let schemas = vec![
            Schema::new(
                "z_event".into(),
                vec![
                    Field::new("z_field".into(), "string".into()),
                    Field::new("a_field".into(), "string".into()),
                ],
            ),
            Schema::new("a_event".into(), vec![Field::new("b".into(), "string".into())]),
        ];

        let normalized = normalize(schemas);

        assert_eq!(normalized[0].eventType, "a_event");
        assert_eq!(normalized[1].eventType, "z_event");
        assert_eq!(normalized[1].fields[0].name, "a_field");
        assert_eq!(normalized[1].fields[1].name, "z_field");
        assert_eq!(normalized[1].fields[0].index, Some(0));
        assert_eq!(normalized[1].fields[1].index, Some(1));
    }
}
