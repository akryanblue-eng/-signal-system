use crate::types::{Trace, VdceError};

/// Row 5a: continuity — trace integrity predicate.
///
/// Enforces that step_ids form a 0-based consecutive sequence with no gaps or
/// duplicates.  This is a structural property of the trace itself and does not
/// require closed-world reasoning, so it runs before Row 4.
pub fn check_continuity(trace: &Trace) -> Result<(), VdceError> {
    for (index, step) in trace.steps.iter().enumerate() {
        let expected_id = index as u64;
        if step.step_id != expected_id {
            return Err(VdceError::TraceInvariantViolation(format!(
                "continuity broken: position {} has step_id {} (expected {})",
                index, step.step_id, expected_id
            )));
        }
    }
    Ok(())
}
