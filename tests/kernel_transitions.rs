use signal_system::event::{Event, State};
use signal_system::kernel::{fold, KernelError};

// --- Valid paths through the state machine ---

#[test]
fn pending_activate_active() {
    let result = fold(State::Pending, [Event::Activate { entity_id: 1 }]);
    assert_eq!(result, Ok(State::Active));
}

#[test]
fn active_complete_completed() {
    let result = fold(State::Active, [Event::Complete { entity_id: 1 }]);
    assert_eq!(result, Ok(State::Completed));
}

#[test]
fn active_fail_failed() {
    let result = fold(State::Active, [Event::Fail { entity_id: 1, code: 500 }]);
    assert_eq!(result, Ok(State::Failed));
}

#[test]
fn failed_reset_pending() {
    let result = fold(State::Failed, [Event::Reset { entity_id: 1 }]);
    assert_eq!(result, Ok(State::Pending));
}

#[test]
fn full_lifecycle() {
    let events = vec![
        Event::Activate { entity_id: 1 },
        Event::Fail { entity_id: 1, code: 503 },
        Event::Reset { entity_id: 1 },
        Event::Activate { entity_id: 1 },
        Event::Complete { entity_id: 1 },
    ];
    assert_eq!(fold(State::Pending, events), Ok(State::Completed));
}

#[test]
fn empty_sequence_returns_initial_state() {
    assert_eq!(fold(State::Pending, []), Ok(State::Pending));
    assert_eq!(fold(State::Active, []), Ok(State::Active));
    assert_eq!(fold(State::Completed, []), Ok(State::Completed));
}

// --- Invalid transitions — every illegal (state, event) combination ---

fn assert_invalid(initial: State, event: Event, expected_position: usize) {
    let result = fold(initial, [event]);
    assert!(
        matches!(result, Err(KernelError::Transition { position, .. }) if position == expected_position),
        "expected Transition error at position {expected_position}, got {result:?}"
    );
}

#[test]
fn pending_cannot_complete() {
    assert_invalid(State::Pending, Event::Complete { entity_id: 1 }, 0);
}

#[test]
fn pending_cannot_fail() {
    assert_invalid(State::Pending, Event::Fail { entity_id: 1, code: 0 }, 0);
}

#[test]
fn pending_cannot_reset() {
    assert_invalid(State::Pending, Event::Reset { entity_id: 1 }, 0);
}

#[test]
fn active_cannot_activate() {
    assert_invalid(State::Active, Event::Activate { entity_id: 1 }, 0);
}

#[test]
fn active_cannot_reset() {
    assert_invalid(State::Active, Event::Reset { entity_id: 1 }, 0);
}

#[test]
fn completed_cannot_activate() {
    assert_invalid(State::Completed, Event::Activate { entity_id: 1 }, 0);
}

#[test]
fn completed_cannot_complete() {
    assert_invalid(State::Completed, Event::Complete { entity_id: 1 }, 0);
}

#[test]
fn completed_cannot_fail() {
    assert_invalid(State::Completed, Event::Fail { entity_id: 1, code: 0 }, 0);
}

#[test]
fn completed_cannot_reset() {
    assert_invalid(State::Completed, Event::Reset { entity_id: 1 }, 0);
}

#[test]
fn failed_cannot_activate() {
    assert_invalid(State::Failed, Event::Activate { entity_id: 1 }, 0);
}

#[test]
fn failed_cannot_complete() {
    assert_invalid(State::Failed, Event::Complete { entity_id: 1 }, 0);
}

#[test]
fn failed_cannot_fail_again() {
    assert_invalid(State::Failed, Event::Fail { entity_id: 1, code: 0 }, 0);
}

#[test]
fn fold_stops_at_first_invalid_transition() {
    // Position 1 is invalid (Complete from Pending after failed Activate)
    // but we can't get there; test that position is reported correctly
    let events = vec![
        Event::Activate { entity_id: 1 },   // 0 — valid: Pending → Active
        Event::Activate { entity_id: 1 },   // 1 — invalid: Active + Activate
        Event::Complete { entity_id: 1 },   // 2 — never reached
    ];
    let result = fold(State::Pending, events);
    assert!(
        matches!(result, Err(KernelError::Transition { position: 1, .. })),
        "expected error at position 1, got {result:?}"
    );
}
