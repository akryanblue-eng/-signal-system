use sha2::{Digest, Sha256};

/// Per-vector root: domain-separated hash binding vector ID to its RI-0 commit.
/// Changing any vector's inputs changes only that vector's root, not others.
pub fn per_vector_root(id: &str, ri0_commit: &[u8; 32]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(b"GOLDEN_VECTOR_V1\0");
    h.update(id.as_bytes());
    h.update(ri0_commit);
    h.finalize().into()
}

/// Global root: deterministic aggregate over all per-vector roots (sorted by ID).
/// Changing any single vector breaks the global root without masking which vector drifted.
pub fn global_root(per_roots: &[(String, [u8; 32])]) -> [u8; 32] {
    // Caller must provide per_roots sorted by id — enforced via load_vectors_from_dir ordering.
    let mut h = Sha256::new();
    h.update(b"GOLDEN_LOCK_V1\0");
    for (_, root) in per_roots {
        h.update(root);
    }
    h.finalize().into()
}

#[derive(Debug)]
pub struct VectorResult {
    pub id: String,
    pub ri0_commit: String,
    pub per_root: String,
}

pub fn evaluate_vectors(
    vectors: &[crate::vector::GoldenVector],
) -> (Vec<VectorResult>, String) {
    let mut per_roots: Vec<(String, [u8; 32])> = Vec::new();
    let mut results: Vec<VectorResult> = Vec::new();

    for v in vectors {
        let witness = v.to_witness();
        let commit = dsvm_core::ri0_replay(&witness);
        let pvr = per_vector_root(&v.id, &commit);
        results.push(VectorResult {
            id: v.id.clone(),
            ri0_commit: hex::encode(commit),
            per_root: hex::encode(pvr),
        });
        per_roots.push((v.id.clone(), pvr));
    }

    // per_roots already sorted by ID (vectors sorted in load_vectors_from_dir)
    let gr = global_root(&per_roots);
    (results, hex::encode(gr))
}
