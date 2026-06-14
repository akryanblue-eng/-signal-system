mod lock;
mod vector;

use std::collections::HashMap;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let usage = "Usage: golden-lock <generate|verify> --vectors <dir> [--baseline <file>]";

    if args.len() < 4 {
        eprintln!("{usage}");
        std::process::exit(2);
    }

    let cmd = &args[1];
    let opts = parse_flags(&args[2..]);
    let vectors_dir = opts.get("vectors").unwrap_or_else(|| {
        eprintln!("--vectors <dir> required");
        std::process::exit(2);
    });

    let vectors = vector::load_vectors_from_dir(vectors_dir);
    if vectors.is_empty() {
        eprintln!("No .json vector files found in '{vectors_dir}'");
        std::process::exit(2);
    }

    let (results, computed_root, spec_hash) = lock::evaluate_vectors(&vectors);

    match cmd.as_str() {
        "generate" => {
            let baseline_path = opts
                .get("baseline")
                .cloned()
                .unwrap_or_else(|| "golden-lock.json".to_string());
            cmd_generate(&results, &computed_root, &spec_hash, &baseline_path);
        }
        "verify" => {
            let baseline_path = opts.get("baseline").unwrap_or_else(|| {
                eprintln!("--baseline <file> required for verify");
                std::process::exit(2);
            });
            cmd_verify(&results, &computed_root, &spec_hash, baseline_path);
        }
        other => {
            eprintln!("Unknown command '{other}'. {usage}");
            std::process::exit(2);
        }
    }
}

fn cmd_generate(
    results: &[lock::VectorResult],
    global: &str,
    spec_hash: &str,
    baseline_path: &str,
) {
    println!("Golden Vector Lock — generate");
    println!();
    println!("  spec_hash (vas-exec-model-v1): {spec_hash}");
    println!();
    for r in results {
        println!("  vector: {}", r.id);
        println!("  commit: {}", r.ri0_commit);
        println!("  root:   {}", r.per_root);
        println!();
    }
    println!("global_root: {global}");

    let baseline = serde_json::json!({
        "version": "1",
        "spec": "vas-exec-model-v1",
        "spec_hash": spec_hash,
        "global_root": global,
        "vectors": results.iter().map(|r| &r.id).collect::<Vec<_>>(),
    });
    std::fs::write(baseline_path, serde_json::to_string_pretty(&baseline).unwrap())
        .unwrap_or_else(|e| panic!("write {baseline_path}: {e}"));
    println!();
    println!("Baseline written to {baseline_path}");
}

fn cmd_verify(
    results: &[lock::VectorResult],
    computed: &str,
    spec_hash: &str,
    baseline_path: &str,
) {
    let baseline_src = std::fs::read_to_string(baseline_path)
        .unwrap_or_else(|e| panic!("read {baseline_path}: {e}"));
    let baseline: serde_json::Value = serde_json::from_str(&baseline_src)
        .unwrap_or_else(|e| panic!("parse {baseline_path}: {e}"));
    let locked = baseline["global_root"]
        .as_str()
        .unwrap_or_else(|| panic!("global_root missing from baseline"));
    let locked_spec = baseline["spec_hash"].as_str().unwrap_or("(not recorded)");

    println!("Golden Vector Lock — verify");
    println!();
    println!("  spec_hash (vas-exec-model-v1): {spec_hash}");
    if locked_spec != spec_hash {
        println!("  WARNING: spec_hash differs from baseline ({locked_spec})");
    }
    println!();
    for r in results {
        println!("  vector: {}  commit: {}  root: {}", r.id, r.ri0_commit, r.per_root);
    }
    println!();
    println!("computed global_root: {computed}");
    println!("locked   global_root: {locked}");
    println!();

    if computed == locked {
        println!("PASS — all vectors match golden baseline");
    } else {
        eprintln!("FAIL — global_root mismatch: semantic regression detected");
        if locked_spec != spec_hash {
            eprintln!("  (spec_hash changed — was this an intentional spec update?)");
        }
        std::process::exit(1);
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
