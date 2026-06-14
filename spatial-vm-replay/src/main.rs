use spatial_vm_replay::{lock, vector};
use std::fs;

fn usage() -> ! {
    eprintln!("usage:");
    eprintln!("  spatial-vm-replay generate-all --vectors <dir> --baseline <file>");
    eprintln!("  spatial-vm-replay verify        --vectors <dir> --baseline <file>");
    std::process::exit(1);
}

fn parse_args(args: &[String]) -> (String, String) {
    let mut vectors_dir = None;
    let mut baseline_file = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--vectors" => { i += 1; vectors_dir = args.get(i).cloned(); }
            "--baseline" => { i += 1; baseline_file = args.get(i).cloned(); }
            _ => {}
        }
        i += 1;
    }
    (
        vectors_dir.unwrap_or_else(|| usage()),
        baseline_file.unwrap_or_else(|| usage()),
    )
}

fn cmd_generate_all(vectors_dir: &str, baseline_file: &str) {
    let vectors = vector::load_vectors_from_dir(vectors_dir);
    if vectors.is_empty() {
        eprintln!("no vectors found in {vectors_dir}");
        std::process::exit(1);
    }

    let (results, global_root_hex) = lock::evaluate_vectors(&vectors);

    let mut obj = serde_json::json!({
        "global_root": global_root_hex,
        "vectors": results.iter().map(|r| {
            serde_json::json!({
                "id": r.id,
                "seq_commit": hex::encode(r.seq_commit),
                "per_vector_root": hex::encode(r.per_vector_root),
            })
        }).collect::<Vec<_>>(),
    });

    // stable key order: global_root first, then vectors array
    let json = serde_json::to_string_pretty(&obj).unwrap();
    fs::write(baseline_file, &json)
        .unwrap_or_else(|e| panic!("cannot write {baseline_file}: {e}"));

    println!("generated {baseline_file}");
    println!("global_root: {global_root_hex}");
    for r in &results {
        println!("  {} seq_commit={}", r.id, hex::encode(r.seq_commit));
    }

    // suppress unused warning
    let _ = obj.take();
}

fn cmd_verify(vectors_dir: &str, baseline_file: &str) {
    let vectors = vector::load_vectors_from_dir(vectors_dir);
    let (results, computed_global) = lock::evaluate_vectors(&vectors);

    let baseline_text = fs::read_to_string(baseline_file)
        .unwrap_or_else(|e| panic!("cannot read {baseline_file}: {e}"));
    let baseline: serde_json::Value = serde_json::from_str(&baseline_text)
        .unwrap_or_else(|e| panic!("invalid JSON in {baseline_file}: {e}"));

    let locked_global = baseline["global_root"]
        .as_str()
        .unwrap_or_else(|| panic!("missing global_root in {baseline_file}"));

    let mut ok = true;

    if computed_global != locked_global {
        eprintln!("FAIL global_root mismatch");
        eprintln!("  computed: {computed_global}");
        eprintln!("  locked:   {locked_global}");
        ok = false;
    }

    for r in &results {
        let computed_seq = hex::encode(r.seq_commit);
        let computed_pvr = hex::encode(r.per_vector_root);
        if let Some(entry) = baseline["vectors"]
            .as_array()
            .and_then(|arr| arr.iter().find(|v| v["id"].as_str() == Some(&r.id)))
        {
            let locked_seq = entry["seq_commit"].as_str().unwrap_or("");
            let locked_pvr = entry["per_vector_root"].as_str().unwrap_or("");
            if computed_seq != locked_seq {
                eprintln!("FAIL {} seq_commit mismatch", r.id);
                eprintln!("  computed: {computed_seq}");
                eprintln!("  locked:   {locked_seq}");
                ok = false;
            }
            if computed_pvr != locked_pvr {
                eprintln!("FAIL {} per_vector_root mismatch", r.id);
                eprintln!("  computed: {computed_pvr}");
                eprintln!("  locked:   {locked_pvr}");
                ok = false;
            }
        } else {
            eprintln!("FAIL {} not found in baseline", r.id);
            ok = false;
        }
    }

    if ok {
        println!("OK all {} vectors pass", results.len());
        println!("global_root: {computed_global}");
    } else {
        std::process::exit(1);
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() {
        usage();
    }

    let subcmd = args[0].as_str();
    let rest = &args[1..];

    match subcmd {
        "generate-all" => {
            let (vd, bf) = parse_args(rest);
            cmd_generate_all(&vd, &bf);
        }
        "verify" => {
            let (vd, bf) = parse_args(rest);
            cmd_verify(&vd, &bf);
        }
        _ => {
            eprintln!("unknown subcommand: {subcmd}");
            usage();
        }
    }
}
