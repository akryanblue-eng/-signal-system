"""
Deterministic V_ref interpreter.

interpret(scenario) -> VRefOutput is a pure function:
  - no global state
  - no runtime feedback into policy selection
  - no dynamic reinterpretation of past runs
  - same input always produces the same output (closure enforced)
"""
from __future__ import annotations

import json
from pathlib import Path

from .cer import dispatch
from .types import CannotExpress, ForkCertificate, HealingTranscript, VRefOutput
from .spec.v_ref_spec import find_fork_pairs, merge_convergent, observer_sees_all, visible_events


def interpret(scenario: dict) -> VRefOutput:
    scenario_id = scenario["scenario_id"]

    # CannotExpress: partial observability is checked before CER dispatch.
    # An observer who cannot see all events cannot certify a fork — the
    # fork may or may not exist in the hidden partition.
    if not observer_sees_all(scenario):
        return CannotExpress(
            scenario_id=scenario_id,
            reason="partial_observability",
            partial_observations=visible_events(scenario),
        )

    # Dispatch all events to CER chain (raises on unrecognized event types)
    chain, _merkle_root = dispatch(scenario)

    # Fork detection
    pairs = find_fork_pairs(chain)
    if pairs:
        c1, c2 = pairs[0]
        fork_axis = c1.key
        merge_fn = scenario.get("merge_function")
        if merge_fn is not None:
            merged = merge_convergent(c1, c2)
            if merged is not None:
                return HealingTranscript(
                    scenario_id=scenario_id,
                    pre_state={fork_axis: [c1.value, c2.value]},
                    post_state={fork_axis: merged},
                    healing_steps=[
                        f"fork detected on axis {fork_axis!r}",
                        f"merge_function={merge_fn!r} applied",
                        f"converged to {merged!r}",
                    ],
                    convergent=True,
                )
        return ForkCertificate(
            scenario_id=scenario_id,
            fork_axis=fork_axis,
            conflicting_writes=[
                {"event_id": c1.event_id, "key": c1.key, "value": c1.value, "node": c1.node},
                {"event_id": c2.event_id, "key": c2.key, "value": c2.value, "node": c2.node},
            ],
        )

    return CannotExpress(
        scenario_id=scenario_id,
        reason="no_concurrent_conflict_detected",
        partial_observations=[{"event_id": c.event_id, "key": c.key} for c in chain],
    )


def interpret_file(path: Path) -> VRefOutput:
    return interpret(json.loads(path.read_bytes()))
