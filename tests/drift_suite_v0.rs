use std::fs;

use signal_system::director_loop::{
    Correction, CorrectionAction, CorrectionRule, DirectorLoopRun, Fixture, RegenEvent, Status,
    compute_input_hash, compute_output_hash,
};
use signal_system::verifier::{AuditStatus, FailureCode, GateResult, verify, verify_bytes};

// ── Fixture loader ───────────────────────────────────────────────────────────

fn load() -> DirectorLoopRun {
    let raw = fs::read_to_string("fixtures/temporal_collapse_001/director_loop_run.json")
        .expect("golden fixture must exist");
    serde_json::from_str(&raw).expect("golden fixture must parse")
}

// ── Baseline sanity ──────────────────────────────────────────────────────────

#[test]
fn baseline_passes() {
    let r = verify(&load());
    assert_eq!(r.audit_status, AuditStatus::Pass);
    assert_eq!(r.gates.schema.result,      GateResult::Pass);
    assert_eq!(r.gates.invariants.result,  GateResult::Pass);
    assert_eq!(r.gates.input_hash.result,  GateResult::Pass);
    assert_eq!(r.gates.output_hash.result, GateResult::Pass);
}

// ── D-01: input hash drift ───────────────────────────────────────────────────

#[test]
fn d01_input_hash_drift() {
    let mut run = load();
    run.fixture = Fixture { fixture_id: "temporal_collapse_001_mutated".to_string() };
    let r = verify(&run);
    assert_eq!(r.audit_status,                        AuditStatus::Fail);
    assert_eq!(r.gates.schema.result,                 GateResult::Pass);
    assert_eq!(r.gates.invariants.result,             GateResult::Pass);
    assert_eq!(r.gates.input_hash.result,             GateResult::Fail);
    assert_eq!(r.gates.input_hash.failure_code,       Some(FailureCode::InputHashDrift));
    assert_eq!(r.gates.output_hash.result,            GateResult::NotEvaluated);
}

// ── D-02: output hash drift ──────────────────────────────────────────────────

#[test]
fn d02_output_hash_drift() {
    let mut run = load();
    run.final_coherence = run.final_coherence.saturating_add(1);
    let r = verify(&run);
    assert_eq!(r.audit_status,                        AuditStatus::Fail);
    assert_eq!(r.gates.invariants.result,             GateResult::Pass);
    assert_eq!(r.gates.input_hash.result,             GateResult::Pass);
    assert_eq!(r.gates.output_hash.result,            GateResult::Fail);
    assert_eq!(r.gates.output_hash.failure_code,      Some(FailureCode::OutputHashDrift));
}

// ── D-03: schema violation (extra root-level field) ──────────────────────────

#[test]
fn d03_schema_violation() {
    let raw = fs::read_to_string("fixtures/temporal_collapse_001/director_loop_run.json").unwrap();
    let mut val: serde_json::Value = serde_json::from_str(&raw).unwrap();
    val.as_object_mut()
        .unwrap()
        .insert("extra_field".into(), serde_json::Value::String("x".into()));
    let r = verify_bytes(&serde_json::to_vec(&val).unwrap());
    assert_eq!(r.audit_status,                        AuditStatus::Fail);
    assert_eq!(r.gates.schema.result,                 GateResult::Fail);
    assert_eq!(r.gates.schema.failure_code,           Some(FailureCode::SchemaViolation));
    assert_eq!(r.gates.invariants.result,             GateResult::NotEvaluated);
    assert_eq!(r.gates.input_hash.result,             GateResult::NotEvaluated);
    assert_eq!(r.gates.output_hash.result,            GateResult::NotEvaluated);
}

// ── D-04: corrections ordering violation ─────────────────────────────────────

#[test]
fn d04_corrections_out_of_order() {
    let mut run = load();
    run.corrections.reverse();
    let r = verify(&run);
    assert_eq!(r.audit_status,                        AuditStatus::Fail);
    assert_eq!(r.gates.invariants.result,             GateResult::Fail);
    assert_eq!(r.gates.invariants.failure_code,       Some(FailureCode::CorrectionsOutOfOrder));
    // Hash gates must not have run
    assert_eq!(r.gates.input_hash.result,             GateResult::NotEvaluated);
    assert_eq!(r.gates.output_hash.result,            GateResult::NotEvaluated);
}

// ── D-05: PASSED but final_coherence < threshold ─────────────────────────────

#[test]
fn d05_passed_below_threshold() {
    let mut run = load();
    run.status = Status::Passed;
    run.final_coherence = run.threshold.saturating_sub(1);
    // Recompute hashes to isolate the invariant check from hash drift.
    run.output_hash = compute_output_hash(&run);
    let r = verify(&run);
    assert_eq!(r.audit_status,                        AuditStatus::Fail);
    assert_eq!(r.gates.invariants.result,             GateResult::Fail);
    assert_eq!(r.gates.invariants.failure_code,       Some(FailureCode::PassedBelowThreshold));
    assert_eq!(r.gates.input_hash.result,             GateResult::NotEvaluated);
}

// ── D-05b: invariant fires before hash check regardless of hash validity ──────

#[test]
fn d05b_invariant_fires_before_hash() {
    let mut run = load();
    run.status = Status::Passed;
    run.final_coherence = run.threshold.saturating_sub(1);
    // Do NOT recompute hashes — both are stale.
    // Invariant gate must still fire first.
    let r = verify(&run);
    assert_eq!(r.gates.invariants.failure_code,  Some(FailureCode::PassedBelowThreshold));
    assert_eq!(r.gates.input_hash.result,        GateResult::NotEvaluated);
    assert_eq!(r.gates.output_hash.result,       GateResult::NotEvaluated);
}

// ── D-06: REGENERATED with empty regen_events ────────────────────────────────

#[test]
fn d06_regen_without_events() {
    let mut run = load();
    run.status = Status::Regenerated;
    run.regen_events = vec![];
    run.output_hash = compute_output_hash(&run);
    let r = verify(&run);
    assert_eq!(r.audit_status,                        AuditStatus::Fail);
    assert_eq!(r.gates.invariants.result,             GateResult::Fail);
    assert_eq!(r.gates.invariants.failure_code,       Some(FailureCode::RegenWithoutEvents));
    assert_eq!(r.gates.input_hash.result,             GateResult::NotEvaluated);
}

// ── D-07: canonicalization equivalence ───────────────────────────────────────

#[test]
fn d07_canonicalization_equivalence() {
    let base = load();
    let corrections = vec![
        Correction { rule: CorrectionRule::RhythmDrift, beat_id: "beat_001".into(), action: CorrectionAction::AdjustXfade },
        Correction { rule: CorrectionRule::AvAlignment, beat_id: "beat_003".into(), action: CorrectionAction::AdjustXfade },
    ];

    let mut a = base.clone();
    a.corrections = corrections.clone();
    a.input_hash  = compute_input_hash(&a);
    a.output_hash = compute_output_hash(&a);

    let mut b = base.clone();
    b.corrections = corrections;
    b.input_hash  = compute_input_hash(&b);
    b.output_hash = compute_output_hash(&b);

    assert_eq!(a.input_hash,  b.input_hash,  "input hashes must be identical");
    assert_eq!(a.output_hash, b.output_hash, "output hashes must be identical");
    assert_eq!(verify(&a).audit_status, AuditStatus::Pass);
    assert_eq!(verify(&b).audit_status, AuditStatus::Pass);
}

// ── D-08: audit_notes ordering violation ─────────────────────────────────────

#[test]
fn d08_audit_notes_out_of_order() {
    let mut run = load();
    run.audit_notes.reverse();
    let r = verify(&run);
    assert_eq!(r.audit_status,                        AuditStatus::Fail);
    assert_eq!(r.gates.invariants.result,             GateResult::Fail);
    assert_eq!(r.gates.invariants.failure_code,       Some(FailureCode::AuditNotesOutOfOrder));
    assert_eq!(r.gates.input_hash.result,             GateResult::NotEvaluated);
    assert_eq!(r.gates.output_hash.result,            GateResult::NotEvaluated);
}

// ── Regen with matching event passes ────────────────────────────────────────

#[test]
fn regen_with_event_passes() {
    let mut run = load();
    run.status = Status::Regenerated;
    run.regen_events = vec![RegenEvent { beat_id: "beat_002".into(), request_id: "req_abc".into() }];
    run.input_hash  = compute_input_hash(&run);
    run.output_hash = compute_output_hash(&run);
    assert_eq!(verify(&run).audit_status, AuditStatus::Pass);
}
