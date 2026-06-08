use crate::types::{Step, StepResult, VdceError};
use serde_json::Value;

/// Execute a single step deterministically, producing its output value.
pub fn execute_step(step: &Step) -> Result<StepResult, VdceError> {
    let sid = step.step_id;
    let exec_err = |reason: &str| VdceError::ExecutionError {
        step_id: sid,
        reason: reason.to_string(),
    };

    let output: Value = match step.operation.as_str() {
        "identity" => step.inputs.clone(),

        "add" => {
            let a = step.inputs["a"].as_f64().ok_or_else(|| exec_err("a is not a number"))?;
            let b = step.inputs["b"].as_f64().ok_or_else(|| exec_err("b is not a number"))?;
            let result = a + b;
            // Emit integer JSON when the result is a whole number within safe range.
            if result == result.trunc() && result.abs() < 9.007_199_254_740_992e15 {
                serde_json::json!({ "result": result as i64 })
            } else {
                serde_json::json!({ "result": result })
            }
        }

        "concat" => {
            let parts = step.inputs["parts"]
                .as_array()
                .ok_or_else(|| exec_err("parts is not an array"))?;
            let result: String = parts
                .iter()
                .map(|v| v.as_str().unwrap_or(""))
                .collect();
            serde_json::json!({ "result": result })
        }

        op => {
            return Err(VdceError::ExecutionError {
                step_id: sid,
                reason: format!("unhandled operation {op:?}"),
            });
        }
    };

    Ok(StepResult { step_id: sid, output })
}
