use signal_system::codec::encode;
use signal_system::event::Event;
use signal_system::ledger::Ledger;

fn sample_events() -> Vec<Event> {
    vec![
        Event::Activate { entity_id: 1 },
        Event::Complete { entity_id: 1 },
        Event::Activate { entity_id: 2 },
        Event::Fail { entity_id: 2, code: 404 },
        Event::Reset { entity_id: 2 },
    ]
}

#[test]
fn append_and_read_ordered() {
    let ledger = Ledger::open_in_memory().unwrap();
    let events = sample_events();
    let encoded: Vec<Vec<u8>> = events.iter().map(encode).collect();

    for bytes in &encoded {
        ledger.append(bytes).unwrap();
    }

    let stored = ledger.read_ordered().unwrap();
    assert_eq!(stored, encoded, "stored order must match insertion order");
}

#[test]
fn sequence_numbers_are_monotone() {
    let ledger = Ledger::open_in_memory().unwrap();
    let seqs: Vec<u64> = sample_events()
        .iter()
        .map(|e| ledger.append(&encode(e)).unwrap())
        .collect();

    for window in seqs.windows(2) {
        assert!(window[1] > window[0], "sequence numbers must strictly increase");
    }
}

#[test]
fn read_at_returns_correct_bytes() {
    let ledger = Ledger::open_in_memory().unwrap();
    let event = Event::Fail { entity_id: 77, code: 500 };
    let bytes = encode(&event);
    let seq = ledger.append(&bytes).unwrap();

    let retrieved = ledger.read_at(seq).unwrap();
    assert_eq!(retrieved, Some(bytes));
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

    for event in sample_events() {
        ledger.append(&encode(&event)).unwrap();
    }
    assert_eq!(ledger.len().unwrap(), 5);
}

#[test]
fn bytes_stored_are_not_interpreted() {
    // Ledger must store arbitrary bytes — it does not reject non-event bytes.
    // Validation is the codec's job, not the ledger's.
    let ledger = Ledger::open_in_memory().unwrap();
    let arbitrary = b"not a valid event at all".to_vec();
    let seq = ledger.append(&arbitrary).unwrap();
    let retrieved = ledger.read_at(seq).unwrap().unwrap();
    assert_eq!(retrieved, arbitrary);
}
