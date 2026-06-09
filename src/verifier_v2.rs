use serde::Serialize;

use crate::director_loop_v2::{DirectorLoopRunV2, RunStatus, compute_input_hash, compute_output_hash};

// ── Gate outcome types (V2 namespace — no shared types with V1) ──────────────

#[derive(Debug, Serialize, PartialEq)]
pub struct GateOutcomeV2 {
    pub result: GateResultV2,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub failure_code: Option<FailureCodeV2>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
}

#[derive(Debug, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum GateResultV2 {
    Pass,
    Fail,
    NotEvaluated,
}

/// One variant per root cause. Tests assert on these; CI reads them without
/// parsing free text.
#[derive(Debug, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum FailureCodeV2 {
    // schema gate
    SchemaViolation,
    // structural gate
    TimelineEmpty,
    TimelineNonMonotonic,
    TimelineStatusMismatch,
    CorrectionsOrphanedBeatId,
    AuditNotesOutOfOrder,
    AuditWarningsOutOfOrder,
    // state gate
    PassedBelowThreshold,
    PassedCoherenceRegressed,
    RegenWithoutEvents,
    // hash gates
    InputHashDrift,
    OutputHashDrift,
}

// ── Report ───────────────────────────────────────────────────────────────────

/// Gate results in pipeline order. Never reorder — field definition order is
/// the serialization order.
#[derive(Debug, Serialize)]
pub struct GateResultsV2 {
    pub schema:      GateOutcomeV2,
    pub structural:  GateOutcomeV2,
    pub state:       GateOutcomeV2,
    pub input_hash:  GateOutcomeV2,
    pub output_hash: GateOutcomeV2,
}

#[derive(Debug, Serialize, PartialEq)]
pub enum AuditStatusV2 {
    #[serde(rename = "PASS")] Pass,
    #[serde(rename = "FAIL")] Fail,
}

#[derive(Debug, Serialize)]
pub struct VerifierReportV2 {
    pub audit_status: AuditStatusV2,
    pub gates: GateResultsV2,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub failure_detail: Option<String>,
}

// ── Outcome constructors ─────────────────────────────────────────────────────

fn pass_v2() -> GateOutcomeV2 {
    GateOutcomeV2 { result: GateResultV2::Pass, failure_code: None, path: None }
}

fn fail_v2(code: FailureCodeV2, path: impl Into<String>) -> GateOutcomeV2 {
    GateOutcomeV2 { result: GateResultV2::Fail, failure_code: Some(code), path: Some(path.into()) }
}

fn not_evaluated_v2() -> GateOutcomeV2 {
    GateOutcomeV2 { result: GateResultV2::NotEvaluated, failure_code: None, path: None }
}

fn fail_at_schema_v2(detail: String) -> VerifierReportV2 {
    VerifierReportV2 {
        audit_status: AuditStatusV2::Fail,
        gates: GateResultsV2 {
            schema:      GateOutcomeV2 { result: GateResultV2::Fail, failure_code: Some(FailureCodeV2::SchemaViolation), path: None },
            structural:  not_evaluated_v2(),
            state:       not_evaluated_v2(),
            input_hash:  not_evaluated_v2(),
            output_hash: not_evaluated_v2(),
        },
        failure_detail: Some(detail),
    }
}

// ── Pipeline ─────────────────────────────────────────────────────────────────
// Order: schema → structural → state → input_hash → output_hash.
// Each gate returns on first failure; downstream gates are NotEvaluated.
// No repair, no normalization, no conditional logic inside projections.

pub fn verify_bytes_v2(bytes: &[u8]) -> VerifierReportV2 {
    match serde_json::from_slice::<DirectorLoopRunV2>(bytes) {
        Err(e) => fail_at_schema_v2(e.to_string()),
        Ok(run) => verify_v2(&run),
    }
}

pub fn verify_v2(run: &DirectorLoopRunV2) -> VerifierReportV2 {
    // Gate 2: structural
    let structural = gate_structural(run);
    if structural.result == GateResultV2::Fail {
        return VerifierReportV2 {
            audit_status: AuditStatusV2::Fail,
            gates: GateResultsV2 {
                schema: pass_v2(), structural,
                state: not_evaluated_v2(),
                input_hash: not_evaluated_v2(),
                output_hash: not_evaluated_v2(),
            },
            failure_detail: None,
        };
    }

    // Gate 3: state
    let state = gate_state(run);
    if state.result == GateResultV2::Fail {
        return VerifierReportV2 {
            audit_status: AuditStatusV2::Fail,
            gates: GateResultsV2 {
                schema: pass_v2(), structural, state,
                input_hash: not_evaluated_v2(),
                output_hash: not_evaluated_v2(),
            },
            failure_detail: None,
        };
    }

    // Gate 4: input_hash
    let expected_input = compute_input_hash(run);
    if run.input_hash != expected_input {
        return VerifierReportV2 {
            audit_status: AuditStatusV2::Fail,
            gates: GateResultsV2 {
                schema: pass_v2(), structural, state,
                input_hash: fail_v2(FailureCodeV2::InputHashDrift, "input_hash"),
                output_hash: not_evaluated_v2(),
            },
            failure_detail: Some(format!(
                "input_hash: artifact={} computed={}", run.input_hash, expected_input
            )),
        };
    }

    // Gate 5: output_hash
    let expected_output = compute_output_hash(run);
    if run.output_hash != expected_output {
        return VerifierReportV2 {
            audit_status: AuditStatusV2::Fail,
            gates: GateResultsV2 {
                schema: pass_v2(), structural, state,
                input_hash: pass_v2(),
                output_hash: fail_v2(FailureCodeV2::OutputHashDrift, "output_hash"),
            },
            failure_detail: Some(format!(
                "output_hash: artifact={} computed={}", run.output_hash, expected_output
            )),
        };
    }

    VerifierReportV2 {
        audit_status: AuditStatusV2::Pass,
        gates: GateResultsV2 {
            schema: pass_v2(), structural, state,
            input_hash: pass_v2(), output_hash: pass_v2(),
        },
        failure_detail: None,
    }
}

// ── Gate 2: structural ───────────────────────────────────────────────────────

fn gate_structural(run: &DirectorLoopRunV2) -> GateOutcomeV2 {
    let tl = &run.execution.timeline;

    if tl.is_empty() {
        return fail_v2(FailureCodeV2::TimelineEmpty, "execution.timeline");
    }

    // Steps must be 0-based and contiguous: timeline[i].step == i
    for (i, step) in tl.iter().enumerate() {
        if step.step != i as u32 {
            return fail_v2(
                FailureCodeV2::TimelineNonMonotonic,
                format!("execution.timeline[{i}].step"),
            );
        }
    }

    // Terminal state in timeline must match execution.status
    if tl.last().unwrap().state != run.execution.status {
        return fail_v2(FailureCodeV2::TimelineStatusMismatch, "execution.timeline");
    }

    // Every correction.beat_id must appear in transitions or regen_events.
    // Uses a sorted Vec instead of HashSet to avoid unordered iteration.
    let mut anchored: Vec<&str> = run.execution.transitions.iter()
        .map(|t| t.beat_id.as_str())
        .chain(run.execution.regen_events.iter().map(|r| r.beat_id.as_str()))
        .collect();
    anchored.sort_unstable();

    for (i, correction) in run.execution.corrections.iter().enumerate() {
        if anchored.binary_search(&correction.beat_id.as_str()).is_err() {
            return fail_v2(
                FailureCodeV2::CorrectionsOrphanedBeatId,
                format!("execution.corrections[{i}].beat_id"),
            );
        }
    }

    // audit.notes must be in non-decreasing order (append-only invariant)
    if let Some(i) = run.audit.notes.windows(2).position(|w| w[0] > w[1]) {
        return fail_v2(FailureCodeV2::AuditNotesOutOfOrder, format!("audit.notes[{}]", i + 1));
    }

    if let Some(i) = run.audit.warnings.windows(2).position(|w| w[0] > w[1]) {
        return fail_v2(FailureCodeV2::AuditWarningsOutOfOrder, format!("audit.warnings[{}]", i + 1));
    }

    pass_v2()
}

// ── Gate 3: state ────────────────────────────────────────────────────────────

fn gate_state(run: &DirectorLoopRunV2) -> GateOutcomeV2 {
    let ex = &run.execution;

    // PASSED requires final_coherence >= threshold
    if ex.status == RunStatus::Passed && ex.final_coherence < run.inputs.threshold {
        return fail_v2(FailureCodeV2::PassedBelowThreshold, "execution.final_coherence");
    }

    // PASSED requires final_coherence >= initial_coherence (monotonicity)
    if ex.status == RunStatus::Passed && ex.final_coherence < ex.initial_coherence {
        return fail_v2(FailureCodeV2::PassedCoherenceRegressed, "execution.final_coherence");
    }

    // REGENERATED (terminal) requires at least one regen_event
    if ex.status == RunStatus::Regenerated && ex.regen_events.is_empty() {
        return fail_v2(FailureCodeV2::RegenWithoutEvents, "execution.regen_events");
    }

    // regen_events present requires REGENERATED to appear somewhere in timeline
    if !ex.regen_events.is_empty() {
        let has_regen = ex.timeline.iter().any(|s| s.state == RunStatus::Regenerated);
        if !has_regen {
            return fail_v2(FailureCodeV2::RegenWithoutEvents, "execution.timeline");
        }
    }

    pass_v2()
}
