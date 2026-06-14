// Implementation C — Rust
// RI-0 + CT-0 Evidence Gate chain.
// Canonical encoding must match Python (impl_a) and Go (impl_b) exactly.

use dsvm_core::{ri0_replay, WitnessPacket304};
use sha2::{Digest, Sha256};
use std::time::{SystemTime, UNIX_EPOCH};

struct CfrFailureRecord {
    cfr_id: String,
    failure_code: String,
    scope: String,
    outcome: String,
    evidence_hash: String,
    priority_rank: u32,
}

struct Verdict {
    status: String,
    cfr: Option<CfrFailureRecord>,
}

struct Certificate {
    certificate_id: String,
    run_id: String,
    replay_commit: String,
    verdict_status: String,
    issued_at_ns: u64,
}

fn ct0_evaluate(
    auth_commit: &[u8; 32],
    replay_commit: &[u8; 32],
    run_id: &str,
) -> (Verdict, Certificate) {
    let verdict = if auth_commit == replay_commit {
        Verdict { status: "OK".to_string(), cfr: None }
    } else {
        let mut ev_input = Vec::new();
        ev_input.extend_from_slice(auth_commit);
        ev_input.extend_from_slice(replay_commit);
        let ev_hash: [u8; 32] = Sha256::digest(&ev_input).into();
        Verdict {
            status: "FAIL".to_string(),
            cfr: Some(CfrFailureRecord {
                cfr_id: "CFR-MISMATCH".to_string(),
                failure_code: "REPLAY_MISMATCH".to_string(),
                scope: "RI-0/CT-0".to_string(),
                outcome: "FAIL".to_string(),
                evidence_hash: hex::encode(ev_hash),
                priority_rank: 1,
            }),
        }
    };

    let mut cert_payload = Vec::new();
    cert_payload.extend_from_slice(auth_commit);
    cert_payload.extend_from_slice(replay_commit);
    cert_payload.extend_from_slice(verdict.status.as_bytes());
    cert_payload.extend_from_slice(run_id.as_bytes());
    let cert_hash: [u8; 32] = Sha256::digest(&cert_payload).into();

    let issued_at_ns = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos() as u64;

    let cert = Certificate {
        certificate_id: hex::encode(cert_hash),
        run_id: run_id.to_string(),
        replay_commit: hex::encode(replay_commit),
        verdict_status: verdict.status.clone(),
        issued_at_ns,
    };

    (verdict, cert)
}

fn build_synthetic_trace() -> WitnessPacket304 {
    let bundle_hash: [u8; 32] = Sha256::digest(b"simulation-os-bundle-v0.5").into();
    let validator_pubkey: [u8; 32] = Sha256::digest(b"validator-pubkey-ri0-ct0").into();

    let prev_state_bytes = vec![0u8; 64];

    let mut frozen_batch_bytes = vec![0u8; 48];
    for i in (0..48).step_by(3) {
        frozen_batch_bytes[i] = 0xAB;
        frozen_batch_bytes[i + 1] = 0xCD;
        frozen_batch_bytes[i + 2] = 0xEF;
    }

    WitnessPacket304 {
        run_id: "TRACE-V05-0001".to_string(),
        prev_state_bytes,
        frozen_batch_bytes,
        bundle_hash,
        bundle_version: 5,
        validator_pubkey,
        signals: vec![
            ("signal.alpha".to_string(), 1),
            ("signal.beta".to_string(), 2),
            ("signal.gamma".to_string(), 3),
            ("signal.alpha".to_string(), 99), // duplicate — deduped to 99
        ],
    }
}

fn main() {
    let packet = build_synthetic_trace();

    let mut trace_input = Vec::new();
    trace_input.extend_from_slice(packet.run_id.as_bytes());
    trace_input.extend_from_slice(&packet.bundle_hash);
    let trace_hash: [u8; 32] = Sha256::digest(&trace_input).into();
    let trace_id = hex::encode_upper(&trace_hash[..8]);

    let auth_commit = ri0_replay(&packet);
    let replay_commit = ri0_replay(&packet);

    if auth_commit != replay_commit {
        eprintln!("FATAL: RI-0 non-determinism");
        std::process::exit(1);
    }

    let (verdict, cert) = ct0_evaluate(&auth_commit, &replay_commit, &packet.run_id);

    let build_id = "C1EA5749F20B3D92";

    println!("run_id:      {}", packet.run_id);
    println!("build_id:    {}", build_id);
    println!("trace_id:    {}", trace_id);
    println!("commit:      {}", hex::encode(replay_commit));
    println!("certificate: {}", cert.certificate_id);
    println!("verdict:     {}", verdict.status);
}
