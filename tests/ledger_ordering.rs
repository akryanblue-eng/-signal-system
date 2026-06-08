use signal_system::codec::encode;
use signal_system::event::Event;
use signal_system::ledger::Ledger;

fn sample_events() -> Vec<Event> {
    vec![
        Event::Create    { entity_id: 1, kind: 5 },
        Event::Update    { entity_id: 1, field: 0, value: 42 },
        Event::Create    { entity_id: 2, kind: 3 },
        Event::Merge     { target_id: 1, source_id: 2 },
        Event::Reject    { entity_id: 1, reason_code: 0 },
        Event::Commit    { entity_id: 1 },
    ]
}

#[test]
fn append_and_read_ordered() {
    let ledger = Ledger::open_in_memory().unwrap();
    let encoded: Vec<Vec<u8>> = sample_events().iter().map(encode).collect();
    for bytes in &encoded {
        ledger.append(bytes).unwrap();
    }
    assert_eq!(ledger.read_ordered().unwrap(), encoded);
}

#[test]
fn sequence_numbers_are_monotone() {
    let ledger = Ledger::open_in_memory().unwrap();
    let seqs: Vec<u64> = sample_events()
        .iter()
        .map(|e| ledger.append(&encode(e)).unwrap())
        .collect();
    for w in seqs.windows(2) {
        assert!(w[1] > w[0]);
    }
}

#[test]
fn read_at_returns_correct_bytes() {
    let ledger = Ledger::open_in_memory().unwrap();
    let bytes = encode(&Event::Partition { entity_id: 1, new_entity_id: 2, partition_key: 0x0007 });
    let seq = ledger.append(&bytes).unwrap();
    assert_eq!(ledger.read_at(seq).unwrap(), Some(bytes));
}

#[test]
fn read_at_missing_seq_returns_none() {
    let ledger = Ledger::open_in_memory().unwrap();
    assert_eq!(ledger.read_at(9999).unwrap(), None);
}

#[test]
fn len_reflects_appends() {
    let ledger = Ledger::open_in_memory().unwrap();
    assert_eq!(ledger.len().unwrap(), 0);
    for e in sample_events() {
        ledger.append(&encode(&e)).unwrap();
    }
    assert_eq!(ledger.len().unwrap(), 6);
}

#[test]
fn bytes_stored_are_not_interpreted() {
    let ledger = Ledger::open_in_memory().unwrap();
    let arbitrary = b"not a valid event at all".to_vec();
    let seq = ledger.append(&arbitrary).unwrap();
    assert_eq!(ledger.read_at(seq).unwrap().unwrap(), arbitrary);
}
