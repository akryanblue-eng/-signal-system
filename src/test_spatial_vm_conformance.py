"""
Spatial VM conformance tests — CT-0 style gate for DSVM-0.

Hard gates (must pass for AppFlow integration / Node D):

    test_all_runs_deterministic     every run satisfies CT-0 (two identical commits)
    test_run_ab_bifurcation         commit_A ≠ commit_B
    test_run_ab_source_state_only   only ascension flag differs between A/B states
    test_run_c_determinism          commit_C == commit_A (replay)
    test_run_d_idempotency          commit_D == commit_A (re-entry is no-op)

Negative invariants:

    test_frozen_state_immutable     TravelerState cannot be mutated outside reducer
    test_convergence_score_diminishing  path-weighted memory has strictly diminishing deltas

Advisory:

    test_advisory_projection_diffs  Node B hash differs A vs B; Node C hash is same A vs B
"""
import pytest
from src.traveler_state import (
    TravelerState,
    apply_event,
    apply_events,
    commit_state,
    project_node_b,
    project_node_c,
)
from src.spatial_vm_conformance import (
    run_a, run_b, run_c, run_d, run_all,
    STREAM_RUN_A,
)


# ---------------------------------------------------------------------------
# CT-0 determinism oracle
# ---------------------------------------------------------------------------

def test_all_runs_deterministic():
    report = run_all()
    assert report.all_deterministic, (
        "CT-0 FAIL: at least one run produced non-identical commits across two RI-0 replays."
    )


# ---------------------------------------------------------------------------
# Run A vs B: semantic bifurcation
# ---------------------------------------------------------------------------

def test_run_ab_bifurcation():
    ra, rb = run_a(), run_b()
    assert ra.commit != rb.commit, (
        "Run A (ascension) and Run B (creation) must produce distinct commits. "
        "The choice event must change TravelerState.ascension and therefore the commit."
    )


def test_run_ab_source_state_only():
    """
    Bifurcation must come from TravelerState alone, not from scene residue:
    - visited_nodes, discovered_artifacts, revealed_lore are identical.
    - Only ascension flag differs.
    """
    ra, rb = run_a(), run_b()
    assert ra.final_state.visited_nodes == rb.final_state.visited_nodes, (
        "Both runs must visit identical nodes."
    )
    assert ra.final_state.discovered_artifacts == rb.final_state.discovered_artifacts, (
        "Both runs must discover identical artifacts."
    )
    assert ra.final_state.revealed_lore == rb.final_state.revealed_lore, (
        "Both runs must reveal identical lore."
    )
    assert ra.final_state.ascension != rb.final_state.ascension, (
        "Runs A and B must differ only on ascension flag."
    )
    # Projection must reflect the difference
    assert project_node_b(ra.final_state) != project_node_b(rb.final_state), (
        "Node B projection must differ between Run A and Run B. "
        "If identical, project_node_b is not reading TravelerState.ascension."
    )


# ---------------------------------------------------------------------------
# Run C: determinism replay
# ---------------------------------------------------------------------------

def test_run_c_determinism():
    """
    Identical event streams must produce identical state.
    Compared via state_commit (fixed sentinel run_id) so run identity doesn't interfere.
    """
    ra, rc = run_a(), run_c()
    assert rc.final_state == ra.final_state, (
        "Run C final TravelerState must equal Run A final TravelerState (field equality)."
    )
    assert rc.state_commit == ra.state_commit, (
        "Run C state_commit must equal Run A state_commit. "
        "Identical event streams must always yield identical committed state."
    )


# ---------------------------------------------------------------------------
# Run D: idempotency under re-entry
# ---------------------------------------------------------------------------

def test_run_d_idempotency():
    """
    Re-entering already-visited nodes must not mutate TravelerState.
    Compared via state_commit (fixed sentinel run_id).
    """
    ra, rd = run_a(), run_d()
    assert rd.final_state == ra.final_state, (
        "TravelerState must be unchanged by idempotent re-entry events."
    )
    assert rd.state_commit == ra.state_commit, (
        "Run D state_commit must equal Run A state_commit. "
        "Duplicate node entries must not change committed state."
    )


# ---------------------------------------------------------------------------
# Negative invariants
# ---------------------------------------------------------------------------

def test_frozen_state_immutable():
    """TravelerState.frozen=True is the local guard for negative invariant N4."""
    s = TravelerState(visited_nodes=("neon-in-nirvana",))
    with pytest.raises((AttributeError, TypeError)):
        s.ascension = True  # type: ignore[misc]


def test_convergence_score_diminishing():
    """
    Path-weighted memory must have strictly diminishing deltas.
    This is a property test on the convergence_score formula itself.
    """
    s = TravelerState()
    deltas: list[int] = []
    prev = 0
    for i in range(1, 11):
        s = apply_event(s, {"type": "enter_node", "node_id": f"node-{i}"})
        deltas.append(s.convergence_score - prev)
        prev = s.convergence_score

    for i in range(len(deltas) - 1):
        assert deltas[i] > deltas[i + 1], (
            f"convergence_score delta at visit {i+1} ({deltas[i]}) must exceed "
            f"delta at visit {i+2} ({deltas[i+1]}). "
            "Harmonic path-weighting must have strictly diminishing returns."
        )


def test_no_op_events_do_not_mutate():
    """node_completed and portal_unlocked events must never change TravelerState."""
    s = TravelerState(visited_nodes=("neon-in-nirvana",), ascension=True)
    s2 = apply_event(s, {"type": "node_completed", "node_id": "neon-in-nirvana"})
    s3 = apply_event(s, {"type": "portal_unlocked", "portal_id": "godly-dna"})
    assert s2 == s
    assert s3 == s


# ---------------------------------------------------------------------------
# Advisory: projection hashes
# ---------------------------------------------------------------------------

def test_advisory_projection_diffs(capfd):
    report = run_all()
    diffs = report.advisory_projection_diffs

    for label, info in diffs.items():
        print(f"[advisory] {label}: {'DIFFERS' if info['differs'] else 'SAME'}")

    capfd.readouterr()  # consume output

    assert diffs["run_a_vs_b_node_b"]["differs"], (
        "[advisory] Node B projection hash must differ between Run A and Run B. "
        "Node B is ascension-sensitive."
    )
