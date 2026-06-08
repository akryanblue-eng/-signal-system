use thiserror::Error;

/// All valid states of an entity. No catch-all variant — unknown states
/// are a codec error, not a valid runtime condition.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum State {
    Pending = 0x00,
    Active = 0x01,
    Completed = 0x02,
    Failed = 0x03,
}

/// All valid signal events. Discriminants are fixed and must match codec.rs.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    Activate { entity_id: u64 },
    Complete { entity_id: u64 },
    Fail { entity_id: u64, code: u16 },
    Reset { entity_id: u64 },
}

impl Event {
    pub fn discriminant(&self) -> u8 {
        match self {
            Event::Activate { .. } => 0x01,
            Event::Complete { .. } => 0x02,
            Event::Fail { .. } => 0x03,
            Event::Reset { .. } => 0x04,
        }
    }
}

#[derive(Debug, Error, PartialEq, Eq)]
pub enum TransitionError {
    #[error("invalid transition: {state:?} + {event_discriminant:#04x}")]
    Invalid { state: State, event_discriminant: u8 },
}

/// Total transition function. Every (State, Event) pair is explicitly handled;
/// anything not listed here is a protocol violation, not a runtime default.
pub fn transition(state: State, event: &Event) -> Result<State, TransitionError> {
    match (state, event) {
        (State::Pending, Event::Activate { .. }) => Ok(State::Active),
        (State::Active, Event::Complete { .. }) => Ok(State::Completed),
        (State::Active, Event::Fail { .. }) => Ok(State::Failed),
        (State::Failed, Event::Reset { .. }) => Ok(State::Pending),
        _ => Err(TransitionError::Invalid {
            state,
            event_discriminant: event.discriminant(),
        }),
    }
}
