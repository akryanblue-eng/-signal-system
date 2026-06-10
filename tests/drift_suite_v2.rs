use std::fs;

use signal_system::director_loop_v2::{
    compute_input_hash, compute_output_hash, CorrectionActionV2, CorrectionRuleV2, CorrectionV2,
    RegenEventV2, RegenTrigger, RunStatus,
};
use signal_system::verifier_v2::{
    verify_bytes_v2, verify_v2, AuditStatusV2, FailureCodeV2, GateResultV2,
};

// ── Fixture loader ───────────────────────────────────────────────────────────

fn load_v2() -> signal_system::director_loop_v2::DirectorLoopRunV2 {
    let raw = fs::read_to_string("fixtures/v2/temporal_collapse_001/director_loop_run_v2.json")
        .expect("V2 golden fixture must exist");
    serde_json::from_str(&raw).expect("V2 golden fixture must parse")
}

// ── Baseline ─────────────────────────────────────────────────────────────────

#[test]
fn baseline_v2_passes() {
    let r = verify_v2(&load_v2());
    assert_eq!(r.audit_status, AuditStatusV2::Pass);
    assert_eq!(r.gates.schema.result, GateResultV2::Pass);
    assert_eq!(r.gates.structural.result, GateResultV2::Pass);
    assert_eq!(r.gates.state.result, GateResultV2::Pass);
    assert_eq!(r.gates.input_hash.result, GateResultV2::Pass);
    assert_eq!(r.gates.output_hash.result, GateResultV2::Pass);
}

// ── D-01: input hash drift ───────────────────────────────────────────────────

#[test]
fn v2_d01_input_hash_drift() {
    let mut run = load_v2();
    run.inputs.fixture.fixture_id = "temporal_collapse_001_mutated".to_string();
    let r = verify_v2(&run);
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.structural.result, GateResultV2::Pass);
    assert_eq!(r.gates.state.result, GateResultV2::Pass);
    assert_eq!(r.gates.input_hash.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.input_hash.failure_code,
        Some(FailureCodeV2::InputHashDrift)
    );
    assert_eq!(r.gates.output_hash.result, GateResultV2::NotEvaluated);
}

// ── D-02: output hash drift ──────────────────────────────────────────────────

#[test]
fn v2_d02_output_hash_drift() {
    let mut run = load_v2();
    run.execution.final_coherence = run.execution.final_coherence.saturating_add(1);
    let r = verify_v2(&run);
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.structural.result, GateResultV2::Pass);
    assert_eq!(r.gates.state.result, GateResultV2::Pass);
    assert_eq!(r.gates.input_hash.result, GateResultV2::Pass);
    assert_eq!(r.gates.output_hash.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.output_hash.failure_code,
        Some(FailureCodeV2::OutputHashDrift)
    );
}

// ── D-03: schema violation (unknown root-level field) ────────────────────────

#[test]
fn v2_d03_schema_violation() {
    let raw =
        fs::read_to_string("fixtures/v2/temporal_collapse_001/director_loop_run_v2.json").unwrap();
    let mut val: serde_json::Value = serde_json::from_str(&raw).unwrap();
    val.as_object_mut().unwrap().insert(
        "unknown_field".into(),
        serde_json::Value::String("x".into()),
    );
    let r = verify_bytes_v2(&serde_json::to_vec(&val).unwrap());
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.schema.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.schema.failure_code,
        Some(FailureCodeV2::SchemaViolation)
    );
    assert_eq!(r.gates.structural.result, GateResultV2::NotEvaluated);
    assert_eq!(r.gates.state.result, GateResultV2::NotEvaluated);
    assert_eq!(r.gates.input_hash.result, GateResultV2::NotEvaluated);
    assert_eq!(r.gates.output_hash.result, GateResultV2::NotEvaluated);
}

// ── D-04: timeline empty ─────────────────────────────────────────────────────

#[test]
fn v2_d04_timeline_empty() {
    let mut run = load_v2();
    run.execution.timeline = vec![];
    let r = verify_v2(&run);
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.structural.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.structural.failure_code,
        Some(FailureCodeV2::TimelineEmpty)
    );
    assert_eq!(r.gates.state.result, GateResultV2::NotEvaluated);
    assert_eq!(r.gates.input_hash.result, GateResultV2::NotEvaluated);
    assert_eq!(r.gates.output_hash.result, GateResultV2::NotEvaluated);
}

// ── D-05: timeline step index non-monotonic ──────────────────────────────────

#[test]
fn v2_d05_timeline_non_monotonic() {
    let mut run = load_v2();
    run.execution.timeline[1].step = 99;
    let r = verify_v2(&run);
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.structural.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.structural.failure_code,
        Some(FailureCodeV2::TimelineNonMonotonic)
    );
    assert_eq!(r.gates.state.result, GateResultV2::NotEvaluated);
    assert_eq!(r.gates.input_hash.result, GateResultV2::NotEvaluated);
}

// ── D-06: terminal timeline state ≠ execution.status ─────────────────────────

#[test]
fn v2_d06_timeline_status_mismatch() {
    let mut run = load_v2();
    if let Some(last) = run.execution.timeline.last_mut() {
        last.state = RunStatus::Failed;
    }
    let r = verify_v2(&run);
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.structural.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.structural.failure_code,
        Some(FailureCodeV2::TimelineStatusMismatch)
    );
    assert_eq!(r.gates.state.result, GateResultV2::NotEvaluated);
    assert_eq!(r.gates.input_hash.result, GateResultV2::NotEvaluated);
}

// ── D-07: correction beat_id not anchored in transitions or regen_events ──────

#[test]
fn v2_d07_corrections_orphaned_beat_id() {
    let mut run = load_v2();
    run.execution.corrections.push(CorrectionV2 {
        beat_id: "beat_ghost".to_string(),
        rule: CorrectionRuleV2::RhythmDrift,
        action: CorrectionActionV2::AdjustXfade,
    });
    let r = verify_v2(&run);
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.structural.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.structural.failure_code,
        Some(FailureCodeV2::CorrectionsOrphanedBeatId)
    );
    assert_eq!(r.gates.state.result, GateResultV2::NotEvaluated);
    assert_eq!(r.gates.input_hash.result, GateResultV2::NotEvaluated);
}

// ── D-08: audit notes out of order ───────────────────────────────────────────

#[test]
fn v2_d08_audit_notes_out_of_order() {
    let mut run = load_v2();
    run.audit.notes.reverse();
    let r = verify_v2(&run);
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.structural.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.structural.failure_code,
        Some(FailureCodeV2::AuditNotesOutOfOrder)
    );
    assert_eq!(r.gates.input_hash.result, GateResultV2::NotEvaluated);
    assert_eq!(r.gates.output_hash.result, GateResultV2::NotEvaluated);
}

// ── D-09: audit warnings out of order ────────────────────────────────────────

#[test]
fn v2_d09_audit_warnings_out_of_order() {
    let mut run = load_v2();
    run.audit.warnings = vec!["WARN_Z: late".to_string(), "WARN_A: early".to_string()];
    let r = verify_v2(&run);
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.structural.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.structural.failure_code,
        Some(FailureCodeV2::AuditWarningsOutOfOrder)
    );
    assert_eq!(r.gates.input_hash.result, GateResultV2::NotEvaluated);
    assert_eq!(r.gates.output_hash.result, GateResultV2::NotEvaluated);
}

// ── D-10: PASSED with final_coherence < threshold ────────────────────────────

#[test]
fn v2_d10_passed_below_threshold() {
    let mut run = load_v2();
    run.execution.final_coherence = run.inputs.threshold.saturating_sub(1);
    run.output_hash = compute_output_hash(&run);
    let r = verify_v2(&run);
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.structural.result, GateResultV2::Pass);
    assert_eq!(r.gates.state.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.state.failure_code,
        Some(FailureCodeV2::PassedBelowThreshold)
    );
    assert_eq!(r.gates.input_hash.result, GateResultV2::NotEvaluated);
    assert_eq!(r.gates.output_hash.result, GateResultV2::NotEvaluated);
}

// ── D-11: PASSED with final_coherence < initial_coherence ────────────────────

#[test]
fn v2_d11_passed_coherence_regressed() {
    let mut run = load_v2();
    // final below initial but still above threshold → PassedBelowThreshold does not fire first
    run.execution.final_coherence = run.execution.initial_coherence.saturating_sub(1);
    run.output_hash = compute_output_hash(&run);
    let r = verify_v2(&run);
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.state.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.state.failure_code,
        Some(FailureCodeV2::PassedCoherenceRegressed)
    );
    assert_eq!(r.gates.input_hash.result, GateResultV2::NotEvaluated);
}

// ── D-12: REGENERATED status with no regen_events ────────────────────────────

#[test]
fn v2_d12_regen_without_events() {
    let mut run = load_v2();
    run.execution.status = RunStatus::Regenerated;
    // Align terminal timeline state so structural passes
    if let Some(last) = run.execution.timeline.last_mut() {
        last.state = RunStatus::Regenerated;
    }
    run.execution.regen_events = vec![];
    run.output_hash = compute_output_hash(&run);
    let r = verify_v2(&run);
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.structural.result, GateResultV2::Pass);
    assert_eq!(r.gates.state.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.state.failure_code,
        Some(FailureCodeV2::RegenWithoutEvents)
    );
    assert_eq!(
        r.gates.state.path.as_deref(),
        Some("execution.regen_events")
    );
    assert_eq!(r.gates.input_hash.result, GateResultV2::NotEvaluated);
}

// ── D-13: regen_events present but REGENERATED absent from timeline ───────────

#[test]
fn v2_d13_regen_events_without_timeline_regen() {
    let mut run = load_v2();
    run.execution.regen_events.push(RegenEventV2 {
        beat_id: "beat_001".to_string(),
        trigger: RegenTrigger::StateViolation,
        request_id: "req_abc".to_string(),
    });
    // timeline stays all-PASSED → REGENERATED never appears
    run.output_hash = compute_output_hash(&run);
    let r = verify_v2(&run);
    assert_eq!(r.audit_status, AuditStatusV2::Fail);
    assert_eq!(r.gates.structural.result, GateResultV2::Pass);
    assert_eq!(r.gates.state.result, GateResultV2::Fail);
    assert_eq!(
        r.gates.state.failure_code,
        Some(FailureCodeV2::RegenWithoutEvents)
    );
    assert_eq!(r.gates.state.path.as_deref(), Some("execution.timeline"));
    assert_eq!(r.gates.input_hash.result, GateResultV2::NotEvaluated);
}

// ── Gate ordering proofs ─────────────────────────────────────────────────────

#[test]
fn v2_structural_fires_before_state() {
    let mut run = load_v2();
    run.execution.timeline = vec![];
    run.execution.final_coherence = run.inputs.threshold.saturating_sub(1);
    let r = verify_v2(&run);
    assert_eq!(
        r.gates.structural.failure_code,
        Some(FailureCodeV2::TimelineEmpty)
    );
    assert_eq!(r.gates.state.result, GateResultV2::NotEvaluated);
}

#[test]
fn v2_state_fires_before_hash() {
    let mut run = load_v2();
    run.execution.final_coherence = run.inputs.threshold.saturating_sub(1);
    // Hashes are now stale — state gate must fire before they are checked
    let r = verify_v2(&run);
    assert_eq!(
        r.gates.state.failure_code,
        Some(FailureCodeV2::PassedBelowThreshold)
    );
    assert_eq!(r.gates.input_hash.result, GateResultV2::NotEvaluated);
    assert_eq!(r.gates.output_hash.result, GateResultV2::NotEvaluated);
}

// ── Anchored corrections pass when beat_id is in regen_events ────────────────

#[test]
fn v2_correction_anchored_by_regen_event_passes() {
    let mut run = load_v2();
    run.execution.regen_events.push(RegenEventV2 {
        beat_id: "beat_anchor".to_string(),
        trigger: RegenTrigger::HashMismatch,
        request_id: "req_001".to_string(),
    });
    run.execution.corrections.push(CorrectionV2 {
        beat_id: "beat_anchor".to_string(),
        rule: CorrectionRuleV2::MotionStrength,
        action: CorrectionActionV2::RegenBeat,
    });
    // Keep execution.status = PASSED but fix timeline terminal state and add
    // REGENERATED step so the state gate's regen-in-timeline check passes.
    run.execution
        .timeline
        .push(signal_system::director_loop_v2::TimelineStep {
            step: 3,
            event: signal_system::director_loop_v2::TimelineEvent::RegenApply,
            state: RunStatus::Regenerated,
            beat_id: Some("beat_anchor".to_string()),
        });
    // Terminal step is now Regenerated; align execution.status
    run.execution.status = RunStatus::Regenerated;
    run.input_hash = compute_input_hash(&run);
    run.output_hash = compute_output_hash(&run);
    assert_eq!(verify_v2(&run).audit_status, AuditStatusV2::Pass);
}
