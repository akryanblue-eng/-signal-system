"""
Schema lock: golden vector replay tests.

For each scenario, verifies:
  1. Merkle root is identical to the golden vector (determinism across rebuilds)
  2. Oracle output type matches the golden vector (semantic stability)

Any deviation from a golden vector is an invariant failure, not a warning.
These tests encode the non-regression boundary: once a golden vector exists,
the system's semantic identity is fixed.
"""
import json
from pathlib import Path

from src.cer import dispatch
from src.oracle import interpret
from src.validator import check_golden_vector

SCENARIOS_DIR = Path(__file__).parent / "scenarios"
GOLDEN_DIR = Path(__file__).parent / "golden"


def _load(name: str) -> tuple[dict, dict]:
    scenario = json.loads((SCENARIOS_DIR / f"{name}.json").read_bytes())
    golden = json.loads((GOLDEN_DIR / f"{name}.golden.json").read_bytes())
    return scenario, golden


def test_equivocation_merkle_root_stable():
    """Merkle root is reproducible across rebuilds."""
    scenario, _ = _load("equivocation_001")
    _, root1 = dispatch(scenario)
    _, root2 = dispatch(scenario)
    assert root1 == root2


def test_equivocation_matches_golden_vector():
    scenario, golden = _load("equivocation_001")
    result = check_golden_vector(scenario, golden)
    assert result.merkle_root_matches, (
        f"Merkle root drift on {result.scenario_id}: "
        f"expected={result.expected_root}, actual={result.actual_root}"
    )
    assert result.output_type_matches, (
        f"Output type drift on {result.scenario_id}: "
        f"expected={result.expected_type}, actual={result.actual_type}"
    )


def test_partial_observer_merkle_root_stable():
    scenario, _ = _load("partial_observer_001")
    _, root1 = dispatch(scenario)
    _, root2 = dispatch(scenario)
    assert root1 == root2


def test_partial_observer_matches_golden_vector():
    scenario, golden = _load("partial_observer_001")
    result = check_golden_vector(scenario, golden)
    assert result.merkle_root_matches, (
        f"Merkle root drift on {result.scenario_id}: "
        f"expected={result.expected_root}, actual={result.actual_root}"
    )
    assert result.output_type_matches, (
        f"Output type drift on {result.scenario_id}: "
        f"expected={result.expected_type}, actual={result.actual_type}"
    )


def test_non_mergeable_merkle_root_stable():
    scenario, _ = _load("non_mergeable_001")
    _, root1 = dispatch(scenario)
    _, root2 = dispatch(scenario)
    assert root1 == root2


def test_non_mergeable_matches_golden_vector():
    scenario, golden = _load("non_mergeable_001")
    result = check_golden_vector(scenario, golden)
    assert result.merkle_root_matches, (
        f"Merkle root drift on {result.scenario_id}: "
        f"expected={result.expected_root}, actual={result.actual_root}"
    )
    assert result.output_type_matches, (
        f"Output type drift on {result.scenario_id}: "
        f"expected={result.expected_type}, actual={result.actual_type}"
    )


def test_cer_dispatch_exhaustive_on_known_types():
    """CER dispatch raises for unrecognized event types — no hidden branches."""
    import pytest
    from src.cer import dispatch as cer_dispatch

    bad_scenario = {
        "scenario_id": "dispatch_exhaustion_check",
        "events": [
            {
                "event_id": "x1",
                "type": "unknown_op",
                "key": "k",
                "value": "v",
                "node": "N1",
                "clock": {"N1": 1},
            }
        ],
    }
    with pytest.raises(ValueError, match="CER_DISPATCH_INCOMPLETE"):
        cer_dispatch(bad_scenario)
