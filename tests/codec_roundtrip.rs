use signal_system::codec::{decode, encode, DecodeError};
use signal_system::event::Event;

fn all_events() -> Vec<Event> {
    vec![
        Event::Create    { entity_id: 0,          kind: 0 },
        Event::Create    { entity_id: u64::MAX,   kind: u16::MAX },
        Event::Create    { entity_id: 42,         kind: 7 },
        Event::Update    { entity_id: 1,          field: 0,    value: 0 },
        Event::Update    { entity_id: u64::MAX,   field: 0xFF, value: u64::MAX },
        Event::Update    { entity_id: 99,         field: 3,    value: 12345 },
        Event::Merge     { target_id: 1,          source_id: 2 },
        Event::Merge     { target_id: u64::MAX,   source_id: 0 },
        Event::Partition { entity_id: 10, new_entity_id: 20, partition_key: 0 },
        Event::Partition { entity_id: 10, new_entity_id: 20, partition_key: u64::MAX },
        Event::Commit    { entity_id: 5 },
        Event::Commit    { entity_id: u64::MAX },
        Event::Reject    { entity_id: 3,          reason_code: 0 },
        Event::Reject    { entity_id: 3,          reason_code: u16::MAX },
        Event::Reject    { entity_id: 0,          reason_code: 404 },
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
    let event = Event::Merge { target_id: 99, source_id: 1234 };
    assert_eq!(encode(&event), encode(&event));
}

#[test]
fn encoding_is_little_endian() {
    // Update: entity_id at offset 4, value at offset 13 (4 header + 8 entity_id + 1 field)
    let event = Event::Update { entity_id: 0x0102030405060708, field: 0, value: 0x0A0B0C0D0E0F1011 };
    let bytes = encode(&event);
    assert_eq!(&bytes[4..12], &[0x08, 0x07, 0x06, 0x05, 0x04, 0x03, 0x02, 0x01]);
    assert_eq!(&bytes[13..21], &[0x11, 0x10, 0x0F, 0x0E, 0x0D, 0x0C, 0x0B, 0x0A]);
}

#[test]
fn domain_tag_and_version_are_present() {
    for event in all_events() {
        let bytes = encode(&event);
        assert_eq!(bytes[0], 0x53);
        assert_eq!(bytes[1], 0x49);
        assert_eq!(bytes[2], 0x01);
    }
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
    let mut bytes = encode(&Event::Create { entity_id: 1, kind: 0 });
    bytes[0] = 0xFF;
    assert!(matches!(decode(&bytes), Err(DecodeError::InvalidDomainTag(..))));
}

#[test]
fn decode_rejects_wrong_version() {
    let mut bytes = encode(&Event::Create { entity_id: 1, kind: 0 });
    bytes[2] = 0x02;
    assert!(matches!(decode(&bytes), Err(DecodeError::UnsupportedVersion(0x02))));
}

#[test]
fn decode_rejects_unknown_discriminant() {
    let bytes = [0x53, 0x49, 0x01, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0];
    assert!(matches!(decode(&bytes), Err(DecodeError::UnknownDiscriminant(0xFF))));
}

#[test]
fn decode_rejects_truncated_payload() {
    // Commit needs 8 bytes payload; give it 4
    let bytes = [0x53, 0x49, 0x01, 0x05, 0x00, 0x00, 0x00, 0x00];
    assert!(matches!(decode(&bytes), Err(DecodeError::WrongLength { .. })));
}

#[test]
fn decode_rejects_padded_payload() {
    let mut bytes = encode(&Event::Commit { entity_id: 1 });
    bytes.push(0x00); // one extra byte
    assert!(matches!(decode(&bytes), Err(DecodeError::WrongLength { .. })));
}
