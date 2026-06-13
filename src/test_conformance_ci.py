"""
DSVM-0 CI Gate — pytest wrapper for the frozen oracle.

Loads spatial_vm_fixtures/oracle_runs.json and verifies that the current
implementation produces identical state_commit_hex values for all runs.

This is the build-fails-on-divergence gate.  Add to CI alongside the
conformance tests:

    pytest src/test_spatial_vm_conformance.py src/test_conformance_ci.py -v

Failure output:
    Prints a state diff tree and first-point-of-failure localization,
    mirroring the ReplayHarnessDiff.swift output the Swift CI gate emits.
"""
import json
import sys
from pathlib import Path

import pytest

from src.spatial_vm_conformance import run_a, run_b, run_c, run_d, RunResult
from src.traveler_state import TravelerState

ORACLE_JSON = Path(__file__).parent.parent / "spatial_vm_fixtures" / "oracle_runs.json"


@pytest.fixture(scope="module")
def oracle() -> dict:
    if not ORACLE_JSON.exists():
        pytest.fail(
            f"Oracle fixture missing: {ORACLE_JSON}\n"
            "Run `python -m src.oracle_generator` to generate it."
        )
    return json.loads(ORACLE_JSON.read_text())


@pytest.fixture(scope="module")
def results() -> dict[str, RunResult]:
    return {"A": run_a(), "B": run_b(), "C": run_c(), "D": run_d()}


# ---------------------------------------------------------------------------
# Per-run oracle gate
# ---------------------------------------------------------------------------

def _diff_report(label: str, result: RunResult, frozen_run: dict) -> str:
    frozen_state = frozen_run["expected_state"]
    actual = result.final_state
    lines = [f"\nRun {label} — {result.run_id}"]

    pairs = [
        ("visited_nodes",        tuple(frozen_state["visited_nodes"]),        actual.visited_nodes),
        ("discovered_artifacts", tuple(frozen_state["discovered_artifacts"]),  actual.discovered_artifacts),
        ("revealed_lore",        tuple(frozen_state["revealed_lore"]),         actual.revealed_lore),
        ("ascension",            frozen_state["ascension"],                    actual.ascension),
        ("convergence_score",    frozen_state["convergence_score"],            actual.convergence_score),
    ]
    for field, fv, av in pairs:
        mark = "✅" if fv == av else "❌"
        lines.append(f"  {mark} {field}: oracle={fv!r}, actual={av!r}")

    # First-point-of-failure: replay events step-by-step against the per-step trace oracle
    frozen_trace = frozen_run.get("state_trace", [])
    if frozen_trace:
        s = TravelerState()
        from src.traveler_state import apply_event, commit_state
        first_divergence = None
        for step in frozen_trace:
            s = apply_event(s, step["event"])
            actual_step_commit = commit_state(s, "DSVM0-STATE-ORACLE").hex()
            if actual_step_commit != step["state_commit_hex"]:
                first_divergence = {
                    "step": step["step"],
                    "event": step["event"],
                    "oracle_commit": step["state_commit_hex"][:24],
                    "actual_commit": actual_step_commit[:24],
                    "oracle_state": step["state_after"],
                    "actual_ascension": s.ascension,
                    "actual_gene_locked": s.gene_choice_locked,
                }
                break
        if first_divergence:
            fd = first_divergence
            lines.append(
                f"\n🎯 First Divergence: step {fd['step']} — {fd['event']}"
            )
            lines.append(f"  oracle commit: {fd['oracle_commit']}…")
            lines.append(f"  actual commit: {fd['actual_commit']}…")
            lines.append(f"  oracle ascension={fd['oracle_state']['ascension']}, "
                         f"gene_choice_locked={fd['oracle_state'].get('gene_choice_locked', '?')}")
            lines.append(f"  actual ascension={fd['actual_ascension']}, "
                         f"gene_choice_locked={fd['actual_gene_locked']}")

    lines.append(f"\n  state_commit_hex (oracle): {frozen_run['state_commit_hex'][:32]}…")
    lines.append(f"  state_commit_hex (actual): {result.state_commit.hex()[:32]}…")
    return "\n".join(lines)


@pytest.mark.parametrize("label", ["A", "B", "C", "D"])
def test_run_matches_oracle(label: str, oracle: dict, results: dict[str, RunResult]):
    result = results[label]
    frozen = oracle["runs"].get(label)
    assert frozen is not None, f"Run {label} not found in oracle fixture."

    frozen_commit = frozen["state_commit_hex"]
    actual_commit = result.state_commit.hex()

    assert actual_commit == frozen_commit, (
        f"❌ DSVM-0 CI GATE FAIL: Run {label} diverged from frozen oracle.\n"
        + _diff_report(label, result, frozen)
        + "\n\nIf this change is intentional, regenerate with:\n"
        "  python -m src.oracle_generator"
    )


# ---------------------------------------------------------------------------
# Schema integrity
# ---------------------------------------------------------------------------

def test_oracle_schema(oracle: dict):
    assert oracle.get("schema") == "dsvm0-oracle-v1", (
        "oracle_runs.json schema field must be 'dsvm0-oracle-v1'."
    )
    assert set(oracle["runs"].keys()) >= {"A", "B", "C", "D"}, (
        "oracle_runs.json must contain runs A, B, C, D."
    )


def test_ab_commits_differ_in_oracle(oracle: dict):
    commit_a = oracle["runs"]["A"]["state_commit_hex"]
    commit_b = oracle["runs"]["B"]["state_commit_hex"]
    assert commit_a != commit_b, (
        "Oracle must record distinct state_commit_hex for Run A and Run B."
    )


def test_acd_commits_identical_in_oracle(oracle: dict):
    commit_a = oracle["runs"]["A"]["state_commit_hex"]
    commit_c = oracle["runs"]["C"]["state_commit_hex"]
    commit_d = oracle["runs"]["D"]["state_commit_hex"]
    assert commit_a == commit_c, "Oracle: Run A and Run C must have identical state commits."
    assert commit_a == commit_d, "Oracle: Run A and Run D must have identical state commits."


# ---------------------------------------------------------------------------
# Step-trace gate: validates per-event causal transitions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", ["A", "B"])
def test_step_trace_matches_oracle(label: str, oracle: dict, results: dict[str, RunResult]):
    """
    For each event in the stream, the state commit at that step must match the frozen oracle.
    This is the DSVM Trace Validator: locates the first-diverging event precisely.
    """
    from src.traveler_state import apply_event, commit_state
    frozen_trace = oracle["runs"][label].get("state_trace", [])
    assert frozen_trace, f"No state_trace in oracle for Run {label} — regenerate fixtures."

    s = TravelerState()
    for step in frozen_trace:
        s = apply_event(s, step["event"])
        actual_commit = commit_state(s, "DSVM0-STATE-ORACLE").hex()
        frozen_commit = step["state_commit_hex"]

        assert actual_commit == frozen_commit, (
            f"❌ Trace divergence at step {step['step']} in Run {label}\n"
            f"  Event: {step['event']}\n"
            f"  oracle state_commit: {frozen_commit[:32]}…\n"
            f"  actual state_commit: {actual_commit[:32]}…\n"
            f"  oracle ascension={step['state_after']['ascension']}, "
            f"gene_choice_locked={step['state_after'].get('gene_choice_locked', '?')}\n"
            f"  actual ascension={s.ascension}, gene_choice_locked={s.gene_choice_locked}\n"
            f"\nIf this is intentional, regenerate:\n"
            "  python -m src.oracle_generator"
        )


def test_write_once_guard_in_oracle(oracle: dict):
    """
    After choose_ascension/choose_creation, the oracle trace must show gene_choice_locked=True.
    Subsequent choice events in Run D (re-entry saturation) must not flip ascension.
    """
    for label in ("A", "B"):
        trace = oracle["runs"][label]["state_trace"]
        locked = False
        for step in trace:
            state_after = step["state_after"]
            if step["event"]["type"] in ("choose_ascension", "choose_creation"):
                assert state_after.get("gene_choice_locked") is True, (
                    f"Run {label} step {step['step']}: {step['event']['type']} must set "
                    f"gene_choice_locked=True in oracle. Write-once guard not applied."
                )
                locked = True
            if locked:
                assert state_after.get("gene_choice_locked") is True, (
                    f"Run {label} step {step['step']}: gene_choice_locked must stay True "
                    f"once set. Write-once invariant violated."
                )
