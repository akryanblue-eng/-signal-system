mod compare;
mod tracer;

use sha2::{Digest, Sha256};
use std::collections::HashMap;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let usage = concat!(
        "Usage:\n",
        "  replay-witness generate --vector <file.json> [--output <out.json>]\n",
        "  replay-witness generate-all --vectors <dir> --output-dir <dir>\n",
        "  replay-witness compare <witness_a.json> <witness_b.json>",
    );

    if args.len() < 2 {
        eprintln!("{usage}");
        std::process::exit(2);
    }

    match args[1].as_str() {
        "generate" => {
            let opts = parse_flags(&args[2..]);
            let vector_path = opts.get("vector").unwrap_or_else(|| {
                eprintln!("--vector <file> required");
                std::process::exit(2);
            });
            let vector = load_vector(vector_path);
            let witness = tracer::WitnessLog::generate(&vector.id, &vector.to_witness());
            let json = witness.to_json();
            if let Some(out) = opts.get("output") {
                std::fs::write(out, &json)
                    .unwrap_or_else(|e| panic!("write {out}: {e}"));
                println!("Witness log written to {out}");
                println!("  vector_id:  {}", witness.vector_id);
                println!("  ri0_commit: {}", witness.ri0_commit);
            } else {
                println!("{json}");
            }
        }
        "generate-all" => {
            let opts = parse_flags(&args[2..]);
            let vectors_dir = opts.get("vectors").unwrap_or_else(|| {
                eprintln!("--vectors <dir> required");
                std::process::exit(2);
            });
            let output_dir = opts.get("output-dir").unwrap_or_else(|| {
                eprintln!("--output-dir <dir> required");
                std::process::exit(2);
            });
            std::fs::create_dir_all(output_dir)
                .unwrap_or_else(|e| panic!("create {output_dir}: {e}"));

            let vectors = load_vectors_dir(vectors_dir);
            for v in &vectors {
                let witness = tracer::WitnessLog::generate(&v.id, &v.to_witness());
                let out_path = format!("{output_dir}/{}.json", v.id.to_lowercase().replace('-', "_"));
                std::fs::write(&out_path, witness.to_json())
                    .unwrap_or_else(|e| panic!("write {out_path}: {e}"));
                println!("  {} → {} (commit: {})", v.id, out_path, witness.ri0_commit);
            }
            println!("Generated {} witness log(s) in {output_dir}", vectors.len());
        }
        "compare" => {
            if args.len() < 4 {
                eprintln!("compare requires two witness log files");
                std::process::exit(2);
            }
            let path_a = &args[2];
            let path_b = &args[3];
            let (id_a, commit_a, fields_a) = tracer::load_log(path_a);
            let (id_b, commit_b, fields_b) = tracer::load_log(path_b);

            println!("Replay Witness — compare");
            println!("  A: {path_a} ({id_a})  commit: {commit_a}");
            println!("  B: {path_b} ({id_b})  commit: {commit_b}");
            println!();

            match compare::compare_logs(
                &id_a, &commit_a, &fields_a,
                &id_b, &commit_b, &fields_b,
            ) {
                compare::CompareResult::Match { ri0_commit } => {
                    println!("MATCH — ri0_commit: {ri0_commit}");
                }
                compare::CompareResult::CommitMismatch { field, key, value_a, value_b } => {
                    eprintln!("DIVERGENCE at field '{field}' ({key})");
                    eprintln!("  A: {value_a}");
                    eprintln!("  B: {value_b}");
                    std::process::exit(1);
                }
                compare::CompareResult::StructureMismatch { reason } => {
                    eprintln!("STRUCTURE MISMATCH: {reason}");
                    std::process::exit(1);
                }
            }
        }
        other => {
            eprintln!("Unknown command '{other}'\n{usage}");
            std::process::exit(2);
        }
    }
}

// ---- vector loading (mirrors golden-lock vector format) ----

struct GoldenVector {
    id: String,
    run_id: String,
    prev_state_hex: String,
    frozen_batch_hex: String,
    bundle_hash_hex: String,
    bundle_hash_preimage: String,
    bundle_version: u32,
    validator_pubkey_hex: String,
    validator_pubkey_preimage: String,
    signals: Vec<(String, i64)>,
}

impl GoldenVector {
    fn to_witness(&self) -> dsvm_core::WitnessPacket304 {
        dsvm_core::WitnessPacket304 {
            run_id: self.run_id.clone(),
            prev_state_bytes: hex::decode(&self.prev_state_hex).expect("prev_state_hex"),
            frozen_batch_bytes: hex::decode(&self.frozen_batch_hex).expect("frozen_batch_hex"),
            bundle_hash: self.resolve_bundle_hash(),
            bundle_version: self.bundle_version,
            validator_pubkey: self.resolve_validator_pubkey(),
            signals: self.signals.clone(),
        }
    }

    fn resolve_bundle_hash(&self) -> [u8; 32] {
        if !self.bundle_hash_preimage.is_empty() {
            Sha256::digest(self.bundle_hash_preimage.as_bytes()).into()
        } else {
            hex_to_32(&self.bundle_hash_hex)
        }
    }

    fn resolve_validator_pubkey(&self) -> [u8; 32] {
        if !self.validator_pubkey_preimage.is_empty() {
            Sha256::digest(self.validator_pubkey_preimage.as_bytes()).into()
        } else {
            hex_to_32(&self.validator_pubkey_hex)
        }
    }
}

fn hex_to_32(s: &str) -> [u8; 32] {
    let b = hex::decode(s).unwrap_or_else(|e| panic!("hex_to_32: {e}"));
    assert_eq!(b.len(), 32, "expected 32 bytes");
    b.try_into().unwrap()
}

fn load_vector(path: &str) -> GoldenVector {
    let src = std::fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("read {path}: {e}"));
    parse_vector(&src, path)
}

fn load_vectors_dir(dir: &str) -> Vec<GoldenVector> {
    let mut vectors: Vec<GoldenVector> = std::fs::read_dir(dir)
        .unwrap_or_else(|e| panic!("read dir {dir}: {e}"))
        .filter_map(|e| {
            let e = e.ok()?;
            let p = e.path();
            if p.extension().and_then(|x| x.to_str()) == Some("json") {
                let src = std::fs::read_to_string(&p).ok()?;
                Some(parse_vector(&src, p.to_str().unwrap_or("?")))
            } else {
                None
            }
        })
        .collect();
    vectors.sort_by(|a, b| a.id.cmp(&b.id));
    vectors
}

fn parse_vector(src: &str, path: &str) -> GoldenVector {
    let v: serde_json::Value = serde_json::from_str(src)
        .unwrap_or_else(|e| panic!("parse {path}: {e}"));
    let signals: Vec<(String, i64)> = v["signals"]
        .as_array()
        .unwrap_or(&vec![])
        .iter()
        .map(|pair| {
            let arr = pair.as_array().expect("signal must be [key, value]");
            (
                arr[0].as_str().expect("signal key").to_string(),
                arr[1].as_i64().expect("signal value"),
            )
        })
        .collect();

    GoldenVector {
        id: v["id"].as_str().unwrap_or("").to_string(),
        run_id: v["run_id"].as_str().unwrap_or("").to_string(),
        prev_state_hex: v["prev_state_hex"].as_str().unwrap_or("").to_string(),
        frozen_batch_hex: v["frozen_batch_hex"].as_str().unwrap_or("").to_string(),
        bundle_hash_hex: v["bundle_hash_hex"].as_str().unwrap_or("").to_string(),
        bundle_hash_preimage: v["bundle_hash_preimage"].as_str().unwrap_or("").to_string(),
        bundle_version: v["bundle_version"].as_u64().unwrap_or(0) as u32,
        validator_pubkey_hex: v["validator_pubkey_hex"].as_str().unwrap_or("").to_string(),
        validator_pubkey_preimage: v["validator_pubkey_preimage"].as_str().unwrap_or("").to_string(),
        signals,
    }
}

fn parse_flags(args: &[String]) -> HashMap<String, String> {
    let mut map = HashMap::new();
    let mut i = 0;
    while i < args.len() {
        if let Some(key) = args[i].strip_prefix("--") {
            if i + 1 < args.len() {
                map.insert(key.to_string(), args[i + 1].clone());
                i += 2;
                continue;
            }
        }
        i += 1;
    }
    map
}
