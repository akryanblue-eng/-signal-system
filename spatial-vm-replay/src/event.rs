use serde::Deserialize;

/// Spatial VM events — matches EVENT_SCHEMAS.v1 event_type strings exactly.
/// Field names match the schema's camelCase JSON field names (nodeId, artifactId, etc.).
#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "event_type")]
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

impl SpatialEvent {
    pub fn event_type_str(&self) -> &'static str {
        match self {
            SpatialEvent::EnterNode { .. } => "enter_node",
            SpatialEvent::DiscoverArtifact { .. } => "discover_artifact",
            SpatialEvent::RevealLore { .. } => "reveal_lore",
            SpatialEvent::ChooseAscension => "choose_ascension",
            SpatialEvent::ChooseCreation => "choose_creation",
            SpatialEvent::NodeCompleted { .. } => "node_completed",
            SpatialEvent::PortalUnlocked { .. } => "portal_unlocked",
        }
    }
}
