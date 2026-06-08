/// Canonical serialization layer — the actual enforcement boundary for §12.5.
///
/// Wire format (all integers little-endian):
///   [domain_tag: 2B = 0x53 0x49]["SI"]
///   [version:    1B = 0x01]
///   [discriminant: 1B]
///   [payload: discriminant-specific, fixed layout]
///
/// Decode is fail-closed: any byte sequence that does not exactly match the
/// spec produces DecodeError. No partial decodes, no default fallbacks.
use crate::event::Event;
use thiserror::Error;

const DOMAIN_TAG: [u8; 2] = [0x53, 0x49]; // "SI"
const VERSION: u8 = 0x01;
const HEADER_LEN: usize = 4; // tag(2) + version(1) + discriminant(1)

// Payload lengths per discriminant (bytes after the 4-byte header)
const PAYLOAD_ACTIVATE: usize = 8; // entity_id: u64
const PAYLOAD_COMPLETE: usize = 8;
const PAYLOAD_FAIL: usize = 10; // entity_id: u64 + code: u16
const PAYLOAD_RESET: usize = 8;

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
    #[error("wrong payload length for discriminant {discriminant:#04x}: expected {expected}, got {got}")]
    WrongLength {
        discriminant: u8,
        expected: usize,
        got: usize,
    },
}

pub fn encode(event: &Event) -> Vec<u8> {
    let mut buf = Vec::with_capacity(HEADER_LEN + PAYLOAD_FAIL); // max payload
    buf.extend_from_slice(&DOMAIN_TAG);
    buf.push(VERSION);
    buf.push(event.discriminant());
    match event {
        Event::Activate { entity_id } => {
            buf.extend_from_slice(&entity_id.to_le_bytes());
        }
        Event::Complete { entity_id } => {
            buf.extend_from_slice(&entity_id.to_le_bytes());
        }
        Event::Fail { entity_id, code } => {
            buf.extend_from_slice(&entity_id.to_le_bytes());
            buf.extend_from_slice(&code.to_le_bytes());
        }
        Event::Reset { entity_id } => {
            buf.extend_from_slice(&entity_id.to_le_bytes());
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

    let discriminant = bytes[3];
    let payload = &bytes[HEADER_LEN..];

    match discriminant {
        0x01 => {
            exact_payload(discriminant, payload, PAYLOAD_ACTIVATE)?;
            Ok(Event::Activate {
                entity_id: u64::from_le_bytes(payload[0..8].try_into().unwrap()),
            })
        }
        0x02 => {
            exact_payload(discriminant, payload, PAYLOAD_COMPLETE)?;
            Ok(Event::Complete {
                entity_id: u64::from_le_bytes(payload[0..8].try_into().unwrap()),
            })
        }
        0x03 => {
            exact_payload(discriminant, payload, PAYLOAD_FAIL)?;
            Ok(Event::Fail {
                entity_id: u64::from_le_bytes(payload[0..8].try_into().unwrap()),
                code: u16::from_le_bytes(payload[8..10].try_into().unwrap()),
            })
        }
        0x04 => {
            exact_payload(discriminant, payload, PAYLOAD_RESET)?;
            Ok(Event::Reset {
                entity_id: u64::from_le_bytes(payload[0..8].try_into().unwrap()),
            })
        }
        d => Err(DecodeError::UnknownDiscriminant(d)),
    }
}

fn exact_payload(discriminant: u8, payload: &[u8], expected: usize) -> Result<(), DecodeError> {
    if payload.len() != expected {
        Err(DecodeError::WrongLength {
            discriminant,
            expected,
            got: payload.len(),
        })
    } else {
        Ok(())
    }
}
