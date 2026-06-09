use serde::Serialize;

use crate::director_loop::{DirectorLoopRun, Status, compute_input_hash, compute_output_hash};

#[derive(Debug, Serialize, PartialEq)]
pub enum AuditStatus {
    #[serde(rename = "PASS")]
    Pass,
    #[serde(rename = "FAIL")]
    Fail,
}

#[derive(Debug, Serialize)]
pub struct VerifierReport {
    pub audit_status: AuditStatus,
    pub schema_valid: bool,
    pub transition_valid: bool,
    pub input_hash_valid: bool,
    pub output_hash_valid: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub failure_reason: Option<String>,
}

impl VerifierReport {
    fn pass() -> Self {
        VerifierReport {
            audit_status: AuditStatus::Pass,
            schema_valid: true,
            transition_valid: true,
            input_hash_valid: true,
            output_hash_valid: true,
            failure_reason: None,
        }
    }

    fn schema_fail(reason: String) -> Self {
        VerifierReport {
            audit_status: AuditStatus::Fail,
            schema_valid: false,
            transition_valid: false,
            input_hash_valid: false,
            output_hash_valid: false,
            failure_reason: Some(reason),
        }
    }

    fn invariant_fail(reason: String) -> Self {
        VerifierReport {
            audit_status: AuditStatus::Fail,
            schema_valid: true,
            transition_valid: false,
            input_hash_valid: false,
            output_hash_valid: false,
            failure_reason: Some(reason),
        }
    }

    fn input_hash_fail(artifact: &str, computed: &str) -> Self {
        VerifierReport {
            audit_status: AuditStatus::Fail,
            schema_valid: true,
            transition_valid: true,
            input_hash_valid: false,
            output_hash_valid: false,
            failure_reason: Some(format!(
                "input_hash mismatch: artifact={artifact} computed={computed}"
            )),
        }
    }

    fn output_hash_fail(artifact: &str, computed: &str) -> Self {
        VerifierReport {
            audit_status: AuditStatus::Fail,
            schema_valid: true,
            transition_valid: true,
            input_hash_valid: true,
            output_hash_valid: false,
            failure_reason: Some(format!(
                "output_hash mismatch: artifact={artifact} computed={computed}"
            )),
        }
    }
}

// ── Pipeline ─────────────────────────────────────────────────────────────────
// Fail-fast order: schema → invariants → input_hash → output_hash.
// Each stage runs only if the previous passed.

/// Entry point for raw JSON bytes. Schema validation happens at parse time via
/// `#[serde(deny_unknown_fields)]` on all domain structs.
pub fn verify_bytes(bytes: &[u8]) -> VerifierReport {
    match serde_json::from_slice::<DirectorLoopRun>(bytes) {
        Err(e) => VerifierReport::schema_fail(format!("parse error: {e}")),
        Ok(run) => verify(&run),
    }
}

/// Entry point when the artifact is already parsed.
pub fn verify(run: &DirectorLoopRun) -> VerifierReport {
    if let Some(reason) = check_invariants(run) {
        return VerifierReport::invariant_fail(reason);
    }

    let expected_input = compute_input_hash(run);
    if run.input_hash != expected_input {
        return VerifierReport::input_hash_fail(&run.input_hash, &expected_input);
    }

    let expected_output = compute_output_hash(run);
    if run.output_hash != expected_output {
        return VerifierReport::output_hash_fail(&run.output_hash, &expected_output);
    }

    VerifierReport::pass()
}

// ── Structural invariants ────────────────────────────────────────────────────

fn check_invariants(run: &DirectorLoopRun) -> Option<String> {
    // PASSED requires final_coherence >= threshold
    if run.status == Status::Passed && run.final_coherence < run.threshold {
        return Some(format!(
            "invariant: PASSED but final_coherence ({}) < threshold ({})",
            run.final_coherence, run.threshold
        ));
    }

    // REGENERATED requires at least one regen_event
    if run.status == Status::Regenerated && run.regen_events.is_empty() {
        return Some("invariant: REGENERATED but regen_events is empty".to_string());
    }

    // corrections must be non-decreasing by beat_id (emission order preserved)
    let beats: Vec<&str> = run.corrections.iter().map(|c| c.beat_id.as_str()).collect();
    if beats.windows(2).any(|w| w[0] > w[1]) {
        return Some(format!(
            "invariant: corrections not in beat_id order: {:?}",
            beats
        ));
    }

    // audit_notes must be in non-decreasing phase order (prefix sort)
    if run.audit_notes.windows(2).any(|w| w[0] > w[1]) {
        return Some(format!(
            "invariant: audit_notes not in phase order: {:?}",
            &run.audit_notes
        ));
    }

    None
}
