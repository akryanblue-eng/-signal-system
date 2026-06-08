//! DivergenceDetector -- typed equivalence lattice over CompiledState pairs.
//!
//! Equality is byte-level over canonical state (encode_compiled_state).
//! Mismatch types are derived from structural projections, never from inference.
//!
//! The divergence lattice is a diamond: CONVERGED is the bottom, FULL is the top,
//! CHAIN_ONLY and SEMANTIC are incomparable intermediate nodes. Their join is FULL;
//! their meet is CONVERGED.
use crate::codec::encode_compiled_state;
use crate::event::{CompiledState, EntityRecord, EntityStatus};
use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet};

/// Two-dimensional divergence level.
/// `chain`: event_chain_hash differs.
/// `state`: state_hash differs (entity semantic state differs).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DivergenceLevel {
    pub chain: bool,
    pub state: bool,
}

impl DivergenceLevel {
    pub const CONVERGED:  Self = Self { chain: false, state: false };
    pub const CHAIN_ONLY: Self = Self { chain: true,  state: false };
    pub const SEMANTIC:   Self = Self { chain: false, state: true  };
    pub const FULL:       Self = Self { chain: true,  state: true  };

    pub fn is_converged(&self) -> bool { !self.chain && !self.state }

    /// Lattice join: least upper bound (most diverged that subsumes both).
    pub fn join(self, other: Self) -> Self {
        Self { chain: self.chain || other.chain, state: self.state || other.state }
    }

    /// Lattice meet: greatest lower bound (least diverged common ancestor).
    pub fn meet(self, other: Self) -> Self {
        Self { chain: self.chain && other.chain, state: self.state && other.state }
    }
}

/// Partial order: `a <= b` iff `a` is subsumed by `b` (b diverges at least as much).
/// `ChainOnly` and `Semantic` are incomparable -- `partial_cmp` returns `None`.
impl PartialOrd for DivergenceLevel {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        // a <= b iff each divergence dimension of a is also set in b
        let le = (!self.chain || other.chain) && (!self.state || other.state);
        let ge = (!other.chain || self.chain) && (!other.state || self.state);
        match (le, ge) {
            (true,  true)  => Some(Ordering::Equal),
            (true,  false) => Some(Ordering::Less),
            (false, true)  => Some(Ordering::Greater),
            (false, false) => None,
        }
    }
}

/// A single structural projection mismatch between two states.
/// All values are read directly from state fields -- no derivation or inference.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Mismatch {
    /// event_chain_hash fields differ.
    EventChainHash { a: [u8; 32], b: [u8; 32] },
    /// state_hash fields differ.
    StateHash { a: [u8; 32], b: [u8; 32] },
    /// Entity ID sets differ. Vectors are in ascending ID order.
    EntityPresence { only_in_a: Vec<u64>, only_in_b: Vec<u64> },
    /// Shared entity has different kind.
    EntityKind { entity_id: u64, kind_a: u16, kind_b: u16 },
    /// Shared entity has different status.
    EntityStatus { entity_id: u64, status_a: EntityStatus, status_b: EntityStatus },
    /// Shared entity has different committed bit.
    CommitBit { entity_id: u64, committed_a: bool, committed_b: bool },
    /// Shared entity has different value for a field. None = field absent.
    FieldValue { entity_id: u64, field: u8, value_a: Option<u64>, value_b: Option<u64> },
}

/// Complete divergence classification between two compiled states.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DivergenceReport {
    pub level:      DivergenceLevel,
    pub mismatches: Vec<Mismatch>,
}

/// Detect and classify all structural divergence between two compiled states.
///
/// Fast path: byte equality of full encoded state -> `Converged` immediately.
/// Otherwise: each structural projection is checked independently and exhaustively.
pub fn detect(a: &CompiledState, b: &CompiledState) -> DivergenceReport {
    if encode_compiled_state(a) == encode_compiled_state(b) {
        return DivergenceReport {
            level: DivergenceLevel::CONVERGED,
            mismatches: vec![],
        };
    }

    let mut mismatches = Vec::new();

    if a.event_chain_hash != b.event_chain_hash {
        mismatches.push(Mismatch::EventChainHash {
            a: a.event_chain_hash,
            b: b.event_chain_hash,
        });
    }
    if a.state_hash != b.state_hash {
        mismatches.push(Mismatch::StateHash { a: a.state_hash, b: b.state_hash });
        project_entity_delta(&a.entities, &b.entities, &mut mismatches);
    }

    let level = DivergenceLevel {
        chain: a.event_chain_hash != b.event_chain_hash,
        state: a.state_hash != b.state_hash,
    };

    DivergenceReport { level, mismatches }
}

fn project_entity_delta(
    a: &BTreeMap<u64, EntityRecord>,
    b: &BTreeMap<u64, EntityRecord>,
    out: &mut Vec<Mismatch>,
) {
    let ids_a: BTreeSet<u64> = a.keys().cloned().collect();
    let ids_b: BTreeSet<u64> = b.keys().cloned().collect();

    let only_in_a: Vec<u64> = ids_a.difference(&ids_b).cloned().collect();
    let only_in_b: Vec<u64> = ids_b.difference(&ids_a).cloned().collect();
    if !only_in_a.is_empty() || !only_in_b.is_empty() {
        out.push(Mismatch::EntityPresence { only_in_a, only_in_b });
    }

    for id in ids_a.intersection(&ids_b) {
        let ra = &a[id];
        let rb = &b[id];

        if ra.kind != rb.kind {
            out.push(Mismatch::EntityKind { entity_id: *id, kind_a: ra.kind, kind_b: rb.kind });
        }
        if ra.status != rb.status {
            out.push(Mismatch::EntityStatus {
                entity_id: *id,
                status_a: ra.status,
                status_b: rb.status,
            });
        }
        if ra.committed != rb.committed {
            out.push(Mismatch::CommitBit {
                entity_id: *id,
                committed_a: ra.committed,
                committed_b: rb.committed,
            });
        }

        let all_fields: BTreeSet<u8> =
            ra.fields.keys().chain(rb.fields.keys()).cloned().collect();
        for field in all_fields {
            let va = ra.fields.get(&field).copied();
            let vb = rb.fields.get(&field).copied();
            if va != vb {
                out.push(Mismatch::FieldValue {
                    entity_id: *id,
                    field,
                    value_a: va,
                    value_b: vb,
                });
            }
        }
    }
}

/// Divergence result with completeness annotation.
/// If either prefix is incomplete (C = bot), comparison is undetermined.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AnnotatedDivergence {
    Determined(DivergenceReport),
    /// Comparison deferred: one or both states are derived from an incomplete prefix.
    Undetermined,
}

/// Compare two states only when both prefixes are complete.
///
/// If C(prefix_a) = bot or C(prefix_b) = bot, returns Undetermined.
/// Prevents comparing states that may still change as more events arrive.
pub fn detect_if_complete(
    a: &CompiledState,
    a_complete: bool,
    b: &CompiledState,
    b_complete: bool,
) -> AnnotatedDivergence {
    if !a_complete || !b_complete {
        AnnotatedDivergence::Undetermined
    } else {
        AnnotatedDivergence::Determined(detect(a, b))
    }
}
