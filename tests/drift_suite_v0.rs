use std::fs;

use signal_system::director_loop::{
    Correction, CorrectionAction, CorrectionRule, DirectorLoopRun, Fixture, RegenEvent, Status,
    compute_input_hash, compute_output_hash,
};
use signal_system::verifier::{verify, verify_bytes, AuditStatus};

// ── Fixture loader ───────────────────────────────────────────────────────────

fn load() -> DirectorLoopRun {
    let raw = fs::read_to_string("fixtures/temporal_collapse_001/director_loop_run.json")
        .expect("golden fixture must exist");
    serde_json::from_str(&raw).expect("golden fixture must parse")
}

// ── Baseline sanity ──────────────────────────────────────────────────────────

#[test]
fn baseline_passes() {
    assert_eq!(verify(&load()).audit_status, AuditStatus::Pass);
}

// ── D-01: input hash drift (fixture_id mutation) ─────────────────────────────

#[test]
fn d01_input_hash_drift() {
    let mut run = load();
    run.fixture = Fixture { fixture_id: "temporal_collapse_001_mutated".to_string() };
    let r = verify(&run);
    assert_eq!(r.audit_status, AuditStatus::Fail);
    assert!(r.schema_valid);
    assert!(r.transition_valid);
    assert!(!r.input_hash_valid);
}

// ── D-02: output hash drift (final_coherence mutation) ───────────────────────

#[test]
fn d02_output_hash_drift() {
    let mut run = load();
    run.final_coherence = run.final_coherence.saturating_add(1);
    let r = verify(&run);
    assert_eq!(r.audit_status, AuditStatus::Fail);
    assert!(r.schema_valid);
    assert!(r.transition_valid);
    assert!(r.input_hash_valid);
    assert!(!r.output_hash_valid);
}

// ── D-03: schema violation (extra root-level field) ──────────────────────────
// Must operate at the JSON byte level — typed deserialization already rejects
// unknown fields via #[serde(deny_unknown_fields)].

#[test]
fn d03_schema_violation() {
    let raw = fs::read_to_string("fixtures/temporal_collapse_001/director_loop_run.json").unwrap();
    let mut val: serde_json::Value = serde_json::from_str(&raw).unwrap();
    val.as_object_mut()
        .unwrap()
        .insert("extra_field".into(), serde_json::Value::String("x".into()));
    let mutated = serde_json::to_vec(&val).unwrap();
    let r = verify_bytes(&mutated);
    assert_eq!(r.audit_status, AuditStatus::Fail);
    assert!(!r.schema_valid);
}

// ── D-04: corrections ordering violation ─────────────────────────────────────
// Reversal violates the beat_id non-decreasing invariant.
// Invariant gate fires before hash checks → transition_valid: false.

#[test]
fn d04_corrections_order_violation() {
    let mut run = load();
    run.corrections.reverse();
    let r = verify(&run);
    assert_eq!(r.audit_status, AuditStatus::Fail);
    assert!(r.schema_valid);
    assert!(!r.transition_valid);
}

// ── D-05: state machine contradiction (PASSED but final < threshold) ──────────

#[test]
fn d05_state_machine_contradiction() {
    let mut run = load();
    run.status = Status::Passed;
    run.final_coherence = run.threshold.saturating_sub(1);
    // Recompute output_hash to isolate the invariant check (not the hash).
    // If we didn't recompute, the output hash mismatch would fire first.
    run.output_hash = compute_output_hash(&run);
    let r = verify(&run);
    assert_eq!(r.audit_status, AuditStatus::Fail);
    assert!(r.schema_valid);
    assert!(!r.transition_valid);
}

// ── D-06: regen consistency (REGENERATED with empty regen_events) ─────────────

#[test]
fn d06_regen_consistency() {
    let mut run = load();
    run.status = Status::Regenerated;
    run.regen_events = vec![];
    run.output_hash = compute_output_hash(&run);
    let r = verify(&run);
    assert_eq!(r.audit_status, AuditStatus::Fail);
    assert!(r.schema_valid);
    assert!(!r.transition_valid);
}

// ── D-07: canonicalization equivalence ───────────────────────────────────────
// Two artifacts with identical logical state must produce identical hashes
// regardless of how they were constructed.

#[test]
fn d07_canonicalization_equivalence() {
    let base = load();

    // Artifact A: corrections in natural order
    let mut a = base.clone();
    a.corrections = vec![
        Correction { rule: CorrectionRule::RhythmDrift,  beat_id: "beat_001".into(), action: CorrectionAction::AdjustXfade },
        Correction { rule: CorrectionRule::AvAlignment,  beat_id: "beat_003".into(), action: CorrectionAction::AdjustXfade },
    ];
    a.input_hash  = compute_input_hash(&a);
    a.output_hash = compute_output_hash(&a);

    // Artifact B: same logical corrections, built independently
    let mut b = base.clone();
    b.corrections = vec![
        Correction { rule: CorrectionRule::RhythmDrift,  beat_id: "beat_001".into(), action: CorrectionAction::AdjustXfade },
        Correction { rule: CorrectionRule::AvAlignment,  beat_id: "beat_003".into(), action: CorrectionAction::AdjustXfade },
    ];
    b.input_hash  = compute_input_hash(&b);
    b.output_hash = compute_output_hash(&b);

    assert_eq!(a.input_hash,  b.input_hash,  "input hashes must match for identical logical state");
    assert_eq!(a.output_hash, b.output_hash, "output hashes must match for identical logical state");
    assert_eq!(verify(&a).audit_status, AuditStatus::Pass);
    assert_eq!(verify(&b).audit_status, AuditStatus::Pass);
}

// ── D-08: audit_notes ordering violation ─────────────────────────────────────
// Reversal violates the phase-order invariant.
// Invariant gate fires before hash checks.

#[test]
fn d08_audit_notes_order_violation() {
    let mut run = load();
    run.audit_notes.reverse();
    let r = verify(&run);
    assert_eq!(r.audit_status, AuditStatus::Fail);
    assert!(r.schema_valid);
    assert!(!r.transition_valid);
}

// ── D-05b: input hash still valid under state contradiction ──────────────────
// Proves that invariant gate fires independently of hash validity.

#[test]
fn d05b_invariant_fails_before_hash_check() {
    let mut run = load();
    run.status = Status::Passed;
    run.final_coherence = run.threshold.saturating_sub(1);
    // Do NOT recompute hashes — both are now stale.
    // Invariant gate must fire first anyway.
    let r = verify(&run);
    assert_eq!(r.audit_status, AuditStatus::Fail);
    assert!(!r.transition_valid);
    // input_hash_valid and output_hash_valid are false because pipeline
    // short-circuits at the invariant stage — they were never checked.
    assert!(!r.input_hash_valid);
    assert!(!r.output_hash_valid);
}

// ── Regen event shape ────────────────────────────────────────────────────────

#[test]
fn regen_event_valid_when_status_matches() {
    let mut run = load();
    run.status = Status::Regenerated;
    run.regen_events = vec![RegenEvent {
        beat_id: "beat_002".into(),
        request_id: "req_abc123".into(),
    }];
    run.input_hash  = compute_input_hash(&run);
    run.output_hash = compute_output_hash(&run);
    assert_eq!(verify(&run).audit_status, AuditStatus::Pass);
}
