use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;

// BTreeSet guarantees lexicographic iteration order — canonical_commit is
// fully determined by SET MEMBERSHIP, not insertion order. Two event streams
// that visit the same nodes in different orders produce the same final-state
// commit but different seq_commits (because intermediate commits differ).

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct TravelerState {
    #[serde(default)]
    pub visited_nodes: BTreeSet<String>,
    #[serde(default)]
    pub discovered_artifacts: BTreeSet<String>,
    #[serde(default)]
    pub revealed_lore: BTreeSet<String>,
    #[serde(default)]
    pub ascension: bool,
    #[serde(default)]
    pub gene_choice_locked: bool,
}

impl TravelerState {
    /// Canonical commit: domain-separated, field-ordered, lexicographically-sorted sets.
    /// No serde in this path — all encoding is manual and deterministic.
    pub fn canonical_commit(&self) -> [u8; 32] {
        let mut h = Sha256::new();
        h.update(b"DSVM0:STATE:v1\0");
        encode_set(&mut h, &self.visited_nodes);
        encode_set(&mut h, &self.discovered_artifacts);
        encode_set(&mut h, &self.revealed_lore);
        h.update([self.ascension as u8]);
        h.update([self.gene_choice_locked as u8]);
        h.finalize().into()
    }
}

fn encode_set(h: &mut Sha256, set: &BTreeSet<String>) {
    // u32-BE(count) || for each s in lex order: u16-BE(len) || utf8
    h.update((set.len() as u32).to_be_bytes());
    for s in set {
        let b = s.as_bytes();
        h.update((b.len() as u16).to_be_bytes());
        h.update(b);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_state_is_stable() {
        let s = TravelerState::default();
        assert_eq!(s.canonical_commit(), s.canonical_commit());
    }

    #[test]
    fn set_membership_not_insertion_order() {
        let mut a = TravelerState::default();
        a.visited_nodes.insert("A".into());
        a.visited_nodes.insert("B".into());

        let mut b = TravelerState::default();
        b.visited_nodes.insert("B".into());
        b.visited_nodes.insert("A".into());

        // BTreeSet: same members → same commit regardless of insertion order
        assert_eq!(a.canonical_commit(), b.canonical_commit());
    }

    #[test]
    fn different_members_different_commit() {
        let mut a = TravelerState::default();
        a.visited_nodes.insert("A".into());

        let mut b = TravelerState::default();
        b.visited_nodes.insert("B".into());

        assert_ne!(a.canonical_commit(), b.canonical_commit());
    }

    #[test]
    fn boolean_fields_affect_commit() {
        let base = TravelerState::default();
        let mut with_ascension = base.clone();
        with_ascension.ascension = true;
        assert_ne!(base.canonical_commit(), with_ascension.canonical_commit());
    }
}
