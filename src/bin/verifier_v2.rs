use std::{fs, process};

use signal_system::verifier_v2::{verify_bytes_v2, AuditStatusV2};

/// Exit codes:
///   0 — PASS   (artifact passed all gates)
///   1 — FAIL   (artifact failed a protocol/integrity gate)
///   2 — ERROR  (system failure: I/O error, missing argument, etc.)
fn main() {
    let path = std::env::args().nth(1).unwrap_or_else(|| {
        eprintln!("usage: verifier_v2 <path-to-artifact.json>");
        process::exit(2);
    });

    let bytes = fs::read(&path).unwrap_or_else(|e| {
        eprintln!("error: could not read {path}: {e}");
        process::exit(2);
    });

    let report = verify_bytes_v2(&bytes);
    println!("{}", serde_json::to_string_pretty(&report).unwrap());

    match report.audit_status {
        AuditStatusV2::Pass => process::exit(0),
        AuditStatusV2::Fail => process::exit(1),
    }
}
