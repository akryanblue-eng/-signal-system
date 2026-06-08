use clap::{Parser, Subcommand};
use std::fs;
use std::path::PathBuf;
use vdce::canonical::canonical_bytes;
use vdce::certify::certify;
use vdce::kernel::replay;

#[derive(Parser)]
#[command(name = "vdce", about = "VDCE v1.1 Verification and Deterministic Computation Engine")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Replay a trace through the verification kernel; exit non-zero on any failure.
    Replay {
        #[arg(long)]
        trace: PathBuf,
    },
    /// Replay a trace and emit a deterministic certification artifact.
    Certify {
        #[arg(long)]
        trace: PathBuf,
        #[arg(long)]
        out: PathBuf,
    },
}

fn main() {
    let cli = Cli::parse();
    match cli.command {
        Commands::Replay { trace } => cmd_replay(&trace),
        Commands::Certify { trace, out } => cmd_certify(&trace, &out),
    }
}

fn read_trace(path: &PathBuf) -> Vec<u8> {
    fs::read(path).unwrap_or_else(|e| {
        eprintln!("error: cannot read {}: {e}", path.display());
        std::process::exit(1);
    })
}

fn cmd_replay(trace_path: &PathBuf) {
    let bytes = read_trace(trace_path);
    match replay(&bytes) {
        Ok(ok) => {
            println!("ok: replayed {} step(s)", ok.steps_replayed);
        }
        Err(e) => {
            eprintln!("replay failed: {e}");
            std::process::exit(1);
        }
    }
}

fn cmd_certify(trace_path: &PathBuf, out_path: &PathBuf) {
    let bytes = read_trace(trace_path);

    let ok_parts = match replay(&bytes) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("replay failed: {e}");
            std::process::exit(1);
        }
    };

    let cert = match certify(&ok_parts) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("certification failed: {e}");
            std::process::exit(1);
        }
    };

    // Emit compact canonical bytes to guarantee byte-identical output across runs.
    let cert_bytes = canonical_bytes(&cert).unwrap_or_else(|e| {
        eprintln!("error: certificate serialization failed: {e}");
        std::process::exit(1);
    });

    if let Some(parent) = out_path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).unwrap_or_else(|e| {
                eprintln!("error: cannot create output directory: {e}");
                std::process::exit(1);
            });
        }
    }

    fs::write(out_path, &cert_bytes).unwrap_or_else(|e| {
        eprintln!("error: cannot write {}: {e}", out_path.display());
        std::process::exit(1);
    });

    println!("ok: certificate written to {}", out_path.display());
}
