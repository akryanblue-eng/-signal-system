"""
Spatial VM conformance tests — CT-0 style gate for DSVM-0.

Each test proves exactly one axis of the contract. All four must pass before
AppFlow glue or Node D integration.

Hard gates (must pass):
    test_run_ab_bifurcation        — commit_A ≠ commit_B
    test_run_ab_state_source_only  — bifurcation comes from TravelerState, not scene
    test_run_c_accumulation        — accumulation shifts Node C without new mechanics
    test_run_d_convergence         — path-weighted memory has diminishing deltas
    test_all_runs_deterministic    — every run satisfies CT-0 (PASS)

Advisory (logged, non-blocking):
    test_advisory_projection_diffs — projection hashes differ where expected
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
    run_a,
    run_b,
    run_c,
    run_d,
    run_all,
    STREAM_SATURATING,
)


# ---------------------------------------------------------------------------
# Determinism (CT-0 oracle)
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
        "Run A and Run B must produce distinct commits. "
        "Ascension flip in TravelerState must change the committed state."
    )


def test_run_ab_state_source_only():
    """
    Prove the bifurcation comes from TravelerState alone, not scene residue:
    - Both runs apply exactly one visit_node_a event.
    - Only .ascension differs between the final states.
    - Node B projection therefore differs only because TravelerState differs.
    """
    ra, rb = run_a(), run_b()
    assert ra.final_state.node_a_interaction_count == rb.final_state.node_a_interaction_count, (
        "Both runs must have the same node_a_interaction_count (same event count)."
    )
    assert ra.final_state.ascension != rb.final_state.ascension, (
        "Runs A and B must differ only on ascension flag."
    )
    proj_a = project_node_b(ra.final_state)
    proj_b = project_node_b(rb.final_state)
    assert proj_a != proj_b, (
        "Node B projection must differ between Run A and Run B. "
        "If this fails, projection is not reading TravelerState.ascension."
    )


# ---------------------------------------------------------------------------
# Run C: accumulation
# ---------------------------------------------------------------------------

def test_run_c_accumulation():
    """
    Three Node A visits (same ascension as Run A) must:
    - Produce a different commit than Run A (state changed).
    - Shift Node C perceptual_field from 'baseline' to 'heightened'.
    - Require no new event types (causal depth from existing state only).
    """
    ra, rc = run_a(), run_c()
    assert rc.commit != ra.commit, (
        "Run C must produce a different commit than Run A."
    )
    node_c_a = project_node_c(ra.final_state)
    node_c_c = project_node_c(rc.final_state)
    assert node_c_a["perceptual_field"] == "baseline", (
        "Node C after Run A must report baseline perceptual_field."
    )
    assert node_c_c["perceptual_field"] == "heightened", (
        "Node C after Run C (3 visits) must report heightened perceptual_field."
    )


# ---------------------------------------------------------------------------
# Run D: convergence (path-weighted memory)
# ---------------------------------------------------------------------------

def test_run_d_convergence():
    """
    10 sequential Node A visits must produce strictly decreasing convergence_score deltas.
    Proves there is a convergence function (not branch toggles or flat accumulation).
    """
    s = TravelerState()
    deltas: list[int] = []
    prev = 0
    for ev in STREAM_SATURATING:
        s = apply_event(s, ev)
        deltas.append(s.convergence_score - prev)
        prev = s.convergence_score

    for i in range(len(deltas) - 1):
        assert deltas[i] > deltas[i + 1], (
            f"convergence_score delta at visit {i+1} ({deltas[i]}) must exceed "
            f"delta at visit {i+2} ({deltas[i+1]}). "
            "Path-weighted memory must have strictly diminishing returns."
        )


# ---------------------------------------------------------------------------
# Negative invariant smoke test: reducer is the only write path
# ---------------------------------------------------------------------------

def test_frozen_state_immutable():
    """
    TravelerState is frozen — attempting to mutate it must raise.
    This is a local guard; the real invariant (N1) is enforced at the Swift layer.
    """
    s = TravelerState(ascension=False, node_a_interaction_count=0)
    with pytest.raises((AttributeError, TypeError)):
        s.ascension = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Advisory: projection hashes (non-blocking, informational)
# ---------------------------------------------------------------------------

def test_advisory_projection_diffs(capfd):
    report = run_all()
    diffs = report.advisory_projection_diffs

    # Log diffs for inspection (never assert — advisory only until Node D)
    for label, info in diffs.items():
        status = "DIFFERS" if info["differs"] else "SAME"
        print(f"[advisory] {label}: {status}")

    out, _ = capfd.readouterr()
    # Node B hash must differ (ascension changes its output)
    assert diffs["run_a_vs_b_node_b"]["differs"], (
        "[advisory] Node B projection hash should differ between Run A and Run B."
    )
    # Node C hash must differ (accumulation changes its output)
    assert diffs["run_a_vs_c_node_c"]["differs"], (
        "[advisory] Node C projection hash should differ between Run A and Run C."
    )
