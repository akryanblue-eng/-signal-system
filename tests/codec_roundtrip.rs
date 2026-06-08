use signal_system::codec::{decode, encode, DecodeError};
use signal_system::event::Event;

fn all_events() -> Vec<Event> {
    vec![
        Event::Activate { entity_id: 0 },
        Event::Activate { entity_id: u64::MAX },
        Event::Activate { entity_id: 42 },
        Event::Complete { entity_id: 1 },
        Event::Complete { entity_id: u64::MAX },
        Event::Fail { entity_id: 7, code: 0 },
        Event::Fail { entity_id: 7, code: u16::MAX },
        Event::Fail { entity_id: 0, code: 404 },
        Event::Reset { entity_id: 99 },
        Event::Reset { entity_id: u64::MAX },
    ]
}

#[test]
fn encode_decode_roundtrip() {
    for event in all_events() {
        let encoded = encode(&event);
        let decoded = decode(&encoded).expect("roundtrip must succeed");
        assert_eq!(decoded, event, "roundtrip failed for {event:?}");
    }
}

#[test]
fn encoding_is_stable() {
    // Same event encodes to identical bytes every time — no entropy in encoder.
    let event = Event::Fail { entity_id: 12345, code: 999 };
    let a = encode(&event);
    let b = encode(&event);
    assert_eq!(a, b);
}

#[test]
fn encoding_is_canonical_little_endian() {
    let event = Event::Activate { entity_id: 0x0102030405060708 };
    let bytes = encode(&event);
    // entity_id starts at offset 4; little-endian: LSB first
    assert_eq!(&bytes[4..12], &[0x08, 0x07, 0x06, 0x05, 0x04, 0x03, 0x02, 0x01]);
}

#[test]
fn domain_tag_is_present() {
    let bytes = encode(&Event::Activate { entity_id: 0 });
    assert_eq!(bytes[0], 0x53, "first domain tag byte must be 0x53");
    assert_eq!(bytes[1], 0x49, "second domain tag byte must be 0x49");
    assert_eq!(bytes[2], 0x01, "version must be 0x01");
}

// --- Fail-closed decode tests ---

#[test]
fn decode_rejects_empty() {
    assert_eq!(decode(&[]), Err(DecodeError::TooShort(0)));
}

#[test]
fn decode_rejects_short_header() {
    assert_eq!(decode(&[0x53, 0x49, 0x01]), Err(DecodeError::TooShort(3)));
}

#[test]
fn decode_rejects_wrong_domain_tag() {
    let mut bytes = encode(&Event::Activate { entity_id: 1 });
    bytes[0] = 0xFF;
    assert!(matches!(decode(&bytes), Err(DecodeError::InvalidDomainTag(..))));
}

#[test]
fn decode_rejects_wrong_version() {
    let mut bytes = encode(&Event::Activate { entity_id: 1 });
    bytes[2] = 0x02;
    assert!(matches!(decode(&bytes), Err(DecodeError::UnsupportedVersion(0x02))));
}

#[test]
fn decode_rejects_unknown_discriminant() {
    let bytes = [0x53, 0x49, 0x01, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00];
    assert!(matches!(decode(&bytes), Err(DecodeError::UnknownDiscriminant(0xFF))));
}

#[test]
fn decode_rejects_truncated_payload() {
    // Activate with only 4 bytes of payload instead of 8
    let bytes = [0x53, 0x49, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00];
    assert!(matches!(decode(&bytes), Err(DecodeError::WrongLength { .. })));
}

#[test]
fn decode_rejects_padded_payload() {
    // Activate with 9 bytes of payload instead of 8 (one extra byte appended)
    let mut bytes = encode(&Event::Activate { entity_id: 1 });
    bytes.push(0x00);
    assert!(matches!(decode(&bytes), Err(DecodeError::WrongLength { .. })));
}
