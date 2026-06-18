"""
Stage 2 — Witness Contract Evaluation (WCE).

Witnesses do NOT judge "truth". They detect whether an event can coexist
with existing reconstructed truth (the replayable LedgerState, plus the
quarantine store for event.disambiguated).

Outcome lattice (v1.1 — non-overlapping):
    VALID                 single coherent interpretation; no competing claims.
    CONTRADICTION          a committed truth is violated, deterministically
                            and unambiguously (exactly one rule is broken).
    AMBIGUOUS               the event is well-formed and single-topic, but
                            history admits more than one valid candidate it
                            could attach to, and no anchor disambiguates.
    INSUFFICIENT_CONTEXT     the event cannot be evaluated at all: a required
                            anchor is missing/unresolvable and there is no
                            history to fall back on.

Stage 1 removes uncertainty about what the event is.
The witness layer resolves uncertainty about what the event means in history.

A WitnessContract is a pure function: (event, topic_key, ledger) -> WitnessOutcome.
It must never mutate ledger state — mutation belongs to Stage 3 (ledger.py).
"""
from __future__ import annotations

from typing import Callable

from .ledger import Ledger
from .types import WitnessOutcome, WitnessResult

WitnessContract = Callable[[dict, str, Ledger], WitnessOutcome]

# Maps an event type to the payload field that names its disambiguating
# anchor. Only types that can be quarantined as AMBIGUOUS need an entry here.
ANCHOR_FIELD: dict[str, str] = {
    "decision.superseded": "supersedes",
    "loop.closed": "loop_id",
}


def witness_decision_made(event: dict, topic_key: str, ledger: Ledger) -> WitnessOutcome:
    state = ledger.state
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


def witness_decision_superseded(event: dict, topic_key: str, ledger: Ledger) -> WitnessOutcome:
    state = ledger.state
    target_id = event["payload"].get("supersedes")

    if target_id:
        target = state.decision_by_id(target_id)
        if target is None:
            return WitnessOutcome(
                result=WitnessResult.INSUFFICIENT_CONTEXT,
                reasons=[f"referenced decision {target_id!r} does not exist"],
                affected_topics=[topic_key],
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
        if not target.active:
            return WitnessOutcome(
                result=WitnessResult.CONTRADICTION,
                reasons=[f"referenced decision {target_id!r} is not active"],
                affected_topics=[topic_key],
            )
        return WitnessOutcome(
            result=WitnessResult.VALID,
            reasons=[f"clean resolution of {target_id!r}"],
            affected_topics=[topic_key],
        )

    # No anchor given: resolve from history if and only if it's unambiguous.
    candidates = state.decisions_for_topic(topic_key)
    if not candidates:
        return WitnessOutcome(
            result=WitnessResult.INSUFFICIENT_CONTEXT,
            reasons=[f"no decision history exists for topic {topic_key!r}; nothing to supersede"],
            affected_topics=[topic_key],
        )
    if len(candidates) > 1:
        return WitnessOutcome(
            result=WitnessResult.AMBIGUOUS,
            reasons=[
                f"{len(candidates)} historical decisions exist for topic {topic_key!r}; "
                "explicit 'supersedes' anchor required"
            ],
            affected_topics=[topic_key],
        )
    only = candidates[0]
    if not only.active:
        return WitnessOutcome(
            result=WitnessResult.CONTRADICTION,
            reasons=[f"the only decision on topic {topic_key!r} ({only.event_id}) is already inactive"],
            affected_topics=[topic_key],
        )
    return WitnessOutcome(
        result=WitnessResult.VALID,
        reasons=[f"clean resolution of {only.event_id!r} (implicit, single candidate)"],
        affected_topics=[topic_key],
    )


def witness_loop_opened(event: dict, topic_key: str, ledger: Ledger) -> WitnessOutcome:
    # Concurrent open loops on the same topic are legitimate in v1.1 — that's
    # precisely what makes a later ambiguous loop.closed reachable. No
    # contradiction case exists here; each opened loop is its own identity
    # (the opening event's own id), so there is nothing for a second open to
    # collide with.
    return WitnessOutcome(
        result=WitnessResult.VALID,
        reasons=[f"loop opened for topic {topic_key!r}"],
        affected_topics=[topic_key],
    )


def witness_loop_closed(event: dict, topic_key: str, ledger: Ledger) -> WitnessOutcome:
    state = ledger.state
    anchor = event["payload"].get("loop_id")

    if anchor:
        target = state.loop(anchor)
        if target is None:
            return WitnessOutcome(
                result=WitnessResult.INSUFFICIENT_CONTEXT,
                reasons=[f"referenced loop {anchor!r} does not exist"],
                affected_topics=[topic_key],
            )
        if target.topic_key != topic_key:
            return WitnessOutcome(
                result=WitnessResult.CONTRADICTION,
                reasons=[f"loop {anchor!r} belongs to topic {target.topic_key!r}, not {topic_key!r}"],
                affected_topics=[topic_key, target.topic_key],
            )
        if target.status != "OPEN":
            return WitnessOutcome(
                result=WitnessResult.CONTRADICTION,
                reasons=[f"cannot close non-open loop {anchor!r}"],
                affected_topics=[topic_key],
            )
        return WitnessOutcome(
            result=WitnessResult.VALID,
            reasons=[f"loop {anchor!r} closed"],
            affected_topics=[topic_key],
        )

    # No anchor given: resolve from open loops on this topic if unambiguous.
    open_loops = state.open_loops_for_topic(topic_key)
    if not open_loops:
        return WitnessOutcome(
            result=WitnessResult.CONTRADICTION,
            reasons=[f"cannot close non-open loop: no open loops for topic {topic_key!r}"],
            affected_topics=[topic_key],
        )
    if len(open_loops) > 1:
        return WitnessOutcome(
            result=WitnessResult.AMBIGUOUS,
            reasons=[
                f"{len(open_loops)} open loops exist for topic {topic_key!r}; "
                "explicit 'loop_id' anchor required"
            ],
            affected_topics=[topic_key],
        )
    return WitnessOutcome(
        result=WitnessResult.VALID,
        reasons=[f"loop {open_loops[0].loop_id!r} closed (implicit, single candidate)"],
        affected_topics=[topic_key],
    )


def witness_event_disambiguated(event: dict, topic_key: str, ledger: Ledger) -> WitnessOutcome:
    """
    Resolves a previously-quarantined AMBIGUOUS event by naming an explicit
    anchor. This is the only sanctioned path out of AMBIGUOUS quarantine —
    CSK never infers a disambiguating anchor on its own.
    """
    payload = event["payload"]
    target_id = payload.get("target_event_id")
    anchor_id = payload.get("chosen_anchor_id")
    if not target_id or not anchor_id:
        return WitnessOutcome(
            result=WitnessResult.INSUFFICIENT_CONTEXT,
            reasons=["missing target_event_id or chosen_anchor_id"],
            affected_topics=[topic_key],
        )

    target = ledger.quarantine.get(target_id)
    if target is None:
        return WitnessOutcome(
            result=WitnessResult.INSUFFICIENT_CONTEXT,
            reasons=[f"no quarantined event {target_id!r} to disambiguate"],
            affected_topics=[topic_key],
        )

    from .topics import extract_topic, normalize_topic

    target_topic_key = normalize_topic(extract_topic(target["payload"]))
    if target_topic_key != topic_key:
        return WitnessOutcome(
            result=WitnessResult.CONTRADICTION,
            reasons=[
                f"disambiguation topic {topic_key!r} does not match "
                f"quarantined event topic {target_topic_key!r}"
            ],
            affected_topics=[topic_key, target_topic_key],
        )

    anchor_field = ANCHOR_FIELD.get(target["type"])
    if anchor_field is None:
        return WitnessOutcome(
            result=WitnessResult.INSUFFICIENT_CONTEXT,
            reasons=[f"disambiguation not supported for event type {target['type']!r}"],
            affected_topics=[topic_key],
        )

    synthesized = {**target, "payload": {**target["payload"], anchor_field: anchor_id}}
    inner_outcome = WITNESS_CONTRACTS[target["type"]](synthesized, target_topic_key, ledger)

    if inner_outcome.result != WitnessResult.VALID:
        return WitnessOutcome(
            result=WitnessResult.CONTRADICTION,
            reasons=[f"chosen anchor {anchor_id!r} does not resolve ambiguity: {inner_outcome.reasons}"],
            affected_topics=[topic_key],
        )

    return WitnessOutcome(
        result=WitnessResult.VALID,
        reasons=[f"disambiguates {target_id!r} via anchor {anchor_id!r}"],
        affected_topics=[topic_key],
    )


WITNESS_CONTRACTS: dict[str, WitnessContract] = {
    "decision.made": witness_decision_made,
    "decision.superseded": witness_decision_superseded,
    "loop.opened": witness_loop_opened,
    "loop.closed": witness_loop_closed,
    "event.disambiguated": witness_event_disambiguated,
}


def evaluate(event: dict, topic_key: str, ledger: Ledger) -> WitnessOutcome:
    """Look up and run the witness contract for event['type']. Caller guarantees the type is known."""
    contract = WITNESS_CONTRACTS[event["type"]]
    return contract(event, topic_key, ledger)
