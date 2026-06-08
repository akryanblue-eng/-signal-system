use vdce::canonical::canonical_bytes;
use vdce::certify::certify;
use vdce::kernel::replay;
use vdce::types::VdceError;

// ── Helpers ───────────────────────────────────────────────────────────────────

fn golden_bytes() -> &'static [u8] {
    include_bytes!("../fixtures/golden/golden_trace_v1_1.json")
}

fn trace_json(steps_json: &str) -> Vec<u8> {
    format!(
        r#"{{"schema_version":1,"reducer_version":"1.1","steps":[{steps_json}]}}"#
    )
    .into_bytes()
}

// ── Golden trace ──────────────────────────────────────────────────────────────

#[test]
fn golden_trace_v1_1_replays_ok() {
    let ok = replay(golden_bytes()).expect("golden trace must replay without error");
    assert_eq!(ok.steps_replayed, 3);
}

#[test]
fn golden_trace_v1_1_certifies_ok() {
    let ok = replay(golden_bytes()).unwrap();
    let cert = certify(&ok).expect("golden trace must certify without error");
    assert_eq!(cert.status, "ok");
    assert_eq!(cert.steps_replayed, 3);
    assert!(cert.certificate_hash.is_some());
    let hash = cert.certificate_hash.as_deref().unwrap();
    assert_eq!(hash.len(), 64, "SHA-256 hex must be 64 chars");
}

// ── Empty trace (Option A: valid, steps=0) ────────────────────────────────────

#[test]
fn empty_trace_is_valid() {
    let bytes = trace_json("");
    let ok = replay(&bytes).expect("empty trace must be valid (Option A)");
    assert_eq!(ok.steps_replayed, 0);
}

#[test]
fn empty_trace_certificate_is_deterministic() {
    let bytes = trace_json("");
    let ok1 = replay(&bytes).unwrap();
    let ok2 = replay(&bytes).unwrap();
    let cert1 = certify(&ok1).unwrap();
    let cert2 = certify(&ok2).unwrap();
    let b1 = canonical_bytes(&cert1).unwrap();
    let b2 = canonical_bytes(&cert2).unwrap();
    assert_eq!(b1, b2, "empty trace certificate must be byte-identical across runs");
}

// ── Determinism gate ──────────────────────────────────────────────────────────

#[test]
fn certificate_is_byte_identical_across_runs() {
    let ok1 = replay(golden_bytes()).unwrap();
    let ok2 = replay(golden_bytes()).unwrap();
    let cert1 = certify(&ok1).unwrap();
    let cert2 = certify(&ok2).unwrap();
    let b1 = canonical_bytes(&cert1).unwrap();
    let b2 = canonical_bytes(&cert2).unwrap();
    assert_eq!(b1, b2, "certificate bytes must be identical across runs");
}

#[test]
fn certificate_hash_is_over_null_preimage() {
    let ok = replay(golden_bytes()).unwrap();
    let cert = certify(&ok).unwrap();
    // Recompute expected hash independently.
    use sha2::{Digest, Sha256};
    use vdce::certify::Certificate;
    use vdce::types::{SUPPORTED_REDUCER_VERSION, SUPPORTED_SCHEMA_VERSION};
    let preimage = Certificate {
        certificate_hash: None,
        reducer_version: SUPPORTED_REDUCER_VERSION.to_string(),
        schema_version: SUPPORTED_SCHEMA_VERSION,
        status: "ok".to_string(),
        steps_replayed: ok.steps_replayed,
    };
    let expected_hash = hex::encode(Sha256::digest(canonical_bytes(&preimage).unwrap()));
    assert_eq!(cert.certificate_hash.as_deref().unwrap(), expected_hash);
}

// ── Decode / Schema Gate failures ─────────────────────────────────────────────

#[test]
fn bad_json_is_schema_error() {
    let err = replay(b"not json at all").unwrap_err();
    assert!(
        matches!(err, VdceError::SchemaOrDecode(_)),
        "bad JSON must produce SchemaOrDecode, got: {err}"
    );
}

#[test]
fn wrong_schema_version_is_schema_error() {
    let bytes = br#"{"schema_version":99,"reducer_version":"1.1","steps":[]}"#;
    let err = replay(bytes).unwrap_err();
    assert!(matches!(err, VdceError::SchemaOrDecode(_)));
}

#[test]
fn wrong_reducer_version_is_schema_error() {
    let bytes = br#"{"schema_version":1,"reducer_version":"9.9","steps":[]}"#;
    let err = replay(bytes).unwrap_err();
    assert!(matches!(err, VdceError::SchemaOrDecode(_)));
}

// ── Row 5a: continuity failures ───────────────────────────────────────────────

#[test]
fn non_sequential_step_ids_fail_continuity() {
    let bytes = trace_json(
        r#"{"step_id":0,"operation":"identity","inputs":{"v":1},"expected_output":{"v":1}},
           {"step_id":2,"operation":"identity","inputs":{"v":2},"expected_output":{"v":2}}"#,
    );
    let err = replay(&bytes).unwrap_err();
    assert!(
        matches!(err, VdceError::TraceInvariantViolation(_)),
        "gap in step_ids must produce TraceInvariantViolation, got: {err}"
    );
}

#[test]
fn step_id_not_starting_at_zero_fails_continuity() {
    let bytes = trace_json(
        r#"{"step_id":1,"operation":"identity","inputs":{"v":1},"expected_output":{"v":1}}"#,
    );
    let err = replay(&bytes).unwrap_err();
    assert!(matches!(err, VdceError::TraceInvariantViolation(_)));
}

// ── Row 4: closed-world failures ──────────────────────────────────────────────

#[test]
fn unknown_operation_fails_closed_world() {
    let bytes = trace_json(
        r#"{"step_id":0,"operation":"teleport","inputs":{},"expected_output":{}}"#,
    );
    let err = replay(&bytes).unwrap_err();
    assert!(
        matches!(err, VdceError::ClosedWorldViolation { .. }),
        "unknown operation must produce ClosedWorldViolation, got: {err}"
    );
}

#[test]
fn unknown_nondet_guard_fails_closed_world() {
    let bytes = trace_json(
        r#"{"step_id":0,"operation":"identity","inputs":{"v":1},"expected_output":{"v":1},
            "nondet_guards":[{"name":"undeclared_oracle","value":42}]}"#,
    );
    let err = replay(&bytes).unwrap_err();
    assert!(matches!(err, VdceError::ClosedWorldViolation { .. }));
}

#[test]
fn add_with_missing_inputs_fails_closed_world() {
    let bytes = trace_json(
        r#"{"step_id":0,"operation":"add","inputs":{"a":1},"expected_output":{"result":1}}"#,
    );
    let err = replay(&bytes).unwrap_err();
    assert!(matches!(err, VdceError::ClosedWorldViolation { .. }));
}

// ── Row 5: semantic mismatch failures ─────────────────────────────────────────

#[test]
fn wrong_expected_output_fails_semantic() {
    let bytes = trace_json(
        r#"{"step_id":0,"operation":"add","inputs":{"a":1,"b":2},"expected_output":{"result":99}}"#,
    );
    let err = replay(&bytes).unwrap_err();
    assert!(
        matches!(err, VdceError::SemanticMismatch { step_id: 0, .. }),
        "wrong expected_output must produce SemanticMismatch, got: {err}"
    );
}

// ── Row ordering: 5a runs before Row 4 ───────────────────────────────────────

#[test]
fn continuity_failure_takes_precedence_over_closed_world() {
    // step_id gap + unknown operation: Row 5a must fire first.
    let bytes = trace_json(
        r#"{"step_id":0,"operation":"teleport","inputs":{},"expected_output":{}},
           {"step_id":5,"operation":"teleport","inputs":{},"expected_output":{}}"#,
    );
    let err = replay(&bytes).unwrap_err();
    assert!(
        matches!(err, VdceError::TraceInvariantViolation(_)),
        "Row 5a must fire before Row 4; got: {err}"
    );
}
