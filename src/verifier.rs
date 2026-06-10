use serde::Serialize;

use crate::director_loop::{compute_input_hash, compute_output_hash, DirectorLoopRun, Status};

// ── Gate outcome types ───────────────────────────────────────────────────────

/// Outcome of a single pipeline gate. Field definition order is the
/// serialization order; never reorder.
#[derive(Debug, Serialize, PartialEq)]
pub struct GateOutcome {
    pub result: GateResult,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub failure_code: Option<FailureCode>,
    /// JSON path to the first offending field, e.g. "corrections[1].beat_id".
    /// Present only on Fail; omitted on Pass and NotEvaluated.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
}

#[derive(Debug, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum GateResult {
    Pass,
    Fail,
    NotEvaluated,
}

/// Typed failure codes — one variant per root cause.
/// Tests assert on these directly; CI reads them without parsing free text.
#[derive(Debug, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum FailureCode {
    // schema gate
    SchemaViolation,
    // invariants gate — ordering
    CorrectionsOutOfOrder,
    AuditNotesOutOfOrder,
    // invariants gate — state machine
    PassedBelowThreshold,
    RegenWithoutEvents,
    // hash gate
    InputHashDrift,
    OutputHashDrift,
}

impl GateOutcome {
    fn pass() -> Self {
        GateOutcome {
            result: GateResult::Pass,
            failure_code: None,
            path: None,
        }
    }
    fn fail(code: FailureCode, path: impl Into<String>) -> Self {
        GateOutcome {
            result: GateResult::Fail,
            failure_code: Some(code),
            path: Some(path.into()),
        }
    }
    fn fail_no_path(code: FailureCode) -> Self {
        GateOutcome {
            result: GateResult::Fail,
            failure_code: Some(code),
            path: None,
        }
    }
    fn not_evaluated() -> Self {
        GateOutcome {
            result: GateResult::NotEvaluated,
            failure_code: None,
            path: None,
        }
    }
}

// ── Report ───────────────────────────────────────────────────────────────────

/// Gate results in pipeline order. Named fields (not BTreeMap) — type-safe and
/// deterministically serialized in definition order by serde.
#[derive(Debug, Serialize)]
pub struct GateResults {
    pub schema: GateOutcome,
    pub invariants: GateOutcome,
    pub input_hash: GateOutcome,
    pub output_hash: GateOutcome,
}

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
    pub gates: GateResults,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub failure_detail: Option<String>,
}

// ── Pipeline ─────────────────────────────────────────────────────────────────
// Order: schema → invariants → input_hash → output_hash.
//
// Invariants gate covers BOTH ordering checks and state-machine semantics.
// All invariant checks are preconditions for trusting the hashes; running
// state-machine checks after hash verification would be less fail-fast, not more.

/// Entry point for raw JSON bytes.
/// Schema enforcement happens at parse time via #[serde(deny_unknown_fields)].
/// Any parse failure → schema gate Fail; downstream gates NotEvaluated.
pub fn verify_bytes(bytes: &[u8]) -> VerifierReport {
    match serde_json::from_slice::<DirectorLoopRun>(bytes) {
        Err(e) => fail_at_schema(e.to_string()),
        Ok(run) => verify(&run),
    }
}

/// Entry point when the caller already holds a parsed artifact.
/// Schema gate is implicitly Pass (deny_unknown_fields already enforced).
pub fn verify(run: &DirectorLoopRun) -> VerifierReport {
    // Gate 2: invariants
    let inv = check_invariants(run);
    if inv.result == GateResult::Fail {
        return VerifierReport {
            audit_status: AuditStatus::Fail,
            gates: GateResults {
                schema: GateOutcome::pass(),
                invariants: inv,
                input_hash: GateOutcome::not_evaluated(),
                output_hash: GateOutcome::not_evaluated(),
            },
            failure_detail: None,
        };
    }

    // Gate 3: input_hash
    let expected_input = compute_input_hash(run);
    if run.input_hash != expected_input {
        return VerifierReport {
            audit_status: AuditStatus::Fail,
            gates: GateResults {
                schema: GateOutcome::pass(),
                invariants: inv,
                input_hash: GateOutcome::fail(FailureCode::InputHashDrift, "input_hash"),
                output_hash: GateOutcome::not_evaluated(),
            },
            failure_detail: Some(format!(
                "input_hash: artifact={} computed={}",
                run.input_hash, expected_input
            )),
        };
    }

    // Gate 4: output_hash
    let expected_output = compute_output_hash(run);
    if run.output_hash != expected_output {
        return VerifierReport {
            audit_status: AuditStatus::Fail,
            gates: GateResults {
                schema: GateOutcome::pass(),
                invariants: inv,
                input_hash: GateOutcome::pass(),
                output_hash: GateOutcome::fail(FailureCode::OutputHashDrift, "output_hash"),
            },
            failure_detail: Some(format!(
                "output_hash: artifact={} computed={}",
                run.output_hash, expected_output
            )),
        };
    }

    VerifierReport {
        audit_status: AuditStatus::Pass,
        gates: GateResults {
            schema: GateOutcome::pass(),
            invariants: inv,
            input_hash: GateOutcome::pass(),
            output_hash: GateOutcome::pass(),
        },
        failure_detail: None,
    }
}

// ── Schema failure constructor ────────────────────────────────────────────────

fn fail_at_schema(detail: String) -> VerifierReport {
    VerifierReport {
        audit_status: AuditStatus::Fail,
        gates: GateResults {
            schema: GateOutcome::fail_no_path(FailureCode::SchemaViolation),
            invariants: GateOutcome::not_evaluated(),
            input_hash: GateOutcome::not_evaluated(),
            output_hash: GateOutcome::not_evaluated(),
        },
        failure_detail: Some(detail),
    }
}

// ── Invariant checks ─────────────────────────────────────────────────────────

fn check_invariants(run: &DirectorLoopRun) -> GateOutcome {
    // Corrections must be in non-decreasing beat_id order (emission order preserved).
    let beats: Vec<&str> = run.corrections.iter().map(|c| c.beat_id.as_str()).collect();
    if let Some(i) = beats.windows(2).position(|w| w[0] > w[1]) {
        return GateOutcome::fail(
            FailureCode::CorrectionsOutOfOrder,
            format!("corrections[{}].beat_id", i + 1),
        );
    }

    // audit_notes must be in non-decreasing phase order.
    if let Some(i) = run.audit_notes.windows(2).position(|w| w[0] > w[1]) {
        return GateOutcome::fail(
            FailureCode::AuditNotesOutOfOrder,
            format!("audit_notes[{}]", i + 1),
        );
    }

    // PASSED requires final_coherence >= threshold.
    if run.status == Status::Passed && run.final_coherence < run.threshold {
        return GateOutcome::fail(FailureCode::PassedBelowThreshold, "final_coherence");
    }

    // REGENERATED requires at least one regen_event.
    if run.status == Status::Regenerated && run.regen_events.is_empty() {
        return GateOutcome::fail(FailureCode::RegenWithoutEvents, "regen_events");
    }

    GateOutcome::pass()
}
