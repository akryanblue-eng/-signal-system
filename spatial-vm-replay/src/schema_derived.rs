// DSVM-0 GENERATED FILE — DO NOT EDIT
// source: EVENT_SCHEMAS.v1
// generator: dsvm-schema-compiler@v1.0

#[derive(Debug, Clone, PartialEq)]
pub enum QSEvent {
    ChooseAscension,
    ChooseCreation,
    DiscoverArtifact { artifactId: String },
    EnterNode { nodeId: String },
    NodeCompleted { nodeId: String },
    PortalUnlocked { portalId: String },
    RevealLore { loreId: String },
}

impl QSEvent {
    pub fn event_type(&self) -> &str {
        match self {
            QSEvent::ChooseAscension => "choose_ascension",
            QSEvent::ChooseCreation => "choose_creation",
            QSEvent::DiscoverArtifact { .. } => "discover_artifact",
            QSEvent::EnterNode { .. } => "enter_node",
            QSEvent::NodeCompleted { .. } => "node_completed",
            QSEvent::PortalUnlocked { .. } => "portal_unlocked",
            QSEvent::RevealLore { .. } => "reveal_lore",
        }
    }
}

pub const EVENT_TYPES: &[&str] = &[
    "choose_ascension",
    "choose_creation",
    "discover_artifact",
    "enter_node",
    "node_completed",
    "portal_unlocked",
    "reveal_lore",
];

pub fn is_known_event_type(s: &str) -> bool {
    EVENT_TYPES.binary_search(&s).is_ok()
}

pub const UNIT_EVENT_TYPES: &[&str] = &[
    "choose_ascension",
    "choose_creation",
];

pub fn is_unit_event_type(s: &str) -> bool {
    UNIT_EVENT_TYPES.binary_search(&s).is_ok()
}
