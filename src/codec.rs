/// Canonical serialization layer — the representational closure boundary.
///
/// ## Event wire format (all integers little-endian)
///   [domain_tag: 2B = 0x53 0x49]["SI"]
///   [version:    1B = 0x01]
///   [discriminant: 1B]
///   [payload: discriminant-specific, fixed-length]
///
///   Create    (0x01): entity_id:8 + kind:2            = 14 bytes total
///   Update    (0x02): entity_id:8 + field:1 + value:8 = 21 bytes total
///   Merge     (0x03): target_id:8 + source_id:8       = 20 bytes total
///   Partition (0x04): entity_id:8 + new_id:8 + pkey:8 = 28 bytes total
///   Commit    (0x05): entity_id:8                     = 12 bytes total
///   Reject    (0x06): entity_id:8 + reason_code:2     = 14 bytes total
///
/// ## Entity map wire format (input to state_hash)
///   [entity_count: u32 LE]
///   for each entity in ascending entity_id order:
///     [entity_id: u64 LE][kind: u16 LE][status: u8][linked_id: u64 LE]
///     [committed: u8][field_count: u16 LE]
///     for each field in ascending key order: [key: u8][value: u64 LE]
///
/// ## Compiled state wire format (convergence check input)
///   [entity_map_bytes][state_hash: 32][event_chain_hash: 32][csp: 32]
///
/// Decode is fail-closed: any deviation from spec is Err, never partial.
use crate::event::{CompiledState, EntityRecord, Event};
use std::collections::BTreeMap;
use thiserror::Error;

const DOMAIN_TAG: [u8; 2] = [0x53, 0x49];
const VERSION: u8 = 0x01;
const HEADER_LEN: usize = 4;

const PAYLOAD_CREATE:    usize = 10;
const PAYLOAD_UPDATE:    usize = 17;
const PAYLOAD_MERGE:     usize = 16;
const PAYLOAD_PARTITION: usize = 24;
const PAYLOAD_COMMIT:    usize = 8;
const PAYLOAD_REJECT:    usize = 10;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum DecodeError {
    #[error("buffer too short: {0} bytes")]
    TooShort(usize),
    #[error("invalid domain tag: {0:#04x} {1:#04x}")]
    InvalidDomainTag(u8, u8),
    #[error("unsupported version: {0:#04x}")]
    UnsupportedVersion(u8),
    #[error("unknown discriminant: {0:#04x}")]
    UnknownDiscriminant(u8),
    #[error("wrong payload length for {discriminant:#04x}: expected {expected}, got {got}")]
    WrongLength { discriminant: u8, expected: usize, got: usize },
}

pub fn encode(event: &Event) -> Vec<u8> {
    let mut buf = Vec::with_capacity(HEADER_LEN + PAYLOAD_PARTITION);
    buf.extend_from_slice(&DOMAIN_TAG);
    buf.push(VERSION);
    buf.push(event.discriminant());
    match event {
        Event::Create { entity_id, kind } => {
            buf.extend_from_slice(&entity_id.to_le_bytes());
            buf.extend_from_slice(&kind.to_le_bytes());
        }
        Event::Update { entity_id, field, value } => {
            buf.extend_from_slice(&entity_id.to_le_bytes());
            buf.push(*field);
            buf.extend_from_slice(&value.to_le_bytes());
        }
        Event::Merge { target_id, source_id } => {
            buf.extend_from_slice(&target_id.to_le_bytes());
            buf.extend_from_slice(&source_id.to_le_bytes());
        }
        Event::Partition { entity_id, new_entity_id, partition_key } => {
            buf.extend_from_slice(&entity_id.to_le_bytes());
            buf.extend_from_slice(&new_entity_id.to_le_bytes());
            buf.extend_from_slice(&partition_key.to_le_bytes());
        }
        Event::Commit { entity_id } => {
            buf.extend_from_slice(&entity_id.to_le_bytes());
        }
        Event::Reject { entity_id, reason_code } => {
            buf.extend_from_slice(&entity_id.to_le_bytes());
            buf.extend_from_slice(&reason_code.to_le_bytes());
        }
    }
    buf
}

pub fn decode(bytes: &[u8]) -> Result<Event, DecodeError> {
    if bytes.len() < HEADER_LEN {
        return Err(DecodeError::TooShort(bytes.len()));
    }
    if bytes[0] != DOMAIN_TAG[0] || bytes[1] != DOMAIN_TAG[1] {
        return Err(DecodeError::InvalidDomainTag(bytes[0], bytes[1]));
    }
    if bytes[2] != VERSION {
        return Err(DecodeError::UnsupportedVersion(bytes[2]));
    }
    let d = bytes[3];
    let p = &bytes[HEADER_LEN..];
    match d {
        0x01 => {
            exact(d, p, PAYLOAD_CREATE)?;
            Ok(Event::Create {
                entity_id: u64::from_le_bytes(p[0..8].try_into().unwrap()),
                kind:      u16::from_le_bytes(p[8..10].try_into().unwrap()),
            })
        }
        0x02 => {
            exact(d, p, PAYLOAD_UPDATE)?;
            Ok(Event::Update {
                entity_id: u64::from_le_bytes(p[0..8].try_into().unwrap()),
                field:     p[8],
                value:     u64::from_le_bytes(p[9..17].try_into().unwrap()),
            })
        }
        0x03 => {
            exact(d, p, PAYLOAD_MERGE)?;
            Ok(Event::Merge {
                target_id: u64::from_le_bytes(p[0..8].try_into().unwrap()),
                source_id: u64::from_le_bytes(p[8..16].try_into().unwrap()),
            })
        }
        0x04 => {
            exact(d, p, PAYLOAD_PARTITION)?;
            Ok(Event::Partition {
                entity_id:     u64::from_le_bytes(p[0..8].try_into().unwrap()),
                new_entity_id: u64::from_le_bytes(p[8..16].try_into().unwrap()),
                partition_key: u64::from_le_bytes(p[16..24].try_into().unwrap()),
            })
        }
        0x05 => {
            exact(d, p, PAYLOAD_COMMIT)?;
            Ok(Event::Commit {
                entity_id: u64::from_le_bytes(p[0..8].try_into().unwrap()),
            })
        }
        0x06 => {
            exact(d, p, PAYLOAD_REJECT)?;
            Ok(Event::Reject {
                entity_id:   u64::from_le_bytes(p[0..8].try_into().unwrap()),
                reason_code: u16::from_le_bytes(p[8..10].try_into().unwrap()),
            })
        }
        _ => Err(DecodeError::UnknownDiscriminant(d)),
    }
}

fn exact(d: u8, p: &[u8], expected: usize) -> Result<(), DecodeError> {
    if p.len() != expected {
        Err(DecodeError::WrongLength { discriminant: d, expected, got: p.len() })
    } else {
        Ok(())
    }
}

/// Canonical encoding of the entity map. Input to state_hash computation.
/// BTreeMap iteration order is ascending by key — deterministic.
pub fn encode_entity_map(entities: &BTreeMap<u64, EntityRecord>) -> Vec<u8> {
    let mut buf = Vec::new();
    buf.extend_from_slice(&(entities.len() as u32).to_le_bytes());
    for (id, rec) in entities {
        buf.extend_from_slice(&id.to_le_bytes());
        buf.extend_from_slice(&rec.kind.to_le_bytes());
        buf.push(rec.status as u8);
        buf.extend_from_slice(&rec.linked_id.to_le_bytes());
        buf.push(u8::from(rec.committed));
        buf.extend_from_slice(&(rec.fields.len() as u16).to_le_bytes());
        for (k, v) in &rec.fields {
            buf.push(*k);
            buf.extend_from_slice(&v.to_le_bytes());
        }
    }
    buf
}

/// Full canonical encoding of CompiledState. Used for byte-equality convergence check.
pub fn encode_compiled_state(state: &CompiledState) -> Vec<u8> {
    let mut buf = encode_entity_map(&state.entities);
    buf.extend_from_slice(&state.state_hash);
    buf.extend_from_slice(&state.event_chain_hash);
    buf.extend_from_slice(&state.csp);
    buf
}
