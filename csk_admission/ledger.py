"""
Stage 3 — Ledger Commit Strategy, plus the replayable state model shared
with Stage 2 (witness contracts query this state, and the quarantine store,
read-only).

Commit rules:
    VALID                 -> commit, apply state mutation
    CONTRADICTION          -> commit (materialize the conflict), no mutation, emit DriftEvent
    AMBIGUOUS               -> quarantine, held for resolution
    INSUFFICIENT_CONTEXT     -> quarantine

CSK never hides contradictions — it commits them to history and emits an
explicit drift.detected event rather than silently overwriting canonical
state. CSK never resolves ambiguity implicitly either: an AMBIGUOUS event
sits in quarantine until an explicit `event.disambiguated` event names which
candidate it resolves to (see _promote_disambiguated below).
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
    loop_id: str  # identity = the id of the loop.opened event that created it
    topic_key: str
    status: str  # "OPEN" or "CLOSED"


class LedgerState:
    """Replayable projection: decision history per topic, all decisions by id, loop statuses."""

    def __init__(self) -> None:
        self._decisions_by_topic: dict[str, DecisionRecord] = {}  # active decision per topic
        self._decisions_by_id: dict[str, DecisionRecord] = {}
        self._decision_history_by_topic: dict[str, list[DecisionRecord]] = {}
        self._loops: dict[str, LoopRecord] = {}

    # ── read ─────────────────────────────────────────────────────────────
    def active_decision(self, topic_key: str) -> DecisionRecord | None:
        return self._decisions_by_topic.get(topic_key)

    def decision_by_id(self, event_id: str) -> DecisionRecord | None:
        return self._decisions_by_id.get(event_id)

    def decisions_for_topic(self, topic_key: str) -> list[DecisionRecord]:
        return list(self._decision_history_by_topic.get(topic_key, []))

    def loop(self, loop_id: str) -> LoopRecord | None:
        return self._loops.get(loop_id)

    def open_loops_for_topic(self, topic_key: str) -> list[LoopRecord]:
        return [l for l in self._loops.values() if l.topic_key == topic_key and l.status == "OPEN"]

    # ── mutate (VALID commits only) ─────────────────────────────────────
    def apply_decision_made(self, event_id: str, topic_key: str, payload: dict) -> None:
        prior = self._decisions_by_topic.get(topic_key)
        if prior is not None:
            prior.active = False
        record = DecisionRecord(event_id=event_id, topic_key=topic_key, payload=payload, active=True)
        self._decisions_by_topic[topic_key] = record
        self._decisions_by_id[event_id] = record
        self._decision_history_by_topic.setdefault(topic_key, []).append(record)

    def apply_decision_superseded(self, topic_key: str, explicit_target_id: str | None) -> None:
        if explicit_target_id:
            target = self._decisions_by_id.get(explicit_target_id)
        else:
            candidates = self.decisions_for_topic(topic_key)
            target = candidates[0] if len(candidates) == 1 else None
        if target is None:
            return
        target.active = False
        if self._decisions_by_topic.get(target.topic_key) is target:
            del self._decisions_by_topic[target.topic_key]

    def apply_loop_opened(self, event_id: str, topic_key: str) -> None:
        self._loops[event_id] = LoopRecord(loop_id=event_id, topic_key=topic_key, status="OPEN")

    def apply_loop_closed(self, topic_key: str, explicit_loop_id: str | None) -> None:
        if explicit_loop_id:
            target = self._loops.get(explicit_loop_id)
        else:
            candidates = self.open_loops_for_topic(topic_key)
            target = candidates[0] if len(candidates) == 1 else None
        if target is not None:
            target.status = "CLOSED"


def apply_committed_event(state: LedgerState, event: dict, topic_key: str) -> None:
    """Mutate state for a VALID event. Caller must only call this on VALID results."""
    event_type = event["type"]
    payload = event["payload"]
    if event_type == "decision.made":
        state.apply_decision_made(event["id"], topic_key, payload)
    elif event_type == "decision.superseded":
        state.apply_decision_superseded(topic_key, payload.get("supersedes"))
    elif event_type == "loop.opened":
        state.apply_loop_opened(event["id"], topic_key)
    elif event_type == "loop.closed":
        state.apply_loop_closed(topic_key, payload.get("loop_id"))
    # event.disambiguated mutates nothing directly — its effect is the
    # promotion of a quarantined event, handled by Ledger._promote_disambiguated.


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
        self.quarantine: dict[str, dict] = {}  # keyed by event id, so disambiguation can target it
        self.drift_events: list[DriftEvent] = []
        self.seen_ids: set[str] = set()

    def commit_or_quarantine(
        self, event: dict, topic_key: str, witness: WitnessOutcome
    ) -> tuple[Disposition, DriftEvent | None]:
        self.seen_ids.add(event["id"])

        if witness.result == WitnessResult.VALID:
            apply_committed_event(self.state, event, topic_key)
            self.events.append(event)
            if event["type"] == "event.disambiguated":
                self._promote_disambiguated(event)
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
        self.quarantine[event["id"]] = event
        return Disposition.QUARANTINED, None

    def _promote_disambiguated(self, event: dict) -> None:
        """
        Effect of a VALID event.disambiguated: pull its target out of
        quarantine, bake the chosen anchor into a resolved copy of it, apply
        that copy's mutation, and append it to the committed log. The
        original ambiguous submission is never silently guessed at — it only
        ever enters truth via this explicit, separately-committed pointer.
        """
        from .topics import extract_topic, normalize_topic
        from .witness_contracts import ANCHOR_FIELD

        payload = event["payload"]
        target = self.quarantine.pop(payload["target_event_id"])
        anchor_field = ANCHOR_FIELD[target["type"]]
        resolved = {**target, "payload": {**target["payload"], anchor_field: payload["chosen_anchor_id"]}}
        resolved_topic_key = normalize_topic(extract_topic(resolved["payload"]))
        apply_committed_event(self.state, resolved, resolved_topic_key)
        self.events.append(resolved)


def replay(events: list[dict]) -> LedgerState:
    """
    Deterministically rebuild state from a set of previously-admitted events.
    Events are sorted into canonical order (ts, id) before being applied so
    that replay(events) is independent of the order they are passed in,
    satisfying the system invariant in the spec.

    event.disambiguated entries are administrative audit trail only — their
    effect is already captured by the resolved event Ledger._promote_disambiguated
    appended to the committed log, so replay skips them rather than
    re-deriving quarantine state that no longer exists at replay time.
    """
    from .topics import extract_topic, normalize_topic
    from .witness_contracts import evaluate

    ledger = Ledger()  # scratch ledger; only .state is consulted by the contracts replay uses
    for event in sorted(events, key=lambda e: (e["ts"], e["id"])):
        if event["type"] == "event.disambiguated":
            continue
        topic_key = normalize_topic(extract_topic(event["payload"]))
        if not isinstance(topic_key, str):
            continue  # not replayable in isolation; admission would have rejected it originally
        outcome = evaluate(event, topic_key, ledger)
        if outcome.result == WitnessResult.VALID:
            apply_committed_event(ledger.state, event, topic_key)
    return ledger.state
