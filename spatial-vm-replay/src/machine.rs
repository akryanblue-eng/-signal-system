use crate::event::SpatialEvent;
use crate::state::TravelerState;

/// Pure state transition function. Takes ownership of state, returns new state.
/// All transitions are total (no partial/error states at this layer).
/// node_completed and portal_unlocked have no effect on tracked TravelerState fields.
pub fn apply(mut state: TravelerState, event: &SpatialEvent) -> TravelerState {
    match event {
        SpatialEvent::EnterNode { node_id } => {
            state.visited_nodes.insert(node_id.clone());
        }
        SpatialEvent::DiscoverArtifact { artifact_id } => {
            state.discovered_artifacts.insert(artifact_id.clone());
        }
        SpatialEvent::RevealLore { lore_id } => {
            state.revealed_lore.insert(lore_id.clone());
        }
        SpatialEvent::ChooseAscension => {
            state.ascension = true;
        }
        SpatialEvent::ChooseCreation => {
            state.gene_choice_locked = true;
        }
        SpatialEvent::NodeCompleted { .. } => {}
        SpatialEvent::PortalUnlocked { .. } => {}
    }
    state
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn enter_node_adds_to_visited() {
        let s = apply(TravelerState::default(), &SpatialEvent::EnterNode { node_id: "n1".into() });
        assert!(s.visited_nodes.contains("n1"));
    }

    #[test]
    fn choose_ascension_is_idempotent() {
        let s = apply(TravelerState::default(), &SpatialEvent::ChooseAscension);
        let s2 = apply(s.clone(), &SpatialEvent::ChooseAscension);
        assert_eq!(s, s2);
    }

    #[test]
    fn node_completed_has_no_effect() {
        let before = TravelerState::default();
        let after = apply(before.clone(), &SpatialEvent::NodeCompleted { node_id: "n1".into() });
        assert_eq!(before, after);
    }
}
