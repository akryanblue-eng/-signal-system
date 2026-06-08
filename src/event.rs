use std::collections::BTreeMap;

/// Closed signal event algebra — 6 primitive types.
/// Discriminants are fixed and must match codec.rs exactly.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    Create    { entity_id: u64, kind: u16 },
    Update    { entity_id: u64, field: u8, value: u64 },
    Merge     { target_id: u64, source_id: u64 },
    Partition { entity_id: u64, new_entity_id: u64, partition_key: u64 },
    Commit    { entity_id: u64 },
    Reject    { entity_id: u64, reason_code: u16 },
}

impl Event {
    pub fn discriminant(&self) -> u8 {
        match self {
            Event::Create { .. }    => 0x01,
            Event::Update { .. }    => 0x02,
            Event::Merge { .. }     => 0x03,
            Event::Partition { .. } => 0x04,
            Event::Commit { .. }    => 0x05,
            Event::Reject { .. }    => 0x06,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum EntityStatus {
    Active      = 0x00,
    MergedInto  = 0x01, // linked_id = absorbing entity
    Partitioned = 0x02, // linked_id = spawned partition entity
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EntityRecord {
    pub kind: u16,
    pub status: EntityStatus,
    pub linked_id: u64, // context-dependent; 0 if not applicable
    pub committed: bool,
    pub fields: BTreeMap<u8, u64>,
}

impl EntityRecord {
    pub fn new(kind: u16) -> Self {
        Self {
            kind,
            status: EntityStatus::Active,
            linked_id: 0,
            committed: false,
            fields: BTreeMap::new(),
        }
    }
}

/// The compiled state produced by StateCompiler.
/// Carries its own hash chain for external convergence verification.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CompiledState {
    pub entities: BTreeMap<u64, EntityRecord>,
    /// blake3 of canonical entity encoding — advances on semantic state change
    pub state_hash: [u8; 32],
    /// running blake3 chain of all applied canonical event bytes — advances on every event
    pub event_chain_hash: [u8; 32],
    /// blake3(state_hash || event_chain_hash) — canonical state proof
    pub csp: [u8; 32],
}
