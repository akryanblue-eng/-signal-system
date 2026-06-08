use crate::types::{Step, StepResult, VdceError};

/// Row 5: canonical semantic comparison — actual output must equal declared
/// expected_output by JSON value identity.
pub fn check_semantic(step: &Step, result: &StepResult) -> Result<(), VdceError> {
    if result.output != step.expected_output {
        return Err(VdceError::SemanticMismatch {
            step_id: step.step_id,
            expected: step.expected_output.clone(),
            actual: result.output.clone(),
        });
    }
    Ok(())
}
