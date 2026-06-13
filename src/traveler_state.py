"""
TravelerState: the single evolving ledger for the spatial VM.

All world state lives here. Node projections are pure functions of this struct —
they cannot hold residue from prior navigation. commit_state() hashes into
CommitHash32 via the existing RI-0 engine.
"""
import hashlib
import struct
from dataclasses import dataclass

from .types import WitnessPacket304
from .ri0 import ri0_replay

_BUNDLE_HASH = hashlib.sha256(b"spatial-vm-v1").digest()
_VALIDATOR_PUBKEY = hashlib.sha256(b"spatial-vm-conformance-oracle").digest()
_BUNDLE_VERSION = 1


@dataclass(frozen=True)
class TravelerState:
    ascension: bool = False
    node_a_interaction_count: int = 0
    # Path-weighted memory: each visit_node_a adds 1000 // visit_number.
    # Converges toward harmonic growth (proven diminishing delta in Run D).
    convergence_score: int = 0

    def to_signals(self) -> list[tuple[str, int]]:
        return [
            ("traveler.ascension", 1 if self.ascension else 0),
            ("node_a.interaction_count", self.node_a_interaction_count),
            ("node_a.convergence_score", self.convergence_score),
        ]


def apply_event(state: TravelerState, event: dict) -> TravelerState:
    """Pure reducer: (TravelerState, event) → TravelerState. No side effects."""
    t = event["type"]
    if t == "visit_node_a":
        new_count = state.node_a_interaction_count + 1
        delta = 1000 // new_count
        return TravelerState(
            ascension=state.ascension,
            node_a_interaction_count=new_count,
            convergence_score=state.convergence_score + delta,
        )
    if t == "set_ascension":
        return TravelerState(
            ascension=bool(event["value"]),
            node_a_interaction_count=state.node_a_interaction_count,
            convergence_score=state.convergence_score,
        )
    raise ValueError(f"Unknown event type: {t!r}")


def apply_events(state: TravelerState, events: list[dict]) -> TravelerState:
    for ev in events:
        state = apply_event(state, ev)
    return state


def commit_state(state: TravelerState, run_id: str, prev_commit: bytes = bytes(32)) -> bytes:
    """
    Commit TravelerState into a CommitHash32 via RI-0.
    prev_commit chains states; use bytes(32) for the initial state.
    """
    event_stream_hash = hashlib.sha256(
        struct.pack(">I", state.node_a_interaction_count)
        + struct.pack(">?", state.ascension)
        + struct.pack(">I", state.convergence_score)
    ).digest()

    packet = WitnessPacket304(
        run_id=run_id,
        prev_state_bytes=prev_commit,
        frozen_batch_bytes=event_stream_hash,
        bundle_hash=_BUNDLE_HASH,
        bundle_version=_BUNDLE_VERSION,
        validator_pubkey=_VALIDATOR_PUBKEY,
        signals=state.to_signals(),
    )
    return ri0_replay(packet)


# ---------------------------------------------------------------------------
# Node projection functions
# Each is a pure function of TravelerState — no hidden mutable state.
# ---------------------------------------------------------------------------

def project_node_b(state: TravelerState) -> dict:
    """Node B: ascension-sensitive. Bifurcates on traveler.ascension only."""
    return {
        "scene": "ascended" if state.ascension else "earthbound",
        "gate_open": state.ascension,
    }


def project_node_c(state: TravelerState) -> dict:
    """Node C: accumulation-sensitive. Perceptual field shifts after > 2 Node A visits."""
    return {
        "perceptual_field": (
            "heightened" if state.node_a_interaction_count > 2 else "baseline"
        ),
        "resonance_depth": state.node_a_interaction_count,
        "convergence_score": state.convergence_score,
    }
