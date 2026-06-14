use serde_json::Value;

pub enum CompareResult {
    Match {
        ri0_commit: String,
    },
    CommitMismatch {
        field: String,
        key: String,
        value_a: String,
        value_b: String,
    },
    StructureMismatch {
        reason: String,
    },
}

pub fn compare_logs(
    id_a: &str,
    commit_a: &str,
    fields_a: &[Value],
    id_b: &str,
    commit_b: &str,
    fields_b: &[Value],
) -> CompareResult {
    if commit_a == commit_b {
        return CompareResult::Match { ri0_commit: commit_a.to_string() };
    }

    if fields_a.len() != fields_b.len() {
        return CompareResult::StructureMismatch {
            reason: format!(
                "{id_a} has {} fields, {id_b} has {}",
                fields_a.len(),
                fields_b.len()
            ),
        };
    }

    // Walk fields in RI-0 encoding order; find first byte-level divergence.
    for (fa, fb) in fields_a.iter().zip(fields_b.iter()) {
        let name_a = fa["field"].as_str().unwrap_or("?");
        let name_b = fb["field"].as_str().unwrap_or("?");

        if name_a != name_b {
            return CompareResult::StructureMismatch {
                reason: format!("field order differs: {name_a} vs {name_b}"),
            };
        }

        // length_prefix (where present)
        if fa.get("length_prefix") != fb.get("length_prefix") {
            return CompareResult::CommitMismatch {
                field: name_a.to_string(),
                key: "length_prefix".to_string(),
                value_a: json_str(&fa["length_prefix"]),
                value_b: json_str(&fb["length_prefix"]),
            };
        }

        // payload bytes
        if fa["bytes"] != fb["bytes"] {
            let detail = if name_a == "signals" {
                // Try to narrow to dedup result or signal step
                if fa["after_dedup"] != fb["after_dedup"] {
                    "after_dedup".to_string()
                } else {
                    "bytes (post-dedup encoding)".to_string()
                }
            } else {
                "bytes".to_string()
            };
            return CompareResult::CommitMismatch {
                field: name_a.to_string(),
                key: detail,
                value_a: json_str(&fa["bytes"]),
                value_b: json_str(&fb["bytes"]),
            };
        }
    }

    // All fields identical but commits differ — shouldn't happen with correct SHA256
    CompareResult::StructureMismatch {
        reason: "all field bytes match but ri0_commit differs — SHA256 implementation bug"
            .to_string(),
    }
}

fn json_str(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}
