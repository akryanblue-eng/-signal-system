use serde::Deserialize;

/// Spatial VM events — matches EVENT_SCHEMAS.v1 event_type strings exactly.
/// Field names match the schema's camelCase JSON field names (nodeId, artifactId, etc.).
/// deny_unknown_fields: unknown payload fields are rejected at decode, not silently dropped.
#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "event_type", deny_unknown_fields)]
pub enum SpatialEvent {
    #[serde(rename = "enter_node")]
    EnterNode {
        #[serde(rename = "nodeId")]
        node_id: String,
    },
    #[serde(rename = "discover_artifact")]
    DiscoverArtifact {
        #[serde(rename = "artifactId")]
        artifact_id: String,
    },
    #[serde(rename = "reveal_lore")]
    RevealLore {
        #[serde(rename = "loreId")]
        lore_id: String,
    },
    #[serde(rename = "choose_ascension")]
    ChooseAscension,
    #[serde(rename = "choose_creation")]
    ChooseCreation,
    #[serde(rename = "node_completed")]
    NodeCompleted {
        #[serde(rename = "nodeId")]
        node_id: String,
    },
    #[serde(rename = "portal_unlocked")]
    PortalUnlocked {
        #[serde(rename = "portalId")]
        portal_id: String,
    },
}
