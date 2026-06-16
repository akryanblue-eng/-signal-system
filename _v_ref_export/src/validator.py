"""Type closure validator and golden vector checker for V_ref runners."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .cer import dispatch
from .oracle import interpret
from .types import CannotExpress, ForkCertificate, HealingTranscript

VALID_TYPES = (ForkCertificate, HealingTranscript, CannotExpress)


@dataclass
class TypeClosureResult:
    runner_name: str
    scenario_id: str
    oracle_type: type
    runner_output_type: type | None
    closed: bool
    violation: str | None


@dataclass
class GoldenVectorResult:
    scenario_id: str
    merkle_root_matches: bool
    output_type_matches: bool
    expected_root: str
    actual_root: str
    expected_type: str
    actual_type: str


def check_type_closure(
    runner: Callable[[dict], Any],
    runner_name: str,
    scenario: dict,
) -> TypeClosureResult:
    """Check whether runner's output type matches oracle's output type."""
    expected = interpret(scenario)
    expected_type = type(expected)
    scenario_id = scenario["scenario_id"]

    try:
        actual = runner(scenario)
    except Exception as exc:  # noqa: BLE001
        return TypeClosureResult(
            runner_name=runner_name,
            scenario_id=scenario_id,
            oracle_type=expected_type,
            runner_output_type=None,
            closed=False,
            violation=f"runner raised: {exc}",
        )

    if not isinstance(actual, VALID_TYPES):
        return TypeClosureResult(
            runner_name=runner_name,
            scenario_id=scenario_id,
            oracle_type=expected_type,
            runner_output_type=type(actual),
            closed=False,
            violation=f"non-V_ref output type: {type(actual).__name__}",
        )

    closed = type(actual) is expected_type
    return TypeClosureResult(
        runner_name=runner_name,
        scenario_id=scenario_id,
        oracle_type=expected_type,
        runner_output_type=type(actual),
        closed=closed,
        violation=(
            None
            if closed
            else (
                f"type mismatch: oracle={expected_type.__name__}, "
                f"runner={type(actual).__name__}"
            )
        ),
    )


def check_golden_vector(scenario: dict, golden: dict) -> GoldenVectorResult:
    """Verify scenario produces the same Merkle root and output type as the golden vector."""
    _, actual_root = dispatch(scenario)
    actual_output = interpret(scenario)
    actual_type = type(actual_output).__name__

    return GoldenVectorResult(
        scenario_id=scenario["scenario_id"],
        merkle_root_matches=actual_root == golden["merkle_root"],
        output_type_matches=actual_type == golden["oracle_output_type"],
        expected_root=golden["merkle_root"],
        actual_root=actual_root,
        expected_type=golden["oracle_output_type"],
        actual_type=actual_type,
    )
