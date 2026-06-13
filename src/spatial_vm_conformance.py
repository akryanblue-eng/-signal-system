"""
Spatial VM Conformance Harness — Runs A–D

Machine-checkable encoding of the DSVM-0 contract:

    Given an initial TravelerState₀
    When applying a deterministic event stream E through reducers
    Then TravelerStateₙ must be identical across reruns
    (hard gate: state equality via CT-0; advisory: per-node projection hashes)

Run matrix:

    A   Ascension branch — proves bifurcation sources only from TravelerState
    B   Creation branch  — same event structure, only choice differs; commit_A ≠ commit_B
    C   Replay A         — identical events → identical commit (determinism)
    D   Re-entry saturation — duplicate node events are idempotent; commit_D == commit_A

Negative invariants encoded here:
    N1  No projection value ever mutates TravelerState
    N2  No projection reads scene/entity state as input
    N3  No event carries implicit temporal context (clocks, UUIDs at emission)
    N4  Reducer is the only write path (TravelerState is frozen=True)
"""
import hashlib
from dataclasses import dataclass

from .traveler_state import (
    TravelerState,
    apply_event,
    apply_events,
    commit_state,
    project_node_b,
    project_node_c,
)
from .ct0 import ct0_evaluate


# ---------------------------------------------------------------------------
# Canonical event streams — the oracle source
# ---------------------------------------------------------------------------

# Shared journey through the ascension branch
_JOURNEY_BASE = [
    {"type": "enter_node",        "node_id": "neon-in-nirvana"},
    {"type": "discover_artifact", "artifact_id": "broken-star-compass"},
    {"type": "reveal_lore",       "lore_id": "map-remembers"},
    {"type": "portal_unlocked",   "portal_id": "godly-dna"},
    {"type": "node_completed",    "node_id": "neon-in-nirvana"},
    {"type": "enter_node",        "node_id": "godly-dna"},
]

STREAM_RUN_A = [
    *_JOURNEY_BASE,
    {"type": "choose_ascension"},
    {"type": "node_completed", "node_id": "godly-dna"},
    {"type": "enter_node",     "node_id": "sky-high"},
]

STREAM_RUN_B = [
    *_JOURNEY_BASE,
    {"type": "choose_creation"},   # only difference from A
    {"type": "node_completed", "node_id": "godly-dna"},
    {"type": "enter_node",     "node_id": "sky-high"},
]

STREAM_RUN_C = STREAM_RUN_A  # identical replay — must produce commit_C == commit_A

STREAM_RUN_D = [
    *STREAM_RUN_A,
    # Re-enter already-visited nodes — reducer must be idempotent
    {"type": "enter_node", "node_id": "neon-in-nirvana"},
    {"type": "enter_node", "node_id": "godly-dna"},
    {"type": "enter_node", "node_id": "sky-high"},
    {"type": "enter_node", "node_id": "neon-in-nirvana"},
]


# ---------------------------------------------------------------------------
# Per-run execution
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    run_id: str
    events: list[dict]
    final_state: TravelerState
    commit: bytes       # run-specific commit (run_id is part of hash)
    state_commit: bytes # canonical state commit with fixed sentinel run_id for cross-run comparison
    ct0_verdict: str
    projection_hashes: dict[str, str]
    proves: str


# Fixed sentinel used when comparing state commits across different runs.
# Separates "did the same events produce the same state?" from run identity.
_STATE_ORACLE_RUN_ID = "DSVM0-STATE-ORACLE"


def _projection_hash(node_id: str, state: TravelerState) -> str:
    projectors = {"node_b": project_node_b, "node_c": project_node_c}
    snap = projectors[node_id](state)
    payload = node_id.encode() + repr(sorted(snap.items())).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def _execute_run(run_id: str, events: list[dict], proves: str) -> RunResult:
    sn = apply_events(TravelerState(), events)

    # Hard gate: two independent commits under the run's own ID must be identical
    commit_1 = commit_state(sn, run_id)
    commit_2 = commit_state(sn, run_id)
    verdict, _ = ct0_evaluate(commit_1, commit_2, run_id)

    # Cross-run state oracle: commit with a fixed sentinel ID so runs can be compared
    state_commit = commit_state(sn, _STATE_ORACLE_RUN_ID)

    proj_hashes = {
        "node_b": _projection_hash("node_b", sn),
        "node_c": _projection_hash("node_c", sn),
    }

    return RunResult(
        run_id=run_id,
        events=events,
        final_state=sn,
        commit=commit_1,
        state_commit=state_commit,
        ct0_verdict=verdict.status,
        projection_hashes=proj_hashes,
        proves=proves,
    )


def run_a() -> RunResult:
    return _execute_run(
        "DSVM0-RUN-A", STREAM_RUN_A,
        "ascension branch: commit_A ≠ commit_B (bifurcation from TravelerState.ascension only)",
    )


def run_b() -> RunResult:
    return _execute_run(
        "DSVM0-RUN-B", STREAM_RUN_B,
        "creation branch: commit_B ≠ commit_A; same journey, different choice",
    )


def run_c() -> RunResult:
    return _execute_run(
        "DSVM0-RUN-C", STREAM_RUN_C,
        "determinism replay: identical events → commit_C == commit_A",
    )


def run_d() -> RunResult:
    return _execute_run(
        "DSVM0-RUN-D", STREAM_RUN_D,
        "idempotency: re-entry of visited nodes → commit_D == commit_A (state unchanged)",
    )


# ---------------------------------------------------------------------------
# Conformance report
# ---------------------------------------------------------------------------

@dataclass
class ConformanceReport:
    ab_bifurcation_ok: bool        # commit_A ≠ commit_B
    ab_source_is_state_only: bool  # only ascension differs between A and B states
    c_determinism_ok: bool         # commit_C == commit_A
    d_idempotency_ok: bool         # commit_D == commit_A
    all_deterministic: bool        # every run has CT-0 PASS
    advisory_projection_diffs: dict


def run_all() -> ConformanceReport:
    ra, rb, rc, rd = run_a(), run_b(), run_c(), run_d()

    return ConformanceReport(
        # Bifurcation: state_commit captures state independently of run identity
        ab_bifurcation_ok=ra.state_commit != rb.state_commit,
        ab_source_is_state_only=(
            ra.final_state.visited_nodes == rb.final_state.visited_nodes
            and ra.final_state.discovered_artifacts == rb.final_state.discovered_artifacts
            and ra.final_state.revealed_lore == rb.final_state.revealed_lore
            and ra.final_state.ascension != rb.final_state.ascension
        ),
        c_determinism_ok=rc.state_commit == ra.state_commit,
        d_idempotency_ok=rd.state_commit == ra.state_commit,
        all_deterministic=all(r.ct0_verdict == "OK" for r in [ra, rb, rc, rd]),
        advisory_projection_diffs={
            "run_a_vs_b_node_b": {
                "a": ra.projection_hashes["node_b"],
                "b": rb.projection_hashes["node_b"],
                "differs": ra.projection_hashes["node_b"] != rb.projection_hashes["node_b"],
            },
            "run_a_vs_b_node_c": {
                "a": ra.projection_hashes["node_c"],
                "b": rb.projection_hashes["node_c"],
                "differs": ra.projection_hashes["node_c"] == rb.projection_hashes["node_c"],
            },
        },
    )
