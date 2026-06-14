mod json_gen;
mod manifest;
mod normalize;
mod rust_gen;
mod schema;
mod swift;
mod validate;

use clap::{Parser, Subcommand};
use std::fs;

#[derive(Parser)]
#[command(name = "schema-compiler", about = "DSVM-0 Schema Compiler v1")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    #[command(about = "Compile schema registry to all targets")]
    Build {
        #[arg(short, long)]
        input: String,
        #[arg(short, long)]
        output_dir: String,
    },
}

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Build { input, output_dir } => {
            let schema_json =
                fs::read_to_string(&input).expect("Failed to read schema registry");

            let schemas: Vec<schema::Schema> =
                serde_json::from_str(&schema_json).expect("Failed to parse schema registry");

            validate::validate(&schemas).expect("Schema validation failed");

            let normalized = normalize::normalize(schemas);

            let swift = swift::emit_swift(&normalized);
            let rust = rust_gen::emit_rust(&normalized);
            let json = json_gen::emit_json(&normalized);
            let mf = manifest::Manifest::new(&swift, &rust);

            for dir in &[
                format!("{output_dir}/swift"),
                format!("{output_dir}/rust"),
                format!("{output_dir}/json"),
                format!("{output_dir}/ct0"),
            ] {
                fs::create_dir_all(dir).expect("Failed to create output dir");
            }

            fs::write(format!("{output_dir}/swift/QSEvent.swift"), &swift)
                .expect("Failed to write Swift");
            fs::write(format!("{output_dir}/rust/qsevent.rs"), &rust)
                .expect("Failed to write Rust");
            fs::write(format!("{output_dir}/json/events.schema.json"), &json)
                .expect("Failed to write JSON");
            fs::write(format!("{output_dir}/ct0/event_manifest.json"), mf.to_json())
                .expect("Failed to write manifest");

            println!("Schema Compiler v1 complete");
            println!("  Swift: {output_dir}/swift/QSEvent.swift");
            println!("  Rust:  {output_dir}/rust/qsevent.rs");
            println!("  JSON:  {output_dir}/json/events.schema.json");
            println!("  Manifest: {output_dir}/ct0/event_manifest.json");
            println!("  Combined hash: {}", mf.combined_hash);
        }
    }
}
