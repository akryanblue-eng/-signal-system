use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// Fixed-point millionths — same as V1. 950_000 = 0.95. No floats.
pub type CoherenceValue = u32;

// ── Domain structs ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DirectorLoopRunV2 {
    pub v2_version: String,
    pub run_id: String,
    pub parent_run_id: Option<String>,
    pub protocol_sha: String,
    pub inputs: InputsV2,
    pub execution: ExecutionV2,
    pub audit: AuditLogV2,
    pub input_hash: String,
    pub output_hash: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct InputsV2 {
    pub fixture: FixtureV2,
    pub config: ConfigV2,
    pub threshold: CoherenceValue,
    pub ruleset_version: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FixtureV2 {
    pub fixture_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ConfigV2 {
    pub max_corrections: u32,
    pub regen_budget: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExecutionV2 {
    pub status: RunStatus,
    pub initial_coherence: CoherenceValue,
    pub final_coherence: CoherenceValue,
    pub timeline: Vec<TimelineStep>,
    pub transitions: Vec<TransitionV2>,
    pub corrections: Vec<CorrectionV2>,
    pub regen_events: Vec<RegenEventV2>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TimelineStep {
    pub step: u32,
    pub event: TimelineEvent,
    pub state: RunStatus,
    pub beat_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum TimelineEvent {
    #[serde(rename = "Start")]
    Start,
    #[serde(rename = "Evaluate")]
    Evaluate,
    #[serde(rename = "RegenRequest")]
    RegenRequest,
    #[serde(rename = "RegenApply")]
    RegenApply,
    #[serde(rename = "Transition")]
    Transition,
    #[serde(rename = "Finalize")]
    Finalize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum RunStatus {
    #[serde(rename = "PASSED")]
    Passed,
    #[serde(rename = "REGENERATED")]
    Regenerated,
    #[serde(rename = "FAILED")]
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TransitionV2 {
    pub from: RunStatus,
    pub to: RunStatus,
    pub trigger: RegenTrigger,
    pub beat_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum RegenTrigger {
    #[serde(rename = "StateViolation")]
    StateViolation,
    #[serde(rename = "StructuralViolation")]
    StructuralViolation,
    #[serde(rename = "HashMismatch")]
    HashMismatch,
    #[serde(rename = "ExternalOverride")]
    ExternalOverride,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CorrectionV2 {
    pub beat_id: String,
    pub rule: CorrectionRuleV2,
    pub action: CorrectionActionV2,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CorrectionRuleV2 {
    #[serde(rename = "RHYTHM_DRIFT")]
    RhythmDrift,
    #[serde(rename = "MOTION_STRENGTH")]
    MotionStrength,
    #[serde(rename = "AV_ALIGNMENT")]
    AvAlignment,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CorrectionActionV2 {
    #[serde(rename = "adjust_xfade")]
    AdjustXfade,
    #[serde(rename = "regen_beat")]
    RegenBeat,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RegenEventV2 {
    pub beat_id: String,
    pub trigger: RegenTrigger,
    pub request_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AuditLogV2 {
    pub notes: Vec<String>,
    pub warnings: Vec<String>,
}

// ── Preimage structs (field order is frozen — never reorder) ─────────────────

#[derive(Serialize)]
struct InputHashPreimageV2<'a> {
    v2_version: &'a str,
    run_id: &'a str,
    parent_run_id: Option<&'a str>,
    protocol_sha: &'a str,
    inputs: &'a InputsV2,
}

#[derive(Serialize)]
struct OutputHashPreimageV2<'a> {
    v2_version: &'a str,
    run_id: &'a str,
    parent_run_id: Option<&'a str>,
    execution: &'a ExecutionV2,
    audit: &'a AuditLogV2,
    input_hash: &'a str,
}

// ── Hash computation ─────────────────────────────────────────────────────────

fn canonical_bytes<T: Serialize>(value: &T) -> Vec<u8> {
    serde_json::to_vec(value).expect("V2 types are always serializable")
}

/// SHA-256 over bytes. Output: 64-character lowercase hex, no prefix.
fn sha256_hex(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

pub fn compute_input_hash(run: &DirectorLoopRunV2) -> String {
    sha256_hex(&canonical_bytes(&InputHashPreimageV2 {
        v2_version: &run.v2_version,
        run_id: &run.run_id,
        parent_run_id: run.parent_run_id.as_deref(),
        protocol_sha: &run.protocol_sha,
        inputs: &run.inputs,
    }))
}

pub fn compute_output_hash(run: &DirectorLoopRunV2) -> String {
    sha256_hex(&canonical_bytes(&OutputHashPreimageV2 {
        v2_version: &run.v2_version,
        run_id: &run.run_id,
        parent_run_id: run.parent_run_id.as_deref(),
        execution: &run.execution,
        audit: &run.audit,
        input_hash: &run.input_hash,
    }))
}
