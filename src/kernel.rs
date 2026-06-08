/// Pure execution kernel: a fold over a totally ordered event sequence.
/// No I/O, no side effects, no entropy sources. Given the same initial state
/// and the same event sequence, this function always returns the same result.
use crate::event::{transition, Event, State, TransitionError};
use thiserror::Error;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum KernelError {
    #[error("transition failed at position {position}: {source}")]
    Transition {
        position: usize,
        #[source]
        source: TransitionError,
    },
}

/// Fold an ordered event sequence onto an initial state.
/// Returns Err at the first invalid transition — does not skip or recover.
pub fn fold<I>(initial: State, events: I) -> Result<State, KernelError>
where
    I: IntoIterator<Item = Event>,
{
    events
        .into_iter()
        .enumerate()
        .try_fold(initial, |state, (position, event)| {
            transition(state, &event).map_err(|source| KernelError::Transition { position, source })
        })
}
