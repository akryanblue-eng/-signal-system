use serde::{Deserialize, Serialize};

/// Single source of truth IR for EVENT_SCHEMAS.v1.
///
/// Determinism contract:
/// - Schemas are normalized by sorting by event_type.
/// - Fields are normalized by sorting by name.
/// - No HashMap in the IR.
/// - Types are enumerated (no dynamic type strings — ScalarType is the vocabulary lock).
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct EventSchema {
    /// Canonical authority key (snake_case), e.g. "enter_node"
    pub event_type: String,

    /// Non-authoritative human metadata — never feeds into hash or generated output.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,

    /// Field registry (normalized deterministically by name).
    pub fields: Vec<Field>,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Field {
    /// Canonical field name (camelCase per DSVM-0 event bus convention).
    pub name: String,

    /// Canonical type — enum locks the vocabulary; no per-language string drift.
    #[serde(rename = "type")]
    pub ty: ScalarType,

    /// Requiredness is explicit: no Option<T> leakage in v1 schema layer.
    pub required: bool,
}

/// Canonical scalar vocabulary for v1.
/// Extend only via a versioned schema change.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ScalarType {
    String,
    U64,
    I64,
    Bool,
    Bytes32,
}

impl ScalarType {
    pub fn rust_type(self) -> &'static str {
        match self {
            ScalarType::String => "String",
            ScalarType::U64 => "u64",
            ScalarType::I64 => "i64",
            ScalarType::Bool => "bool",
            ScalarType::Bytes32 => "[u8; 32]",
        }
    }

    pub fn swift_type(self) -> &'static str {
        match self {
            ScalarType::String => "String",
            ScalarType::U64 => "UInt64",
            ScalarType::I64 => "Int64",
            ScalarType::Bool => "Bool",
            ScalarType::Bytes32 => "Data",
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            ScalarType::String => "string",
            ScalarType::U64 => "u64",
            ScalarType::I64 => "i64",
            ScalarType::Bool => "bool",
            ScalarType::Bytes32 => "bytes32",
        }
    }
}

impl EventSchema {
    pub fn canonical_key(&self) -> &str {
        &self.event_type
    }

    /// Deterministic field normalization (sort by name). Pure.
    pub fn normalized(mut self) -> Self {
        self.fields.sort_by(|a, b| a.name.cmp(&b.name));
        self
    }
}

/// Load and normalize the authority registry from a JSON string.
pub fn load_schemas_from_str(json: &str) -> Result<Vec<EventSchema>, serde_json::Error> {
    let mut schemas: Vec<EventSchema> = serde_json::from_str(json)?;
    schemas.sort_by(|a, b| a.event_type.cmp(&b.event_type));
    schemas = schemas.into_iter().map(|s| s.normalized()).collect();
    Ok(schemas)
}

/// Load and normalize the authority registry from a file path.
pub fn load_schemas_from_path(path: &str) -> Result<Vec<EventSchema>, String> {
    let raw = std::fs::read_to_string(path).map_err(|e| format!("read schema: {e}"))?;
    load_schemas_from_str(&raw).map_err(|e| format!("parse schema json: {e}"))
}
