use crate::decode::decode_and_validate;
use crate::execute::execute_step;
use crate::row4::check_closed_world;
use crate::row5::check_semantic;
use crate::row5a::check_continuity;
use crate::types::{ReplayOkParts, VdceError};

/// VDCE v1.1 replay kernel.
///
/// Frozen execution order:
///   Decode/Schema  →  Row 5a (continuity)  →  Row 4 (closed-world)
///   →  [Execute → Row 5] per step  →  Halt
///
/// Empty trace (0 steps) is valid and produces ReplayOkParts { steps_replayed: 0 }.
pub fn replay(trace_bytes: &[u8]) -> Result<ReplayOkParts, VdceError> {
    // Stage 1: Decode / Schema Gate
    let trace = decode_and_validate(trace_bytes)?;

    // Stage 2: Row 5a — continuity (trace integrity, no closed-world reasoning needed)
    check_continuity(&trace)?;

    // Stage 3: Row 4 — closed-world sufficiency
    check_closed_world(&trace)?;

    // Stages 4 + 5 interleaved per step: Execute then semantic comparison
    let mut step_results = Vec::with_capacity(trace.steps.len());
    for step in &trace.steps {
        let result = execute_step(step)?;
        check_semantic(step, &result)?;
        step_results.push(result);
    }

    Ok(ReplayOkParts {
        steps_replayed: step_results.len(),
        step_results,
    })
}
