/// Pass 2 — Canonical Index + Ordering Engine.
///
/// Defines the single global ordering function  I: E → ℕ.
///
///   CCI(E) = LexSortKey(tick_be, node_id, sha256(canonical_bytes))
///
/// CCI is purely computed from explicit canonical inputs — no wall clock,
/// no arrival time, no thread scheduling, no batch grouping. The ordering
/// is therefore identical across OS, architecture, runtime, and concurrency
/// model, and stable under re-derivation from the same canonical bytes.
///
/// This layer converts distributed input chaos into a single deterministic
/// linear event sequence before it reaches the StateCompiler.
use sha2::{Digest, Sha256};

/// Canonical Certificate Index: the only allowed source of temporal ordering.
///
/// 56-byte lexicographic composite key layout:
///   [tick: 8 bytes BE][node_id: 16 bytes][event_hash: 32 bytes]
///
/// Comparison is byte-lexicographic (Ord derives this for [u8; N]):
///   Primary:   tick (BE)    — earlier tick ≺ later tick
///   Secondary: node_id      — deterministic tie-break across nodes
///   Tertiary:  event_hash   — SHA-256 collision-resistant final tie-break
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Cci([u8; 56]);

impl Cci {
    /// Purely compute CCI from canonical inputs. No mutable state.
    pub fn compute(tick: u64, node_id: [u8; 16], event_hash: [u8; 32]) -> Self {
        let mut key = [0u8; 56];
        key[0..8].copy_from_slice(&tick.to_be_bytes()); // BE so lex order == numeric order
        key[8..24].copy_from_slice(&node_id);
        key[24..56].copy_from_slice(&event_hash);
        Self(key)
    }

    pub fn as_bytes(&self) -> &[u8; 56] {
        &self.0
    }

    pub fn tick(&self) -> u64 {
        u64::from_be_bytes(self.0[0..8].try_into().unwrap())
    }

    pub fn node_id(&self) -> [u8; 16] {
        self.0[8..24].try_into().unwrap()
    }

    pub fn event_hash(&self) -> [u8; 32] {
        self.0[24..56].try_into().unwrap()
    }
}

/// SHA-256 of canonical event bytes (Pass 0 encoding).
/// This is the hash component of CCI — distinct from the BLAKE3 chain in oracle.rs.
pub fn sha256_event_hash(canonical_bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(canonical_bytes).into()
}

/// Fully indexed event — a derivation artifact of the ordering layer only.
/// Not stored as mutable state; always recomputed from canonical inputs.
#[derive(Debug, Clone)]
pub struct IndexedEvent {
    pub cci: Cci,
    pub event_hash: [u8; 32],
    pub node_id: [u8; 16],
    pub tick: u64,
    pub canonical_bytes: Vec<u8>, // Pass 0 encoding
}

impl IndexedEvent {
    /// Derive from canonical bytes + explicit tick and node_id.
    /// tick and node_id are transport-layer metadata; canonical_bytes are event content.
    pub fn derive(canonical_bytes: Vec<u8>, tick: u64, node_id: [u8; 16]) -> Self {
        let event_hash = sha256_event_hash(&canonical_bytes);
        let cci = Cci::compute(tick, node_id, event_hash);
        Self { cci, event_hash, node_id, tick, canonical_bytes }
    }
}

/// Pure total-ordering transform.
///
///   Order(ε) = sort(ε, CCI)
///
/// Input:  unordered event set (transport chaos permitted)
/// Output: strictly total-ordered sequence by CCI
pub fn order(events: impl IntoIterator<Item = IndexedEvent>) -> Vec<IndexedEvent> {
    let mut v: Vec<IndexedEvent> = events.into_iter().collect();
    v.sort_by_key(|e| e.cci);
    v
}

/// Merge two already-ordered sequences into one ordered sequence.
///
/// Partition stability invariant:
///   order(A ∪ B) = merge_ordered(order(A), order(B))
///
/// Holds for any partition of the full event set, provided both halves
/// obey Pass 1 encoding and use the identical CCI function.
pub fn merge_ordered(a: Vec<IndexedEvent>, b: Vec<IndexedEvent>) -> Vec<IndexedEvent> {
    let mut result = Vec::with_capacity(a.len() + b.len());
    let mut ai = a.into_iter().peekable();
    let mut bi = b.into_iter().peekable();
    loop {
        match (ai.peek(), bi.peek()) {
            (Some(ea), Some(eb)) => {
                if ea.cci <= eb.cci {
                    result.push(ai.next().unwrap());
                } else {
                    result.push(bi.next().unwrap());
                }
            }
            (Some(_), None) => result.extend(&mut ai),
            (None, Some(_)) => result.extend(&mut bi),
            (None, None) => break,
        }
    }
    result
}
