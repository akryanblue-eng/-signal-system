//! Hash Domain — spec §8.
//!
//! - `edge_id` for an edge `(from, type, to)` is
//!   `sha256(canon_json({"from": from, "to": to, "type": type}))`,
//!   hex-encoded.
//! - `set_hash`: sort edge_ids lexicographically as plain strings, feed
//!   their ASCII bytes into a single SHA-256 with no separator.
//! - `witness_hash`: identical but in caller-given order, never sorted.
//! - UNKNOWN-edge / waiver check (§8 last bullet).

use crate::canon_json::{canon_json, Value};
use sha2::{Digest, Sha256};

/// Compute `edge_id` for an edge `(from, type, to)` per §8: hex-encoded
/// SHA-256 of `canon_json({"from": from, "to": to, "type": type})`. The
/// object has exactly the three keys `from`, `to`, `type` (key order in
/// the source doesn't matter — canon_json sorts them anyway).
pub fn compute_edge_id(from: &str, edge_type: &str, to: &str) -> String {
    let value = Value::obj(vec![
        ("from", Value::str(from)),
        ("to", Value::str(to)),
        ("type", Value::str(edge_type)),
    ]);
    let bytes = canon_json(&value);
    let digest = Sha256::digest(&bytes);
    hex_encode(&digest)
}

/// `set_hash` of a collection of edge_ids (§8): sort as plain strings
/// (ordinary lexicographic order), then feed each one's ASCII bytes into
/// a single SHA-256 hash, in sorted order, with no separator. Output is
/// the hex digest.
///
/// "Ordinary lexicographic order" for the edge_id strings themselves
/// (hex digest strings, hence pure ASCII) is implemented via Rust's
/// native `&str`/`String` `Ord`, which compares by Unicode scalar value
/// / UTF-8 byte sequence -- for an all-ASCII-hex-digit string this is
/// identical to byte-order, codepoint-order, AND UTF-16-code-unit-order,
/// so there is no ambiguity analogous to canon_json's object-key
/// ordering question here (see QUESTIONS.md Q2, which is specific to
/// canon_json object keys, not this hash-domain string sort).
pub fn compute_set_hash<S: AsRef<str>>(edge_ids: &[S]) -> String {
    let mut sorted: Vec<&str> = edge_ids.iter().map(|s| s.as_ref()).collect();
    sorted.sort();
    hash_concat(&sorted)
}

/// `witness_hash` of a sequence of edge_ids (§8): identical to set_hash
/// except fed into the hash in exactly the order given by the caller --
/// never sorted or otherwise reordered.
pub fn compute_witness_hash<S: AsRef<str>>(edge_ids: &[S]) -> String {
    let refs: Vec<&str> = edge_ids.iter().map(|s| s.as_ref()).collect();
    hash_concat(&refs)
}

/// Feed each string's ASCII bytes into a single SHA-256, in the given
/// order, with no separator between them, and return the hex digest.
fn hash_concat(strings: &[&str]) -> String {
    let mut hasher = Sha256::new();
    for s in strings {
        hasher.update(s.as_bytes());
    }
    let digest = hasher.finalize();
    hex_encode(&digest)
}

fn hex_encode(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{:02x}", b));
    }
    s
}

/// A single edge `(from, type, to)`, as used by [`check_no_unknown_edges`].
#[derive(Debug, Clone)]
pub struct Edge {
    pub from: String,
    pub edge_type: String,
    pub to: String,
}

/// §8's UNKNOWN-edge / waiver check: a collection of edges contains no
/// un-waived UNKNOWN edges if and only if, for every edge with type
/// `UNKNOWN`, that edge's edge_id appears in the caller-supplied
/// waived-edge-id set. Edges that are not type `UNKNOWN` never require
/// waiving. Returns `true` if the collection passes (no un-waived
/// UNKNOWN edges), `false` otherwise.
pub fn check_no_unknown_edges(edges: &[Edge], waived_edge_ids: &[String]) -> bool {
    let waived: std::collections::HashSet<&str> =
        waived_edge_ids.iter().map(|s| s.as_str()).collect();
    for edge in edges {
        if edge.edge_type == "UNKNOWN" {
            let id = compute_edge_id(&edge.from, &edge.edge_type, &edge.to);
            if !waived.contains(id.as_str()) {
                return false;
            }
        }
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn edge_id_is_64_char_lowercase_hex() {
        let id = compute_edge_id("A", "IMPORTS", "B");
        assert_eq!(id.len(), 64);
        assert!(id
            .chars()
            .all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase()));
    }

    #[test]
    fn edge_id_deterministic_and_order_independent_of_struct_field_order() {
        // Calling with the same logical (from, type, to) always gives
        // the same id, regardless of how we constructed the call.
        let id1 = compute_edge_id("A", "IMPORTS", "B");
        let id2 = compute_edge_id("A", "IMPORTS", "B");
        assert_eq!(id1, id2);
    }

    #[test]
    fn edge_id_distinguishes_from_to_type() {
        let id_ab = compute_edge_id("A", "IMPORTS", "B");
        let id_ba = compute_edge_id("B", "IMPORTS", "A");
        let id_different_type = compute_edge_id("A", "CALLS", "B");
        assert_ne!(id_ab, id_ba);
        assert_ne!(id_ab, id_different_type);
    }

    #[test]
    fn edge_id_matches_hand_computed_sha256() {
        // canon_json({"from":"A","to":"B","type":"IMPORTS"}) sorted keys
        // from,to,type -> {"from":"A","to":"B","type":"IMPORTS"}
        let expected_json = r#"{"from":"A","to":"B","type":"IMPORTS"}"#;
        let digest = Sha256::digest(expected_json.as_bytes());
        let expected_hex = hex_encode(&digest);
        assert_eq!(compute_edge_id("A", "IMPORTS", "B"), expected_hex);
    }

    #[test]
    fn set_hash_is_order_independent() {
        let ids_a = vec!["bbb".to_string(), "aaa".to_string(), "ccc".to_string()];
        let ids_b = vec!["ccc".to_string(), "aaa".to_string(), "bbb".to_string()];
        assert_eq!(compute_set_hash(&ids_a), compute_set_hash(&ids_b));
    }

    #[test]
    fn set_hash_matches_hand_computed_sorted_concat() {
        let ids = vec!["bbb".to_string(), "aaa".to_string()];
        // sorted: aaa, bbb -> concat "aaabbb"
        let digest = Sha256::digest(b"aaabbb");
        let expected = hex_encode(&digest);
        assert_eq!(compute_set_hash(&ids), expected);
    }

    #[test]
    fn witness_hash_is_order_dependent() {
        let ids_a = vec!["bbb".to_string(), "aaa".to_string()];
        let ids_b = vec!["aaa".to_string(), "bbb".to_string()];
        assert_ne!(compute_witness_hash(&ids_a), compute_witness_hash(&ids_b));
    }

    #[test]
    fn witness_hash_matches_hand_computed_caller_order_concat() {
        let ids = vec!["bbb".to_string(), "aaa".to_string()];
        // caller order: bbb, aaa -> concat "bbbaaa" (NOT sorted)
        let digest = Sha256::digest(b"bbbaaa");
        let expected = hex_encode(&digest);
        assert_eq!(compute_witness_hash(&ids), expected);
    }

    #[test]
    fn set_hash_and_witness_hash_agree_when_input_already_sorted() {
        let ids = vec!["aaa".to_string(), "bbb".to_string(), "ccc".to_string()];
        assert_eq!(compute_set_hash(&ids), compute_witness_hash(&ids));
    }

    #[test]
    fn set_hash_empty_collection() {
        let ids: Vec<String> = vec![];
        let digest = Sha256::digest(b"");
        let expected = hex_encode(&digest);
        assert_eq!(compute_set_hash(&ids), expected);
    }

    #[test]
    fn no_unknown_edges_passes_when_none_are_unknown() {
        let edges = vec![
            Edge {
                from: "A".into(),
                edge_type: "IMPORTS".into(),
                to: "B".into(),
            },
            Edge {
                from: "B".into(),
                edge_type: "CALLS".into(),
                to: "C".into(),
            },
        ];
        assert!(check_no_unknown_edges(&edges, &[]));
    }

    #[test]
    fn unwaived_unknown_edge_fails() {
        let edges = vec![Edge {
            from: "A".into(),
            edge_type: "UNKNOWN".into(),
            to: "B".into(),
        }];
        assert!(!check_no_unknown_edges(&edges, &[]));
    }

    #[test]
    fn waived_unknown_edge_passes() {
        let edge = Edge {
            from: "A".into(),
            edge_type: "UNKNOWN".into(),
            to: "B".into(),
        };
        let id = compute_edge_id(&edge.from, &edge.edge_type, &edge.to);
        assert!(check_no_unknown_edges(&[edge], &[id]));
    }

    #[test]
    fn one_waived_one_not_fails_overall() {
        let edge1 = Edge {
            from: "A".into(),
            edge_type: "UNKNOWN".into(),
            to: "B".into(),
        };
        let edge2 = Edge {
            from: "C".into(),
            edge_type: "UNKNOWN".into(),
            to: "D".into(),
        };
        let id1 = compute_edge_id(&edge1.from, &edge1.edge_type, &edge1.to);
        // Only edge1's id is waived; edge2 is not.
        assert!(!check_no_unknown_edges(&[edge1, edge2], &[id1]));
    }

    #[test]
    fn waiving_an_unrelated_id_does_not_help() {
        let edge = Edge {
            from: "A".into(),
            edge_type: "UNKNOWN".into(),
            to: "B".into(),
        };
        assert!(!check_no_unknown_edges(&[edge], &["deadbeef".to_string()]));
    }

    #[test]
    fn empty_edge_collection_passes_trivially() {
        assert!(check_no_unknown_edges(&[], &[]));
    }
}
