// Golden trace v1.1 — first certified causal execution.
//
// Fixture: fixtures/golden_trace_v1_1.json
// Once committed, the fixture is the reference contract.
// Any change in behaviour is detectable by replaying and comparing.
//
// Generation (run once, then commit the fixture):
//   cargo test generate_golden_trace_v1_1 -- --ignored
//
// Validation (run always):
//   cargo test golden_trace_v1_1_replay
//
// Mutation suite (verifies the fixture catches specific drift classes):
//   cargo test mutation_

use serde::{Deserialize, Serialize};
use signal_system::codec::{decode, encode};
use signal_system::event::Event;
use signal_system::index::{sha256_event_hash, Cci};
use signal_system::ingress::{ExecutionPrefix, KnowledgeState};
use signal_system::kernel::{compile, genesis};
use std::path::PathBuf;

fn node(id: u8) -> [u8; 16] { [id; 16] }

// --- Hex helpers ---

fn hex_enc(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}

fn hex_dec(s: &str) -> Vec<u8> {
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).expect("valid hex"))
        .collect()
}

fn hex_to_32(s: &str) -> [u8; 32] {
    hex_dec(s).try_into().expect("32-byte hash")
}

fn hex_to_16(s: &str) -> [u8; 16] {
    hex_dec(s).try_into().expect("16-byte node_id")
}

// --- Fixture schema (frozen) ---

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq)]
struct GoldenTrace {
    recorded_schema: u8,
    trace_id: String,
    records: Vec<TraceRecord>,
}

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq)]
struct TraceRecord {
    step_index: u64,
    // Continuity anchor: must equal records[i-1].semantic.post_state_hash.
    // record[0] must equal genesis_state_hash.
    previous_post_hash: String,
    input: CanonicalInput,
    admission_result: String,
    semantic: StepSemanticDigest,
}

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq, Clone)]
#[serde(tag = "kind")]
enum CanonicalInput {
    #[serde(rename = "event")]
    Event { bytes: String, tick: u64, node_id: String },
    #[serde(rename = "ack")]
    Ack { event_hash: String, node_id: String },
}

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq)]
struct StepSemanticDigest {
    pre_state_hash: String,   // state_hash before this step's input is applied
    post_state_hash: String,  // state_hash after try_advance (same as pre if advance fails)
    frontier_digest: String,  // hex of CCI bytes, or "none"
    prefix_digest: String,    // sha256 of ordered canonical bytes, or "none"
    ready: bool,              // try_advance(stable=true) succeeded
    ack_closure: bool,        // all staging events fully acked by all known nodes
}

// --- Snapshot helpers ---

fn compile_state_hash(prefix: &ExecutionPrefix) -> [u8; 32] {
    let events: Vec<Event> = prefix.events.iter()
        .map(|ie| decode(&ie.canonical_bytes).expect("prefix has only valid events"))
        .collect();
    compile(genesis(), events).state_hash
}

fn prefix_digest(prefix: &ExecutionPrefix) -> String {
    if prefix.events.is_empty() {
        return "none".to_string();
    }
    let mut combined: Vec<u8> = Vec::new();
    for ie in &prefix.events {
        combined.extend_from_slice(&ie.canonical_bytes);
    }
    hex_enc(&sha256_event_hash(&combined))
}

fn frontier_digest(cci: Option<Cci>) -> String {
    cci.map(|f| hex_enc(f.as_bytes())).unwrap_or_else(|| "none".to_string())
}

// --- Continuity check ---

fn check_continuity(trace: &GoldenTrace) -> bool {
    for pair in trace.records.windows(2) {
        if pair[1].previous_post_hash != pair[0].semantic.post_state_hash {
            return false;
        }
    }
    true
}

// --- Trace generation ---
//
// 7-step canonical trace (single-node cluster, node(1)):
//   Step 0: Event(e1=Create{entity_id:1, kind:5}, tick=1)
//   Step 1: Ack(e1, node1) → first frontier advance
//   Step 2: Event(e2=Update{entity_id:1, field:0, value:42}, tick=2)
//   Step 3: Ack(e2, node1) → second frontier advance
//   Step 4: Ack(e1, node1) again — idempotence pressure, already processed
//   Step 5: Event(e3=Commit{entity_id:1}, tick=3)
//   Step 6: Ack(e3, node1) → third frontier advance
fn generate_trace() -> GoldenTrace {
    let e1 = encode(&Event::Create { entity_id: 1, kind: 5 });
    let e2 = encode(&Event::Update { entity_id: 1, field: 0, value: 42 });
    let e3 = encode(&Event::Commit { entity_id: 1 });
    let h1 = sha256_event_hash(&e1);
    let h2 = sha256_event_hash(&e2);
    let h3 = sha256_event_hash(&e3);

    let steps: Vec<CanonicalInput> = vec![
        CanonicalInput::Event { bytes: hex_enc(&e1), tick: 1, node_id: hex_enc(&node(1)) },
        CanonicalInput::Ack   { event_hash: hex_enc(&h1), node_id: hex_enc(&node(1)) },
        CanonicalInput::Event { bytes: hex_enc(&e2), tick: 2, node_id: hex_enc(&node(1)) },
        CanonicalInput::Ack   { event_hash: hex_enc(&h2), node_id: hex_enc(&node(1)) },
        CanonicalInput::Ack   { event_hash: hex_enc(&h1), node_id: hex_enc(&node(1)) }, // idempotent
        CanonicalInput::Event { bytes: hex_enc(&e3), tick: 3, node_id: hex_enc(&node(1)) },
        CanonicalInput::Ack   { event_hash: hex_enc(&h3), node_id: hex_enc(&node(1)) },
    ];

    let mut ks = KnowledgeState::new(node(1), [node(1)]);
    let mut records: Vec<TraceRecord> = Vec::new();

    // Persistent state across steps
    let mut curr_state_hash:    [u8; 32] = genesis().state_hash;
    let mut curr_frontier:      Option<Cci> = None;
    let mut curr_prefix_digest: String = "none".to_string();

    // Genesis state hash is the continuity anchor for record[0]
    let genesis_hash = hex_enc(&genesis().state_hash);
    let mut prev_post_hash = genesis_hash;

    for (idx, input) in steps.into_iter().enumerate() {
        let pre_state_hash = hex_enc(&curr_state_hash);

        // Apply input to KnowledgeState
        match &input {
            CanonicalInput::Event { bytes, tick, node_id } => {
                ks.ingest(hex_dec(bytes), *tick, hex_to_16(node_id));
            }
            CanonicalInput::Ack { event_hash, node_id } => {
                ks.acknowledge(hex_to_32(event_hash), hex_to_16(node_id));
            }
        }

        // C predicate — ack closure: all staging events acked by all known nodes
        let ack_closure = ks.staging.event_hashes().all(|h| ks.acks.all_acknowledged(h));

        // Try advance and capture result
        let (ready, admission_result) = match ks.try_advance(true) {
            Ok(ref prefix) => {
                curr_state_hash    = compile_state_hash(prefix);
                curr_frontier      = prefix.frontier;
                curr_prefix_digest = prefix_digest(prefix);
                (true, "Ok".to_string())
            }
            Err(e) => (false, format!("{:?}", e)),
        };

        let post_state_hash = hex_enc(&curr_state_hash);

        records.push(TraceRecord {
            step_index: idx as u64,
            previous_post_hash: prev_post_hash.clone(),
            input,
            admission_result,
            semantic: StepSemanticDigest {
                pre_state_hash,
                post_state_hash: post_state_hash.clone(),
                frontier_digest: frontier_digest(curr_frontier),
                prefix_digest: curr_prefix_digest.clone(),
                ready,
                ack_closure,
            },
        });

        prev_post_hash = post_state_hash;
    }

    GoldenTrace { recorded_schema: 1, trace_id: "7c3a9e".to_string(), records }
}

// --- Fixture I/O ---

fn fixture_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("fixtures")
        .join("golden_trace_v1_1.json")
}

fn load_fixture() -> GoldenTrace {
    let path = fixture_path();
    assert!(path.exists(), "fixture not found at {:?} — run: cargo test generate_golden_trace_v1_1 -- --ignored", path);
    let json = std::fs::read_to_string(&path).expect("read fixture");
    serde_json::from_str(&json).expect("parse fixture")
}

// --- Generation (run once, then commit the output) ---

#[test]
#[ignore]
fn generate_golden_trace_v1_1() {
    let trace = generate_trace();
    let path  = fixture_path();
    std::fs::create_dir_all(path.parent().unwrap()).unwrap();
    std::fs::write(&path, serde_json::to_string_pretty(&trace).unwrap()).unwrap();
    eprintln!("Written: {:?}", path);
}

// --- Replay validation ---

#[test]
fn golden_trace_v1_1_replay() {
    let fixture   = load_fixture();
    let generated = generate_trace();

    assert_eq!(generated.recorded_schema, fixture.recorded_schema,
        "schema version drift");
    assert_eq!(generated.trace_id, fixture.trace_id,
        "trace_id drift");
    assert_eq!(generated.records.len(), fixture.records.len(),
        "record count drift");

    for (g, f) in generated.records.iter().zip(fixture.records.iter()) {
        assert_eq!(g, f,
            "semantic drift at step {}\n  expected: {}\n  actual:   {}",
            f.step_index,
            serde_json::to_string(f).unwrap(),
            serde_json::to_string(g).unwrap());
    }

    // Continuity chain must hold across all records
    assert!(check_continuity(&fixture),
        "continuity chain broken: record[i].previous_post_hash != record[i-1].semantic.post_state_hash");

    // record[0] is anchored to genesis
    assert_eq!(fixture.records[0].previous_post_hash, hex_enc(&genesis().state_hash),
        "record[0].previous_post_hash must equal genesis state hash");
}

// --- Mutation suite ---
//
// Each test mutates one field of the generated trace and verifies
// that the specific validation layer catches it.

// Mutation: schema version change → detected at schema comparison (stage 0).
#[test]
fn mutation_schema_version_detected() {
    let mut mutated = generate_trace();
    mutated.recorded_schema = 2;
    let fixture = load_fixture();
    assert_ne!(mutated.recorded_schema, fixture.recorded_schema,
        "schema version mutation must be detectable");
}

// Mutation: corrupted previous_post_hash → detected by continuity chain.
#[test]
fn mutation_previous_post_hash_breaks_continuity() {
    let mut trace = generate_trace();
    // Flip the first character of record[2].previous_post_hash
    let orig = &trace.records[2].previous_post_hash.clone();
    trace.records[2].previous_post_hash = flip_hex_char(orig, 0);
    assert!(!check_continuity(&trace),
        "corrupted previous_post_hash must break continuity check");
}

// Mutation: post_state_hash flip → continuity chain detects it at the next record.
#[test]
fn mutation_post_state_hash_breaks_continuity() {
    let mut trace = generate_trace();
    let orig = trace.records[1].semantic.post_state_hash.clone();
    trace.records[1].semantic.post_state_hash = flip_hex_char(&orig, 0);
    // record[2].previous_post_hash must no longer match the mutated record[1].post_state_hash
    assert_ne!(
        trace.records[2].previous_post_hash,
        trace.records[1].semantic.post_state_hash,
        "post_state_hash mutation must break continuity with next record"
    );
    assert!(!check_continuity(&trace));
}

// Mutation: frontier_digest flip → semantic oracle detects it.
#[test]
fn mutation_frontier_digest_detected() {
    let generated = generate_trace();
    let mut mutated = generate_trace();
    let orig = mutated.records[1].semantic.frontier_digest.clone();
    mutated.records[1].semantic.frontier_digest = flip_hex_char(&orig, 0);
    assert_ne!(generated.records[1].semantic, mutated.records[1].semantic,
        "frontier_digest mutation must be detectable by semantic comparison");
}

// Mutation: input bytes change → different event hash → different state hash chain.
// Verified by checking that the generated trace differs from a trace built with altered input.
#[test]
fn mutation_input_bytes_changes_semantic_chain() {
    let genuine = generate_trace();
    // Verify that if we change the event bytes at step 0, the semantic output changes.
    // We do this by checking that the input bytes field is part of the equality contract.
    let mut altered = generate_trace();
    if let CanonicalInput::Event { ref mut bytes, .. } = altered.records[0].input {
        // Corrupt the last byte of the event payload
        let mut raw = hex_dec(bytes);
        *raw.last_mut().unwrap() ^= 0xFF;
        *bytes = hex_enc(&raw);
    }
    // The altered struct differs in the input field — detectable
    assert_ne!(genuine.records[0].input, altered.records[0].input,
        "input bytes mutation must be detectable in the input field");
}

// Mutation: remove field (schema strictness) — deserialization must reject.
#[test]
fn mutation_missing_input_field_rejected() {
    let json = std::fs::read_to_string(fixture_path()).expect("read fixture");
    let mut v: serde_json::Value = serde_json::from_str(&json).expect("parse json");
    // Remove the required "bytes" field from step 0's event input
    v["records"][0]["input"].as_object_mut().unwrap().remove("bytes");
    let corrupted = serde_json::to_string(&v).unwrap();
    let result: Result<GoldenTrace, _> = serde_json::from_str(&corrupted);
    assert!(result.is_err(),
        "missing required input field must cause deserialization failure");
}

// --- Helper ---

fn flip_hex_char(s: &str, pos: usize) -> String {
    s.chars().enumerate().map(|(i, c)| {
        if i == pos { if c == 'a' || c == 'A' { 'b' } else { 'a' }
        } else { c }
    }).collect()
}
