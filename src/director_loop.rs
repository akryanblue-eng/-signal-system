use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// Coherence in fixed-point millionths (0..=1_000_000 = 0.0..=1.0).
/// Avoids float serialization variance per VDCE v1.1 canonicalization rules.
pub type CoherenceValue = u32;

// ── Domain structs (field order is part of the frozen canonical contract) ───

#[derive(Debug, Serialize, Deserialize)]
pub struct DirectorLoopRun {
    // input domain
    pub director_loop_version: String,
    pub fixture: Fixture,
    pub config: Config,
    pub threshold: CoherenceValue,
    pub ruleset_version: String,
    // output domain
    pub status: Status,
    pub initial_coherence: CoherenceValue,
    pub final_coherence: CoherenceValue,
    pub corrections: Vec<Correction>,
    pub regen_events: Vec<RegenEvent>,
    pub audit_notes: String,
    // integrity boundary
    pub input_hash: String,
    pub output_hash: String,
}

/// Extend with fixture-specific fields before freezing for a given fixture set.
/// All fields are included verbatim in the input_hash preimage.
#[derive(Debug, Serialize, Deserialize)]
pub struct Fixture {
    pub fixture_id: String,
}

/// Extend with config-specific fields before freezing for a given run set.
/// All fields are included verbatim in the input_hash preimage.
#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    pub max_corrections: u32,
    pub regen_budget: u32,
}

#[derive(Debug, Serialize, Deserialize)]
pub enum Status {
    #[serde(rename = "PASSED")]
    Passed,
    #[serde(rename = "REGENERATED")]
    Regenerated,
    #[serde(rename = "FAILED")]
    Failed,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Correction {
    pub rule: CorrectionRule,
    pub beat_id: String,
    pub action: CorrectionAction,
}

#[derive(Debug, Serialize, Deserialize)]
pub enum CorrectionRule {
    #[serde(rename = "RHYTHM_DRIFT")]
    RhythmDrift,
    #[serde(rename = "MOTION_STRENGTH")]
    MotionStrength,
    #[serde(rename = "AV_ALIGNMENT")]
    AvAlignment,
}

#[derive(Debug, Serialize, Deserialize)]
pub enum CorrectionAction {
    #[serde(rename = "adjust_xfade")]
    AdjustXfade,
    #[serde(rename = "regen_beat")]
    RegenBeat,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct RegenEvent {
    pub beat_id: String,
    pub request_id: String,
}

// ── Preimage structs ────────────────────────────────────────────────────────
// Field order here is frozen. Never reorder — serde serializes in definition
// order, and any reorder silently changes every hash in the corpus.

#[derive(Serialize)]
struct InputHashPreimage<'a> {
    director_loop_version: &'a str,
    threshold: CoherenceValue,
    ruleset_version: &'a str,
    fixture: &'a Fixture,
    config: &'a Config,
}

#[derive(Serialize)]
struct OutputHashPreimage<'a> {
    status: &'a Status,
    initial_coherence: CoherenceValue,
    final_coherence: CoherenceValue,
    corrections: &'a [Correction],
    regen_events: &'a [RegenEvent],
    audit_notes: &'a str,
}

// ── Hash computation ────────────────────────────────────────────────────────

/// Canonical bytes: compact (non-pretty) JSON via serde_json::to_vec over a
/// serde-derived typed struct. Field order is struct definition order, which
/// serde derive guarantees — no HashMap, no serde_json::Value in the hash
/// boundary. This achieves deterministic encoding without requiring RFC 8785
/// JCS; the two are equivalent only because all hash-boundary types are fully
/// typed structs with frozen field order.
fn canonical_bytes<T: Serialize>(value: &T) -> Vec<u8> {
    serde_json::to_vec(value).expect("DirectorLoopRun types are always serializable")
}

/// SHA-256 over bytes, returned as 64-character lowercase hex, no prefix.
/// Invariant: always lowercase [a-f0-9]{64}. hex::encode guarantees this.
fn sha256_hex(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

pub fn compute_input_hash(run: &DirectorLoopRun) -> String {
    let preimage = InputHashPreimage {
        director_loop_version: &run.director_loop_version,
        threshold: run.threshold,
        ruleset_version: &run.ruleset_version,
        fixture: &run.fixture,
        config: &run.config,
    };
    sha256_hex(&canonical_bytes(&preimage))
}

pub fn compute_output_hash(run: &DirectorLoopRun) -> String {
    let preimage = OutputHashPreimage {
        status: &run.status,
        initial_coherence: run.initial_coherence,
        final_coherence: run.final_coherence,
        corrections: &run.corrections,
        regen_events: &run.regen_events,
        audit_notes: &run.audit_notes,
    };
    sha256_hex(&canonical_bytes(&preimage))
}

/// Verify both hashes in a run artifact. Returns Ok(()) or a list of failures.
pub fn verify(run: &DirectorLoopRun) -> Result<(), Vec<String>> {
    let mut failures = Vec::new();

    let expected_input = compute_input_hash(run);
    if run.input_hash != expected_input {
        failures.push(format!(
            "input_hash mismatch: artifact={} computed={}",
            run.input_hash, expected_input
        ));
    }

    let expected_output = compute_output_hash(run);
    if run.output_hash != expected_output {
        failures.push(format!(
            "output_hash mismatch: artifact={} computed={}",
            run.output_hash, expected_output
        ));
    }

    if failures.is_empty() {
        Ok(())
    } else {
        Err(failures)
    }
}
