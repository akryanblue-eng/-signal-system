use crate::event::SpatialEvent;
use crate::state::TravelerState;
use serde::Deserialize;
use std::fs;
use std::path::Path;

#[derive(Debug, Deserialize)]
pub struct SpatialVector {
    pub id: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub initial_state: TravelerState,
    pub events: Vec<SpatialEvent>,
}

/// Load all *.json files from dir that have an "id" field (skips manifest.json, etc.).
/// Returns vectors sorted lexicographically by id.
pub fn load_vectors_from_dir(dir: &str) -> Vec<SpatialVector> {
    let dir_path = Path::new(dir);
    let mut entries: Vec<_> = fs::read_dir(dir_path)
        .unwrap_or_else(|e| panic!("cannot read vectors dir {dir}: {e}"))
        .filter_map(|e| e.ok())
        .filter(|e| {
            e.path().extension().and_then(|x| x.to_str()) == Some("json")
        })
        .collect();

    entries.sort_by_key(|e| e.path());

    let mut vectors: Vec<SpatialVector> = entries
        .iter()
        .filter_map(|e| {
            let text = fs::read_to_string(e.path())
                .unwrap_or_else(|err| panic!("cannot read {:?}: {err}", e.path()));
            let v: serde_json::Value = serde_json::from_str(&text)
                .unwrap_or_else(|err| panic!("invalid JSON in {:?}: {err}", e.path()));
            if v.get("id").is_none() {
                return None;
            }
            Some(serde_json::from_value::<SpatialVector>(v)
                .unwrap_or_else(|err| panic!("bad vector in {:?}: {err}", e.path())))
        })
        .collect();

    vectors.sort_by(|a, b| a.id.cmp(&b.id));
    vectors
}
