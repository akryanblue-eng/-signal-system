use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Schema {
    pub eventType: String,
    pub fields: Vec<Field>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Field {
    pub name: String,
    #[serde(rename = "type")]
    pub r#type: String,
    #[serde(default)]
    pub index: Option<u32>,
}

impl Schema {
    pub fn new(event_type: String, fields: Vec<Field>) -> Self {
        Self { eventType: event_type, fields }
    }
}

impl Field {
    pub fn new(name: String, r#type: String) -> Self {
        Self { name, r#type, index: None }
    }
}
