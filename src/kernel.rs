/// StateCompiler: deterministic algebraic fold over a canonical event stream.
///
/// compile(S₀, [E₁..Eₙ]) = δ(δ(...δ(S₀, E₁)..., Eₙ₋₁), Eₙ)
///
/// transition (δ) is total — no error path. Pass 0 guarantees all events
/// reaching this layer are canonical. Invalid semantic combinations (e.g.,
/// Update on a non-existent entity) are deterministic no-ops, not errors.
use crate::codec::{encode, encode_entity_map};
use crate::event::{CompiledState, EntityRecord, EntityStatus, Event};
use crate::oracle::{chain_advance, compute_csp, state_value_hash};
use std::collections::BTreeMap;

/// Initial state: empty entity space, genesis chain hash, derived hashes.
pub fn genesis() -> CompiledState {
    let entities: BTreeMap<u64, EntityRecord> = BTreeMap::new();
    let state_hash = state_value_hash(&encode_entity_map(&entities));
    let event_chain_hash = [0u8; 32];
    let csp = compute_csp(&state_hash, &event_chain_hash);
    CompiledState { entities, state_hash, event_chain_hash, csp }
}

/// Pure total transition. Applies one event to a state and returns the successor.
/// Hash chain is always updated; state_hash only changes when entities change.
pub fn transition(mut state: CompiledState, event: &Event) -> CompiledState {
    apply_semantic(&mut state.entities, event);

    state.state_hash = state_value_hash(&encode_entity_map(&state.entities));

    let event_bytes = encode(event);
    state.event_chain_hash = chain_advance(&state.event_chain_hash, &event_bytes);

    state.csp = compute_csp(&state.state_hash, &state.event_chain_hash);
    state
}

/// Deterministic fold of a totally ordered event sequence onto an initial state.
/// Base: compile(S, []) = S
/// Step: compile(S, [E|rest]) = compile(δ(S, E), rest)
pub fn compile(initial: CompiledState, events: impl IntoIterator<Item = Event>) -> CompiledState {
    events.into_iter().fold(initial, |state, event| transition(state, &event))
}

fn apply_semantic(entities: &mut BTreeMap<u64, EntityRecord>, event: &Event) {
    match event {
        Event::Create { entity_id, kind } => {
            // Idempotent: no-op if entity already exists.
            entities.entry(*entity_id).or_insert_with(|| EntityRecord::new(*kind));
        }

        Event::Update { entity_id, field, value } => {
            // No-op on missing entity or non-Active entity.
            if let Some(rec) = entities.get_mut(entity_id) {
                if rec.status == EntityStatus::Active {
                    rec.fields.insert(*field, *value);
                }
            }
        }

        Event::Merge { target_id, source_id } => {
            // No-op on self-merge or missing entity.
            if target_id != source_id
                && entities.contains_key(target_id)
                && entities.contains_key(source_id)
            {
                let source_fields = entities[source_id].fields.clone();
                // Target fields win on conflict (ordered union: target takes precedence).
                let target = entities.get_mut(target_id).unwrap();
                for (k, v) in source_fields {
                    target.fields.entry(k).or_insert(v);
                }
                // Source is absorbed: mark merged, clear fields, link to target.
                let source = entities.get_mut(source_id).unwrap();
                source.status = EntityStatus::MergedInto;
                source.linked_id = *target_id;
                source.fields.clear();
            }
        }

        Event::Partition { entity_id, new_entity_id, partition_key } => {
            // No-op if origin missing, ids equal, or new_entity_id already taken.
            if entity_id != new_entity_id
                && entities.contains_key(entity_id)
                && !entities.contains_key(new_entity_id)
            {
                let kind = (*partition_key & 0xFFFF) as u16;
                let mut child = EntityRecord::new(kind);
                child.linked_id = *entity_id;
                entities.insert(*new_entity_id, child);
                let origin = entities.get_mut(entity_id).unwrap();
                origin.status = EntityStatus::Partitioned;
                origin.linked_id = *new_entity_id;
            }
        }

        Event::Commit { entity_id } => {
            if let Some(rec) = entities.get_mut(entity_id) {
                rec.committed = true;
            }
        }

        Event::Reject { .. } => {
            // No-op on semantic state. event_chain_hash advances in transition().
        }
    }
}
