use serde::{Deserialize, Serialize};
use serde_json::Value;
use thiserror::Error;

pub const SUPPORTED_SCHEMA_VERSION: u32 = 1;
pub const SUPPORTED_REDUCER_VERSION: &str = "1.1";

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Trace {
    pub schema_version: u32,
    pub reducer_version: String,
    pub steps: Vec<Step>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Step {
    pub step_id: u64,
    pub operation: String,
    pub inputs: Value,
    pub expected_output: Value,
    #[serde(default)]
    pub nondet_guards: Vec<NondetGuard>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct NondetGuard {
    pub name: String,
    pub value: Value,
}

#[derive(Debug)]
pub struct ReplayOkParts {
    pub steps_replayed: usize,
    pub step_results: Vec<StepResult>,
}

#[derive(Debug)]
pub struct StepResult {
    pub step_id: u64,
    pub output: Value,
}

#[derive(Debug, Error)]
pub enum VdceError {
    #[error("schema/decode error: {0}")]
    SchemaOrDecode(String),

    #[error("trace invariant violation: {0}")]
    TraceInvariantViolation(String),

    #[error("closed-world violation at step {step_id}: {reason}")]
    ClosedWorldViolation { step_id: u64, reason: String },

    #[error("execution error at step {step_id}: {reason}")]
    ExecutionError { step_id: u64, reason: String },

    #[error("semantic mismatch at step {step_id}: expected {expected}, got {actual}")]
    SemanticMismatch {
        step_id: u64,
        expected: Value,
        actual: Value,
    },
}
