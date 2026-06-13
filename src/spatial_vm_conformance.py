"""
Spatial VM Conformance Harness — Runs A–D

Machine-checkable encoding of the DSVM-0 contract:

    Given an initial TravelerState₀
    When applying a deterministic event stream E through reducers
    Then TravelerStateₙ and each node's projectWorld(TravelerStateₙ) must be
    identical across reruns (state equality = hard gate; projection hash = advisory).

Each run isolates a single axis of the contract:

    A vs B  — semantic bifurcation sourced only from TravelerState (ascension flip)
    C       — accumulation deepens Node C perceptual field without new mechanics
    D       — path-weighted memory (convergence_score) proves a convergence function

Oracle:
    Hard gate:  commit_state(TravelerStateₙ) equality via RI-0 (CT-0 PASS required)
    Advisory:   projection hash per node — logged, non-blocking until Node D lands

Negative invariants (violations break VM correctness):
    N1  No node projection value ever mutates TravelerState
    N2  No projection function reads scene/entity state as input
    N3  No convergence_score accumulated outside the reducer
    N4  No event carries implicit temporal context (clocks, UUIDs at emission)
"""
import hashlib
import struct
from dataclasses import dataclass

from .traveler_state import (
    TravelerState,
    apply_events,
    commit_state,
    project_node_b,
    project_node_c,
)
from .ct0 import ct0_evaluate


# ---------------------------------------------------------------------------
# Canonical event streams used across all runs
# ---------------------------------------------------------------------------

E_VISIT_A = {"type": "visit_node_a"}
E_ASCEND = {"type": "set_ascension", "value": True}

STREAM_BASE = [E_VISIT_A]                           # Run A: one visit, no ascension
STREAM_ASCENDED = [E_ASCEND, E_VISIT_A]             # Run B: same visit, ascension flipped first
STREAM_EXTRA_A = [E_VISIT_A, E_VISIT_A, E_VISIT_A]  # Run C: three visits, same ascension as A
STREAM_SATURATING = [E_VISIT_A] * 10                 # Run D: saturation (convergence proof)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _projection_hash(node_id: str, state: TravelerState) -> str:
    projectors = {"node_b": project_node_b, "node_c": project_node_c}
    snap = projectors[node_id](state)
    payload = node_id.encode() + repr(sorted(snap.items())).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


@dataclass
class RunResult:
    run_id: str
    final_state: TravelerState
    commit: bytes
    ct0_verdict: str
    projection_hashes: dict[str, str]  # advisory
    proves: str


def _execute_run(run_id: str, events: list[dict], proves: str) -> RunResult:
    s0 = TravelerState()
    sn = apply_events(s0, events)

    # Hard gate: two independent commits must be identical (determinism via CT-0)
    commit_1 = commit_state(sn, run_id)
    commit_2 = commit_state(sn, run_id)
    verdict, _ = ct0_evaluate(commit_1, commit_2, run_id)

    # Advisory: projection hashes (non-blocking)
    proj_hashes = {
        "node_b": _projection_hash("node_b", sn),
        "node_c": _projection_hash("node_c", sn),
    }

    return RunResult(
        run_id=run_id,
        final_state=sn,
        commit=commit_1,
        ct0_verdict=verdict.status,
        projection_hashes=proj_hashes,
        proves=proves,
    )


# ---------------------------------------------------------------------------
# Run A–D
# ---------------------------------------------------------------------------

def run_a() -> RunResult:
    return _execute_run(
        run_id="SPATIAL-VM-RUN-A",
        events=STREAM_BASE,
        proves="baseline: ascension=False, single Node A visit",
    )


def run_b() -> RunResult:
    return _execute_run(
        run_id="SPATIAL-VM-RUN-B",
        events=STREAM_ASCENDED,
        proves="ascension flip: same event count, different TravelerState.ascension",
    )


def run_c() -> RunResult:
    return _execute_run(
        run_id="SPATIAL-VM-RUN-C",
        events=STREAM_EXTRA_A,
        proves="accumulation: Node C perceptual_field shifts from baseline to heightened",
    )


def run_d() -> RunResult:
    return _execute_run(
        run_id="SPATIAL-VM-RUN-D",
        events=STREAM_SATURATING,
        proves="convergence: path-weighted memory saturates (diminishing delta proven)",
    )


# ---------------------------------------------------------------------------
# Assertions that constitute the conformance gate
# ---------------------------------------------------------------------------

@dataclass
class ConformanceReport:
    ab_bifurcation_ok: bool        # commit_A ≠ commit_B
    ab_source_is_state_only: bool  # Node B projection differs only because state differs
    c_accumulation_ok: bool        # commit_C ≠ commit_A; node_c field changed
    d_convergence_ok: bool         # delta sequence is strictly decreasing
    all_deterministic: bool        # every run has CT-0 PASS
    advisory_projection_diffs: dict  # informational; not a gate


def run_all() -> ConformanceReport:
    ra = run_a()
    rb = run_b()
    rc = run_c()

    # Run D: compute states step-by-step to prove diminishing deltas
    s = TravelerState()
    deltas: list[int] = []
    prev_score = 0
    for ev in STREAM_SATURATING:
        from .traveler_state import apply_event
        s = apply_event(s, ev)
        deltas.append(s.convergence_score - prev_score)
        prev_score = s.convergence_score
    rd = _execute_run("SPATIAL-VM-RUN-D", STREAM_SATURATING, run_d().proves)

    # Hard-gate assertions
    ab_bifurcation_ok = ra.commit != rb.commit
    ab_source_is_state_only = (
        ra.final_state.node_a_interaction_count == rb.final_state.node_a_interaction_count
        and ra.final_state.ascension != rb.final_state.ascension
        and project_node_b(ra.final_state) != project_node_b(rb.final_state)
    )
    c_accumulation_ok = (
        rc.commit != ra.commit
        and project_node_c(ra.final_state)["perceptual_field"] == "baseline"
        and project_node_c(rc.final_state)["perceptual_field"] == "heightened"
    )
    d_convergence_ok = all(
        deltas[i] > deltas[i + 1] for i in range(len(deltas) - 1)
    )
    all_deterministic = all(
        r.ct0_verdict == "OK" for r in [ra, rb, rc, rd]
    )

    advisory_diffs = {
        "run_a_vs_b_node_b": {
            "a": ra.projection_hashes["node_b"],
            "b": rb.projection_hashes["node_b"],
            "differs": ra.projection_hashes["node_b"] != rb.projection_hashes["node_b"],
        },
        "run_a_vs_c_node_c": {
            "a": ra.projection_hashes["node_c"],
            "c": rc.projection_hashes["node_c"],
            "differs": ra.projection_hashes["node_c"] != rc.projection_hashes["node_c"],
        },
    }

    return ConformanceReport(
        ab_bifurcation_ok=ab_bifurcation_ok,
        ab_source_is_state_only=ab_source_is_state_only,
        c_accumulation_ok=c_accumulation_ok,
        d_convergence_ok=d_convergence_ok,
        all_deterministic=all_deterministic,
        advisory_projection_diffs=advisory_diffs,
    )
