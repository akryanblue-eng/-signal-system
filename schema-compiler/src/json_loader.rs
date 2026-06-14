use crate::schema::Schema;

pub fn load_schemas_from_str(s: &str) -> Result<Vec<Schema>, serde_json::Error> {
    serde_json::from_str(s)
}
