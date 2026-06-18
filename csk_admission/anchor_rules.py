"""
Witness DSL v1 — a constraint grammar, not a programming language.

witness_loop_closed and witness_decision_superseded (the only two event
types that can be quarantined as AMBIGUOUS) turned out to be the same
shape: resolve via an explicit anchor, or fall back to history if and only
if exactly one candidate exists there. AnchorRule makes that shape data
instead of two near-duplicate hand-written functions, so it declares —
once — what counts as a valid anchor, what happens at zero/one/many
candidates, and what a target must satisfy to be a legal repair. It does
not define new behavior; csk_admission/tests/test_witness_contracts.py and
test_disambiguation.py pass unmodified against it as the proof.

This is deliberately not a textual/parsed grammar: there are exactly two
instances of this shape today, and a string format with no second consumer
would be speculative generality, not a DSL doing real work.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .ledger import Ledger, LedgerState
from .types import WitnessOutcome, WitnessResult


@dataclass(frozen=True)
class AnchorRule:
    event_type: str
    anchor_field: str
    noun: str
    lookup: Callable[[LedgerState, str], Any | None]
    candidates_for_topic: Callable[[LedgerState, str], list]
    record_topic: Callable[[Any], str]
    record_id: Callable[[Any], str]
    is_valid_target: Callable[[Any], bool]
    invalid_target_message: Callable[[str], str]
    zero_candidates_result: WitnessResult
    zero_candidates_message: Callable[[str], str]


def evaluate_anchor_rule(rule: AnchorRule, event: dict, topic_key: str, ledger: Ledger) -> WitnessOutcome:
    state = ledger.state
    anchor_id = event["payload"].get(rule.anchor_field)

    if anchor_id:
        target = rule.lookup(state, anchor_id)
        if target is None:
            return WitnessOutcome(
                result=WitnessResult.INSUFFICIENT_CONTEXT,
                reasons=[f"referenced {rule.noun} {anchor_id!r} does not exist"],
                affected_topics=[topic_key],
            )
        target_topic = rule.record_topic(target)
        if target_topic != topic_key:
            return WitnessOutcome(
                result=WitnessResult.CONTRADICTION,
                reasons=[f"{rule.noun} {anchor_id!r} belongs to topic {target_topic!r}, not {topic_key!r}"],
                affected_topics=[topic_key, target_topic],
            )
        if not rule.is_valid_target(target):
            return WitnessOutcome(
                result=WitnessResult.CONTRADICTION,
                reasons=[rule.invalid_target_message(anchor_id)],
                affected_topics=[topic_key],
            )
        return WitnessOutcome(
            result=WitnessResult.VALID,
            reasons=[f"clean resolution of {anchor_id!r}"],
            affected_topics=[topic_key],
        )

    candidates = rule.candidates_for_topic(state, topic_key)
    if not candidates:
        return WitnessOutcome(
            result=rule.zero_candidates_result,
            reasons=[rule.zero_candidates_message(topic_key)],
            affected_topics=[topic_key],
        )
    if len(candidates) > 1:
        return WitnessOutcome(
            result=WitnessResult.AMBIGUOUS,
            reasons=[
                f"{len(candidates)} historical {rule.noun}s exist for topic {topic_key!r}; "
                f"explicit {rule.anchor_field!r} anchor required"
            ],
            affected_topics=[topic_key],
        )
    only = candidates[0]
    if not rule.is_valid_target(only):
        return WitnessOutcome(
            result=WitnessResult.CONTRADICTION,
            reasons=[rule.invalid_target_message(rule.record_id(only))],
            affected_topics=[topic_key],
        )
    return WitnessOutcome(
        result=WitnessResult.VALID,
        reasons=[f"clean resolution of {rule.record_id(only)!r} (implicit, single candidate)"],
        affected_topics=[topic_key],
    )


LOOP_CLOSED_RULE = AnchorRule(
    event_type="loop.closed",
    anchor_field="loop_id",
    noun="loop",
    lookup=lambda state, anchor_id: state.loop(anchor_id),
    candidates_for_topic=lambda state, topic_key: state.open_loops_for_topic(topic_key),
    record_topic=lambda record: record.topic_key,
    record_id=lambda record: record.loop_id,
    is_valid_target=lambda record: record.status == "OPEN",
    invalid_target_message=lambda anchor_id: f"cannot close non-open loop {anchor_id!r}",
    zero_candidates_result=WitnessResult.CONTRADICTION,
    zero_candidates_message=lambda topic_key: f"cannot close non-open loop: no open loops for topic {topic_key!r}",
)

DECISION_SUPERSEDED_RULE = AnchorRule(
    event_type="decision.superseded",
    anchor_field="supersedes",
    noun="decision",
    lookup=lambda state, anchor_id: state.decision_by_id(anchor_id),
    candidates_for_topic=lambda state, topic_key: state.decisions_for_topic(topic_key),
    record_topic=lambda record: record.topic_key,
    record_id=lambda record: record.event_id,
    is_valid_target=lambda record: record.active,
    invalid_target_message=lambda anchor_id: f"referenced decision {anchor_id!r} is not active",
    zero_candidates_result=WitnessResult.INSUFFICIENT_CONTEXT,
    zero_candidates_message=lambda topic_key: f"no decision history exists for topic {topic_key!r}; nothing to supersede",
)

ANCHOR_RULES: dict[str, AnchorRule] = {
    "loop.closed": LOOP_CLOSED_RULE,
    "decision.superseded": DECISION_SUPERSEDED_RULE,
}
