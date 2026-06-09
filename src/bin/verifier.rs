use std::{fs, process};

use signal_system::verifier::{verify_bytes, AuditStatus};

/// Exit codes:
///   0 — PASS   (artifact passed all gates)
///   1 — FAIL   (artifact failed a protocol/integrity gate)
///   2 — ERROR  (system failure: I/O error, missing argument, etc.)
fn main() {
    let path = std::env::args().nth(1).unwrap_or_else(|| {
        eprintln!("usage: verifier <path-to-artifact.json>");
        process::exit(2);
    });

    let bytes = fs::read(&path).unwrap_or_else(|e| {
        eprintln!("error: could not read {path}: {e}");
        process::exit(2);
    });

    let report = verify_bytes(&bytes);
    // Report always goes to stdout. Callers parse it; exit code is the verdict.
    println!("{}", serde_json::to_string_pretty(&report).unwrap());

    match report.audit_status {
        AuditStatus::Pass => process::exit(0),
        AuditStatus::Fail => process::exit(1),
    }
}
