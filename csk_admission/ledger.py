"""
Stage 3 — Ledger Commit Strategy, plus the replayable state model shared
with Stage 2 (witness contracts query this state read-only).

Commit rules:
    VALID                 -> commit, apply state mutation
    CONTRADICTION          -> commit (materialize the conflict), no mutation, emit DriftEvent
    AMBIGUOUS               -> quarantine
    INSUFFICIENT_CONTEXT     -> quarantine

CSK never hides contradictions — it commits them to history and emits an
explicit drift.detected event rather than silently overwriting canonical
state.
"""
from __future__ import annotations

from dataclasses import dataclass

from .types import Disposition, DriftEvent, WitnessOutcome, WitnessResult


@dataclass
class DecisionRecord:
    event_id: str
    topic_key: str
    payload: dict
    active: bool = True


@dataclass
class LoopRecord:
    loop_id: str
    status: str  # "OPEN" or "CLOSED"


class LedgerState:
    """Replayable projection: active decision per topic, all decisions by id, loop statuses."""

    def __init__(self) -> None:
        self._decisions_by_topic: dict[str, DecisionRecord] = {}
        self._decisions_by_id: dict[str, DecisionRecord] = {}
        self._loops: dict[str, LoopRecord] = {}

    # ── read ─────────────────────────────────────────────────────────────
    def active_decision(self, topic_key: str) -> DecisionRecord | None:
        return self._decisions_by_topic.get(topic_key)

    def decision_by_id(self, event_id: str) -> DecisionRecord | None:
        return self._decisions_by_id.get(event_id)

    def loop(self, loop_id: str) -> LoopRecord | None:
        return self._loops.get(loop_id)

    # ── mutate (VALID commits only) ─────────────────────────────────────
    def apply_decision_made(self, event_id: str, topic_key: str, payload: dict) -> None:
        prior = self._decisions_by_topic.get(topic_key)
        if prior is not None:
            prior.active = False
        record = DecisionRecord(event_id=event_id, topic_key=topic_key, payload=payload, active=True)
        self._decisions_by_topic[topic_key] = record
        self._decisions_by_id[event_id] = record

    def apply_decision_superseded(self, target_event_id: str) -> None:
        target = self._decisions_by_id.get(target_event_id)
        if target is None:
            return
        target.active = False
        if self._decisions_by_topic.get(target.topic_key) is target:
            del self._decisions_by_topic[target.topic_key]

    def apply_loop_opened(self, loop_id: str) -> None:
        self._loops[loop_id] = LoopRecord(loop_id=loop_id, status="OPEN")

    def apply_loop_closed(self, loop_id: str) -> None:
        existing = self._loops.get(loop_id)
        if existing is not None:
            existing.status = "CLOSED"


def apply_committed_event(state: LedgerState, event: dict, topic_key: str) -> None:
    """Mutate state for a VALID event. Caller must only call this on VALID results."""
    event_type = event["type"]
    payload = event["payload"]
    if event_type == "decision.made":
        state.apply_decision_made(event["id"], topic_key, payload)
    elif event_type == "decision.superseded":
        state.apply_decision_superseded(payload["supersedes"])
    elif event_type == "loop.opened":
        state.apply_loop_opened(payload["loop_id"])
    elif event_type == "loop.closed":
        state.apply_loop_closed(payload["loop_id"])


class Ledger:
    """
    Owns the committed event log, the quarantine store, and the replayable
    state projection. Mirrors the on-disk layout described in the spec:
        /ledger/events.jsonl
        /quarantine/events.jsonl
    (persistence is the caller's responsibility — this class is the in-memory
    authority; see pipeline.EventAdmissionPipeline for jsonl serialization).
    """

    def __init__(self) -> None:
        self.state = LedgerState()
        self.events: list[dict] = []
        self.quarantine: list[dict] = []
        self.drift_events: list[DriftEvent] = []
        self.seen_ids: set[str] = set()

    def commit_or_quarantine(
        self, event: dict, topic_key: str, witness: WitnessOutcome
    ) -> tuple[Disposition, DriftEvent | None]:
        self.seen_ids.add(event["id"])

        if witness.result == WitnessResult.VALID:
            apply_committed_event(self.state, event, topic_key)
            self.events.append(event)
            return Disposition.COMMITTED, None

        if witness.result == WitnessResult.CONTRADICTION:
            self.events.append(event)
            drift = DriftEvent(
                type="drift.detected",
                topic_key=topic_key,
                severity="HIGH",
                source_event_ids=[event["id"]],
            )
            self.drift_events.append(drift)
            return Disposition.COMMITTED, drift

        # AMBIGUOUS, INSUFFICIENT_CONTEXT -> quarantine, no state mutation
        self.quarantine.append(event)
        return Disposition.QUARANTINED, None


def replay(events: list[dict]) -> LedgerState:
    """
    Deterministically rebuild state from a set of previously-admitted events.
    Events are sorted into canonical order (ts, id) before being applied so
    that replay(events) is independent of the order they are passed in,
    satisfying the system invariant in the spec.
    """
    from .topics import extract_topic, normalize_topic
    from .witness_contracts import evaluate

    state = LedgerState()
    for event in sorted(events, key=lambda e: (e["ts"], e["id"])):
        topic_key = normalize_topic(extract_topic(event["payload"]))
        if not isinstance(topic_key, str):
            continue  # not replayable in isolation; admission would have rejected it originally
        outcome = evaluate(event, topic_key, state)
        if outcome.result == WitnessResult.VALID:
            apply_committed_event(state, event, topic_key)
    return state
