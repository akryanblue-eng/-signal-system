"""
TravelerState: the single evolving ledger for the spatial VM.

All world state lives here. Projections are pure functions of this struct —
they cannot hold residue from prior navigation. commit_state() hashes into
CommitHash32 via RI-0.

Domain model matches the Swift TravelerState shape:

    visited_nodes         ordered tuple of entered node IDs (insertion order)
    discovered_artifacts  ordered tuple of found artifact IDs (deduped)
    revealed_lore         ordered tuple of unlocked lore IDs (deduped)
    ascension             branch-choice flag (True = ascension, False = creation)

Derived property (not stored, always recomputed from visited_nodes):
    convergence_score     path-weighted memory: Σ(1000 // i) for i in 1..len(visited_nodes)
                          Harmonic-like; each node contributes strictly less than the last.
"""
import hashlib
from dataclasses import dataclass

from .types import WitnessPacket304
from .ri0 import ri0_replay

_BUNDLE_HASH = hashlib.sha256(b"spatial-vm-v1").digest()
_VALIDATOR_PUBKEY = hashlib.sha256(b"spatial-vm-conformance-oracle").digest()
_BUNDLE_VERSION = 1


@dataclass(frozen=True)
class TravelerState:
    visited_nodes: tuple[str, ...] = ()
    discovered_artifacts: tuple[str, ...] = ()
    revealed_lore: tuple[str, ...] = ()
    ascension: bool = False

    @property
    def convergence_score(self) -> int:
        return sum(1000 // i for i in range(1, len(self.visited_nodes) + 1))

    def to_signals(self) -> list[tuple[str, int]]:
        def _seq_hash(seq: tuple[str, ...]) -> int:
            payload = "||".join(seq).encode("utf-8")
            # Truncate to 60 bits so it always fits in a signed int64 signal slot.
            return int(hashlib.sha256(payload).hexdigest()[:15], 16)

        return [
            ("traveler.ascension",           1 if self.ascension else 0),
            ("traveler.visited_count",        len(self.visited_nodes)),
            ("traveler.visited_hash",         _seq_hash(self.visited_nodes)),
            ("traveler.artifacts_count",      len(self.discovered_artifacts)),
            ("traveler.artifacts_hash",       _seq_hash(self.discovered_artifacts)),
            ("traveler.lore_count",           len(self.revealed_lore)),
            ("traveler.lore_hash",            _seq_hash(self.revealed_lore)),
            ("traveler.convergence_score",    self.convergence_score),
        ]


def apply_event(state: TravelerState, event: dict) -> TravelerState:
    """Pure reducer: (TravelerState, event) → TravelerState. No side effects."""
    t = event["type"]

    if t == "enter_node":
        nid = event["node_id"]
        if nid in state.visited_nodes:
            return state
        return TravelerState(
            visited_nodes=state.visited_nodes + (nid,),
            discovered_artifacts=state.discovered_artifacts,
            revealed_lore=state.revealed_lore,
            ascension=state.ascension,
        )

    if t == "discover_artifact":
        aid = event["artifact_id"]
        if aid in state.discovered_artifacts:
            return state
        return TravelerState(
            visited_nodes=state.visited_nodes,
            discovered_artifacts=state.discovered_artifacts + (aid,),
            revealed_lore=state.revealed_lore,
            ascension=state.ascension,
        )

    if t == "reveal_lore":
        lid = event["lore_id"]
        if lid in state.revealed_lore:
            return state
        return TravelerState(
            visited_nodes=state.visited_nodes,
            discovered_artifacts=state.discovered_artifacts,
            revealed_lore=state.revealed_lore + (lid,),
            ascension=state.ascension,
        )

    if t == "choose_ascension":
        return TravelerState(
            visited_nodes=state.visited_nodes,
            discovered_artifacts=state.discovered_artifacts,
            revealed_lore=state.revealed_lore,
            ascension=True,
        )

    if t == "choose_creation":
        return TravelerState(
            visited_nodes=state.visited_nodes,
            discovered_artifacts=state.discovered_artifacts,
            revealed_lore=state.revealed_lore,
            ascension=False,
        )

    # No-ops: exist for event-bus parity with the Swift QSEvent enum.
    # These events travel through the rule layer but produce no state mutation.
    if t in ("node_completed", "portal_unlocked"):
        return state

    raise ValueError(f"Unknown event type: {t!r}")


def apply_events(state: TravelerState, events: list[dict]) -> TravelerState:
    for ev in events:
        state = apply_event(state, ev)
    return state


def commit_state(state: TravelerState, run_id: str, prev_commit: bytes = bytes(32)) -> bytes:
    """Hash TravelerState into CommitHash32 via RI-0."""
    packet = WitnessPacket304(
        run_id=run_id,
        prev_state_bytes=prev_commit,
        frozen_batch_bytes=bytes(32),
        bundle_hash=_BUNDLE_HASH,
        bundle_version=_BUNDLE_VERSION,
        validator_pubkey=_VALIDATOR_PUBKEY,
        signals=state.to_signals(),
    )
    return ri0_replay(packet)


# ---------------------------------------------------------------------------
# Node projection functions — pure functions of TravelerState
# ---------------------------------------------------------------------------

def project_node_b(state: TravelerState) -> dict:
    """Node B: ascension-sensitive. Scene bifurcates on traveler.ascension only."""
    return {
        "scene": "ascended" if state.ascension else "earthbound",
        "gate_open": state.ascension,
        "visited_count": len(state.visited_nodes),
    }


def project_node_c(state: TravelerState) -> dict:
    """Node C: accumulation-sensitive. Perceptual field deepens with more node visits."""
    depth = len(state.visited_nodes)
    return {
        "perceptual_field": "heightened" if depth > 2 else "baseline",
        "resonance_depth": depth,
        "convergence_score": state.convergence_score,
        "artifact_awareness": len(state.discovered_artifacts),
    }
