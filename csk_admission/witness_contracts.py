"""
Stage 2 — Witness Contract Evaluation (WCE).

Witnesses do NOT judge "truth". They detect whether an event can coexist
with existing reconstructed truth (the replayable LedgerState).

A WitnessContract is a pure function: (event, topic_key, state) -> WitnessOutcome.
"""
from __future__ import annotations

from typing import Callable

from .ledger import LedgerState
from .types import WitnessOutcome, WitnessResult

WitnessContract = Callable[[dict, str, LedgerState], WitnessOutcome]


def witness_decision_made(event: dict, topic_key: str, state: LedgerState) -> WitnessOutcome:
    active = state.active_decision(topic_key)
    if active is None:
        return WitnessOutcome(
            result=WitnessResult.VALID,
            reasons=["first decision for topic"],
            affected_topics=[topic_key],
        )

    supersedes = event["payload"].get("supersedes")
    if supersedes == active.event_id:
        return WitnessOutcome(
            result=WitnessResult.VALID,
            reasons=[f"proper supersede chain: replaces active decision {active.event_id}"],
            affected_topics=[topic_key],
        )

    return WitnessOutcome(
        result=WitnessResult.CONTRADICTION,
        reasons=[f"competing active decision exists for topic {topic_key!r} (active={active.event_id})"],
        affected_topics=[topic_key],
    )


def witness_decision_superseded(event: dict, topic_key: str, state: LedgerState) -> WitnessOutcome:
    target_id = event["payload"].get("supersedes")
    if not target_id:
        return WitnessOutcome(
            result=WitnessResult.INSUFFICIENT_CONTEXT,
            reasons=["missing 'supersedes' reference"],
            affected_topics=[topic_key],
        )

    target = state.decision_by_id(target_id)
    if target is None:
        return WitnessOutcome(
            result=WitnessResult.INSUFFICIENT_CONTEXT,
            reasons=[f"referenced decision {target_id!r} does not exist"],
            affected_topics=[topic_key],
        )

    if not target.active:
        return WitnessOutcome(
            result=WitnessResult.CONTRADICTION,
            reasons=[f"referenced decision {target_id!r} is not active"],
            affected_topics=[topic_key, target.topic_key],
        )

    if target.topic_key != topic_key:
        return WitnessOutcome(
            result=WitnessResult.CONTRADICTION,
            reasons=[
                f"supersede topic mismatch: event topic {topic_key!r} "
                f"!= target topic {target.topic_key!r}"
            ],
            affected_topics=[topic_key, target.topic_key],
        )

    return WitnessOutcome(
        result=WitnessResult.VALID,
        reasons=[f"clean resolution of {target_id!r}"],
        affected_topics=[topic_key],
    )


def witness_loop_opened(event: dict, topic_key: str, state: LedgerState) -> WitnessOutcome:
    loop_id = event["payload"].get("loop_id")
    if not loop_id:
        return WitnessOutcome(
            result=WitnessResult.INSUFFICIENT_CONTEXT,
            reasons=["missing loop_id"],
            affected_topics=[topic_key],
        )

    existing = state.loop(loop_id)
    if existing is not None and existing.status == "OPEN":
        return WitnessOutcome(
            result=WitnessResult.CONTRADICTION,
            reasons=[f"loop {loop_id!r} is already open"],
            affected_topics=[topic_key],
        )

    return WitnessOutcome(
        result=WitnessResult.VALID,
        reasons=[f"loop {loop_id!r} opened"],
        affected_topics=[topic_key],
    )


def witness_loop_closed(event: dict, topic_key: str, state: LedgerState) -> WitnessOutcome:
    loop_id = event["payload"].get("loop_id")
    if not loop_id:
        return WitnessOutcome(
            result=WitnessResult.INSUFFICIENT_CONTEXT,
            reasons=["missing loop_id"],
            affected_topics=[topic_key],
        )

    existing = state.loop(loop_id)
    if existing is None or existing.status != "OPEN":
        return WitnessOutcome(
            result=WitnessResult.CONTRADICTION,
            reasons=[f"cannot close non-open loop {loop_id!r}"],
            affected_topics=[topic_key],
        )

    return WitnessOutcome(
        result=WitnessResult.VALID,
        reasons=[f"loop {loop_id!r} closed"],
        affected_topics=[topic_key],
    )


WITNESS_CONTRACTS: dict[str, WitnessContract] = {
    "decision.made": witness_decision_made,
    "decision.superseded": witness_decision_superseded,
    "loop.opened": witness_loop_opened,
    "loop.closed": witness_loop_closed,
}


def evaluate(event: dict, topic_key: str, state: LedgerState) -> WitnessOutcome:
    """Look up and run the witness contract for event['type']. Caller guarantees the type is known."""
    contract = WITNESS_CONTRACTS[event["type"]]
    return contract(event, topic_key, state)
