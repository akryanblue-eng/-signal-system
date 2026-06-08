//! Ingress + Completeness Layer.
//!
//! The only place in the system where partiality is explicit.
//! StagingBuffer holds unvalidated, unordered, possibly-duplicate bytes from transport.
//! build_prefix() is the gate: Pass 0 validation + C completeness check + Pass 2 ordering.
//! Nothing reaches Pass 3 (kernel::compile) without clearing all three.
use crate::codec::decode;
use crate::index::{order, sha256_event_hash, Cci, IndexedEvent};
use std::collections::{BTreeMap, BTreeSet};

// --- StagingBuffer ---

#[derive(Clone)]
struct StagingEntry {
    bytes: Vec<u8>,
    tick: u64,
    node_id: [u8; 16],
}

/// Unordered partial event container. Partiality is explicit here.
///
/// Properties: unordered, deduplicates by event_hash, accepts invalid bytes,
/// accepts duplicates (collapsed), may be incomplete (partial global view).
pub struct StagingBuffer {
    entries: BTreeMap<[u8; 32], StagingEntry>,
}

impl Default for StagingBuffer {
    fn default() -> Self { Self::new() }
}

impl StagingBuffer {
    pub fn new() -> Self {
        Self { entries: BTreeMap::new() }
    }

    /// Ingest raw bytes from transport with originating tick and node_id.
    /// Returns true if this was a new (non-duplicate) entry.
    pub fn ingest(&mut self, bytes: Vec<u8>, tick: u64, node_id: [u8; 16]) -> bool {
        let hash = sha256_event_hash(&bytes);
        if self.entries.contains_key(&hash) {
            return false;
        }
        self.entries.insert(hash, StagingEntry { bytes, tick, node_id });
        true
    }

    /// K merge operator: monotonic union. K(B1) subset-of K(B1 union B2).
    /// Existing entries are never removed or overwritten.
    pub fn merge(&mut self, other: &StagingBuffer) {
        for (hash, entry) in &other.entries {
            self.entries.entry(*hash).or_insert_with(|| entry.clone());
        }
    }

    pub fn len(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self) -> bool { self.entries.is_empty() }

    pub fn event_hashes(&self) -> impl Iterator<Item = &[u8; 32]> {
        self.entries.keys()
    }

    /// True iff both buffers contain exactly the same set of event hashes.
    pub fn hash_set_eq(&self, other: &StagingBuffer) -> bool {
        let a: BTreeSet<_> = self.entries.keys().collect();
        let b: BTreeSet<_> = other.entries.keys().collect();
        a == b
    }
}

// --- AcknowledgmentGraph ---

/// A(E, i) = true iff node i has acknowledged event E.
pub struct AcknowledgmentGraph {
    acks: BTreeMap<[u8; 32], BTreeSet<[u8; 16]>>,
    known_nodes: BTreeSet<[u8; 16]>,
}

impl AcknowledgmentGraph {
    pub fn new(nodes: impl IntoIterator<Item = [u8; 16]>) -> Self {
        Self {
            acks: BTreeMap::new(),
            known_nodes: nodes.into_iter().collect(),
        }
    }

    pub fn acknowledge(&mut self, event_hash: [u8; 32], node_id: [u8; 16]) {
        self.acks.entry(event_hash).or_default().insert(node_id);
    }

    /// C(E) = true iff all known nodes have acknowledged event_hash.
    pub fn all_acknowledged(&self, event_hash: &[u8; 32]) -> bool {
        if self.known_nodes.is_empty() {
            return true;
        }
        match self.acks.get(event_hash) {
            None => false,
            Some(acked) => self.known_nodes.is_subset(acked),
        }
    }

    pub fn ack_count(&self, event_hash: &[u8; 32]) -> usize {
        self.acks.get(event_hash).map_or(0, |s| s.len())
    }

    pub fn node_count(&self) -> usize { self.known_nodes.len() }
}

// --- CompletenessState ---

/// C predicate output.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CompletenessState {
    Complete,
    Incomplete { unacknowledged: Vec<[u8; 32]> },
}

impl CompletenessState {
    pub fn is_complete(&self) -> bool { matches!(self, Self::Complete) }
}

/// Evaluate the C predicate.
///
/// C = top iff:
///   - stable = true (caller asserts stability window delta has passed)
///   - all events acknowledged by all known nodes
pub fn check_completeness(
    event_hashes: impl IntoIterator<Item = [u8; 32]>,
    acks: &AcknowledgmentGraph,
    stable: bool,
) -> CompletenessState {
    let hashes: Vec<[u8; 32]> = event_hashes.into_iter().collect();
    if !stable {
        return CompletenessState::Incomplete { unacknowledged: hashes };
    }
    let unacknowledged: Vec<[u8; 32]> = hashes
        .into_iter()
        .filter(|h| !acks.all_acknowledged(h))
        .collect();
    if unacknowledged.is_empty() {
        CompletenessState::Complete
    } else {
        CompletenessState::Incomplete { unacknowledged }
    }
}

// --- ExecutionPrefix ---

/// Error returned when build_prefix cannot produce a valid prefix.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PrefixError {
    /// C = bot: cannot fold until all acknowledgments are received.
    Incomplete { unacknowledged_count: usize },
}

/// A valid execution prefix: Pass 0 validated, C complete, Pass 2 ordered.
/// Ready for handoff to kernel::compile (Pass 3).
pub struct ExecutionPrefix {
    /// Totally ordered valid events, ascending by CCI.
    pub events: Vec<IndexedEvent>,
    /// Max CCI of the prefix. None iff prefix is empty.
    pub frontier: Option<Cci>,
    /// Hashes of entries that failed Pass 0 decode (reported, not blocking).
    pub decode_failures: Vec<[u8; 32]>,
}

/// Build a valid execution prefix from a staging buffer.
///
/// 1. Pass 0: separate decodable from invalid entries.
/// 2. C predicate over valid entries only.
/// 3. If C = bot, return Err(Incomplete).
/// 4. Pass 2: order valid entries by CCI.
pub fn build_prefix(
    buffer: &StagingBuffer,
    acks: &AcknowledgmentGraph,
    stable: bool,
) -> Result<ExecutionPrefix, PrefixError> {
    let mut valid: Vec<(&[u8; 32], &StagingEntry)> = Vec::new();
    let mut decode_failures: Vec<[u8; 32]> = Vec::new();

    for (hash, entry) in &buffer.entries {
        if decode(&entry.bytes).is_ok() {
            valid.push((hash, entry));
        } else {
            decode_failures.push(*hash);
        }
    }

    let valid_hashes = valid.iter().map(|(h, _)| **h);
    match check_completeness(valid_hashes, acks, stable) {
        CompletenessState::Incomplete { unacknowledged } => {
            return Err(PrefixError::Incomplete {
                unacknowledged_count: unacknowledged.len(),
            });
        }
        CompletenessState::Complete => {}
    }

    let indexed: Vec<IndexedEvent> = valid
        .into_iter()
        .map(|(_, e)| IndexedEvent::derive(e.bytes.clone(), e.tick, e.node_id))
        .collect();
    let ordered = order(indexed);
    let frontier = ordered.last().map(|e| e.cci);

    Ok(ExecutionPrefix { events: ordered, frontier, decode_failures })
}

// --- KnowledgeState ---

/// K(i) = (StagingBuffer, frontier, AcknowledgmentGraph) for a single node.
pub struct KnowledgeState {
    pub node_id: [u8; 16],
    pub staging: StagingBuffer,
    pub frontier: Option<Cci>,
    pub acks: AcknowledgmentGraph,
}

impl KnowledgeState {
    pub fn new(node_id: [u8; 16], all_nodes: impl IntoIterator<Item = [u8; 16]>) -> Self {
        Self {
            node_id,
            staging: StagingBuffer::new(),
            frontier: None,
            acks: AcknowledgmentGraph::new(all_nodes),
        }
    }

    pub fn ingest(&mut self, bytes: Vec<u8>, tick: u64, origin: [u8; 16]) {
        self.staging.ingest(bytes, tick, origin);
    }

    pub fn acknowledge(&mut self, event_hash: [u8; 32], from: [u8; 16]) {
        self.acks.acknowledge(event_hash, from);
    }

    /// Try to build an execution prefix. Updates frontier on success.
    pub fn try_advance(&mut self, stable: bool) -> Result<ExecutionPrefix, PrefixError> {
        let prefix = build_prefix(&self.staging, &self.acks, stable)?;
        if let Some(f) = prefix.frontier {
            self.frontier = Some(f);
        }
        Ok(prefix)
    }
}
