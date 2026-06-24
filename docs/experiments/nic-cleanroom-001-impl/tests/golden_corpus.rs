//! Post-freeze evaluation harness — NOT part of the clean-room implementation.
//!
//! This file was added by the experiment orchestrator AFTER the clean-room
//! implementer declared the crate complete (see ../FREEZE.md) and after the
//! golden corpus was revealed for the first time (see
//! ../../docs/experiments/nic-cleanroom-001.md). It drives every case in
//! golden_corpus/cases.json through the frozen crate's public API exactly
//! as written; it makes no changes to src/.

use nic_core::glob::glob_match;
use nic_core::hashdomain::{
    check_no_unknown_edges, compute_edge_id, compute_set_hash, compute_witness_hash, Edge,
};
use nic_core::path::canonical_path_hex;
use nic_core::proof::verify_proof_schema;
use nic_core::url::canonicalize_url;
use serde_json::Value;
use std::fs;

#[derive(Debug)]
struct CaseResult {
    id: String,
    ok: bool,
    detail: String,
}

fn run_op(op: &str, args: &Value) -> Result<Value, String> {
    match op {
        "canonical_path" => {
            let raw = args["raw"].as_str().unwrap();
            canonical_path_hex(raw)
                .map(Value::String)
                .map_err(|e| e.to_string())
        }
        "glob_match" => {
            let pattern = args["pattern"].as_str().unwrap();
            let path = args["path"].as_str().unwrap();
            glob_match(pattern, path)
                .map(Value::Bool)
                .map_err(|e| e.to_string())
        }
        "canonicalize_url" => {
            let raw_url = args["raw_url"].as_str().unwrap();
            canonicalize_url(raw_url)
                .map(Value::String)
                .map_err(|e| e.to_string())
        }
        "compute_edge_id" => {
            let from = args["from_"].as_str().unwrap();
            let ty = args["type"].as_str().unwrap();
            let to = args["to"].as_str().unwrap();
            Ok(Value::String(compute_edge_id(from, ty, to)))
        }
        "compute_set_hash" => {
            let ids: Vec<String> = args["edge_ids"]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| v.as_str().unwrap().to_string())
                .collect();
            Ok(Value::String(compute_set_hash(&ids)))
        }
        "compute_witness_hash" => {
            let ids: Vec<String> = args["edge_ids"]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| v.as_str().unwrap().to_string())
                .collect();
            Ok(Value::String(compute_witness_hash(&ids)))
        }
        "check_no_unknown_edges" => {
            let edges: Vec<Edge> = args["edges"]
                .as_array()
                .unwrap()
                .iter()
                .map(|e| Edge {
                    from: e["from_"].as_str().unwrap().to_string(),
                    edge_type: e["type"].as_str().unwrap().to_string(),
                    to: e["to"].as_str().unwrap().to_string(),
                })
                .collect();
            let waived: Vec<String> = args["waived_edge_ids"]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| v.as_str().unwrap().to_string())
                .collect();
            Ok(Value::Bool(check_no_unknown_edges(&edges, &waived)))
        }
        "verify_proof_schema" => Ok(Value::Bool(verify_proof_schema(&args["obj"]))),
        other => Err(format!("unknown op {other}")),
    }
}

#[test]
fn golden_corpus_conformance() {
    let raw = fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/golden_corpus/cases.json"))
        .expect("read cases.json");
    let corpus: Value = serde_json::from_str(&raw).expect("parse cases.json");
    let cases = corpus["cases"].as_array().expect("cases array");

    let mut results = Vec::new();
    for case in cases {
        let id = case["id"].as_str().unwrap().to_string();
        let op = case["op"].as_str().unwrap();
        let args = &case["args"];

        let outcome = run_op(op, args);

        if let Some(expect_error) = case.get("expect_error").and_then(|v| v.as_str()) {
            match outcome {
                Ok(v) => results.push(CaseResult {
                    id,
                    ok: false,
                    detail: format!("expected error containing {expect_error:?}, got Ok({v})"),
                }),
                Err(msg) if msg.contains(expect_error) => {
                    results.push(CaseResult { id, ok: true, detail: String::new() })
                }
                Err(msg) => results.push(CaseResult {
                    id,
                    ok: false,
                    detail: format!("error {msg:?} does not contain {expect_error:?}"),
                }),
            }
        } else {
            let expect = case.get("expect").cloned().unwrap_or(Value::Null);
            match outcome {
                Ok(v) if v == expect => {
                    results.push(CaseResult { id, ok: true, detail: String::new() })
                }
                Ok(v) => results.push(CaseResult {
                    id,
                    ok: false,
                    detail: format!("expected {expect}, got {v}"),
                }),
                Err(msg) => results.push(CaseResult {
                    id,
                    ok: false,
                    detail: format!("unexpected error: {msg}"),
                }),
            }
        }
    }

    let failed: Vec<&CaseResult> = results.iter().filter(|r| !r.ok).collect();
    let passed = results.len() - failed.len();
    println!("golden corpus: {passed}/{} passed", results.len());
    for f in &failed {
        println!("  FAIL {}: {}", f.id, f.detail);
    }
    assert!(failed.is_empty(), "{} of {} cases failed", failed.len(), results.len());
}

#[test]
fn manifest_hash_parity() {
    let registry_raw = fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/golden_corpus/edge_extractor_v1.json"
    ))
    .expect("read edge_extractor_v1.json");
    let registry: Value = serde_json::from_str(&registry_raw).expect("parse registry");

    let manifest_raw = fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/golden_corpus/manifest.json"
    ))
    .expect("read manifest.json");
    let committed: Value = serde_json::from_str(&manifest_raw).expect("parse manifest.json");

    let computed = nic_core::manifest::Manifest::build(
        &registry,
        committed["case_count"].as_i64().unwrap(),
    )
    .expect("build manifest");

    let committed_proof_schema_hash = committed["proof_schema_hash"].as_str().unwrap();
    let committed_registry_hash = committed["registry_hash"].as_str().unwrap();

    println!(
        "proof_schema_hash: computed={} committed={}",
        computed.proof_schema_hash, committed_proof_schema_hash
    );
    println!(
        "registry_hash:     computed={} committed={}",
        computed.registry_hash, committed_registry_hash
    );

    assert_eq!(computed.proof_schema_hash, committed_proof_schema_hash);
    assert_eq!(computed.registry_hash, committed_registry_hash);
}
