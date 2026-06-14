use crate::replay;
use crate::vector::SpatialVector;
use sha2::{Digest, Sha256};

pub struct VectorResult {
    pub id: String,
    pub seq_commit: [u8; 32],
    pub per_vector_root: [u8; 32],
}

/// per_vector_root = SHA256("SPATIAL_VECTOR_V1\0" || id_bytes || seq_commit)
pub fn per_vector_root(id: &str, seq_commit: &[u8; 32]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(b"SPATIAL_VECTOR_V1\0");
    h.update(id.as_bytes());
    h.update(seq_commit);
    h.finalize().into()
}

/// global_root = SHA256("SPATIAL_LOCK_V1\0" || per_roots sorted by id)
/// per_roots must be provided sorted lexicographically by id.
pub fn global_root(per_roots: &[(String, [u8; 32])]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(b"SPATIAL_LOCK_V1\0");
    for (_, root) in per_roots {
        h.update(root);
    }
    h.finalize().into()
}

/// Run all vectors through replay and compute per-vector roots and global root.
/// Returns (results sorted by id, global_root_hex).
pub fn evaluate_vectors(vectors: &[SpatialVector]) -> (Vec<VectorResult>, String) {
    let mut per_roots: Vec<(String, [u8; 32])> = Vec::new();
    let mut results: Vec<VectorResult> = Vec::new();

    for v in vectors {
        let rr = replay::replay(v.initial_state.clone(), &v.events);
        let pvr = per_vector_root(&v.id, &rr.seq_commit);
        per_roots.push((v.id.clone(), pvr));
        results.push(VectorResult {
            id: v.id.clone(),
            seq_commit: rr.seq_commit,
            per_vector_root: pvr,
        });
    }

    // per_roots already sorted by id (load_vectors_from_dir sorts by id)
    let gr = global_root(&per_roots);
    (results, hex::encode(gr))
}
