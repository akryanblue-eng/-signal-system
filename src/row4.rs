use crate::types::{Trace, VdceError};

/// Closed world of operations the kernel can execute.
const KNOWN_OPERATIONS: &[&str] = &["identity", "add", "concat"];

/// Closed world of permissible nondet guard names.
const KNOWN_NONDET_GUARDS: &[&str] = &["timestamp", "random_seed", "external_value"];

/// Row 4: closed-world sufficiency checks on decoded record inputs and declared
/// nondet guards.
///
/// Rejects any step whose operation or guards fall outside the declared closed
/// world, and validates that required input fields are present and well-typed.
pub fn check_closed_world(trace: &Trace) -> Result<(), VdceError> {
    for step in &trace.steps {
        let sid = step.step_id;

        if !KNOWN_OPERATIONS.contains(&step.operation.as_str()) {
            return Err(VdceError::ClosedWorldViolation {
                step_id: sid,
                reason: format!("unknown operation {:?}", step.operation),
            });
        }

        for guard in &step.nondet_guards {
            if !KNOWN_NONDET_GUARDS.contains(&guard.name.as_str()) {
                return Err(VdceError::ClosedWorldViolation {
                    step_id: sid,
                    reason: format!("unknown nondet guard {:?}", guard.name),
                });
            }
        }

        check_inputs(sid, &step.operation, &step.inputs)?;
    }
    Ok(())
}

fn check_inputs(step_id: u64, op: &str, inputs: &serde_json::Value) -> Result<(), VdceError> {
    let cw_err = |reason: &str| VdceError::ClosedWorldViolation {
        step_id,
        reason: reason.to_string(),
    };

    match op {
        "identity" => {
            if inputs.is_null() {
                return Err(cw_err("'identity' requires non-null inputs"));
            }
        }
        "add" => {
            match (inputs.get("a"), inputs.get("b")) {
                (Some(a), Some(b)) if a.is_number() && b.is_number() => {}
                _ => return Err(cw_err("'add' requires numeric inputs.a and inputs.b")),
            }
        }
        "concat" => {
            match inputs.get("parts") {
                Some(p) if p.is_array() => {}
                _ => return Err(cw_err("'concat' requires inputs.parts as array")),
            }
        }
        _ => {}
    }
    Ok(())
}
