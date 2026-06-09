use std::{fs, process};

use signal_system::verifier::{verify_bytes, AuditStatus};

fn main() {
    let path = std::env::args().nth(1).unwrap_or_else(|| {
        eprintln!("usage: verifier <path-to-artifact.json>");
        process::exit(2);
    });

    let bytes = fs::read(&path).unwrap_or_else(|e| {
        eprintln!("error reading {path}: {e}");
        process::exit(2);
    });

    let report = verify_bytes(&bytes);
    println!("{}", serde_json::to_string_pretty(&report).unwrap());

    if report.audit_status == AuditStatus::Fail {
        process::exit(1);
    }
}
