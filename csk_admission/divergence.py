"""
Replay Divergence Engine — static analysis over the quarantine store and
the replayable LedgerState. It sits outside the admission/witness/commit
runtime: it never mutates the ledger, never participates in ingest(), and
is not consulted by replay(). It only answers a diagnostic question after
the fact: "of the events currently sitting in AMBIGUOUS quarantine, which
anchors would resolve each one, and which of those would actually work?"

CSK never forks ledger state — an AMBIGUOUS event is held, not branched
into multiple parallel interpretations (see docs: forked-history ambiguity
/ Case C is out of scope). So there is no combinatorial set of possible
ledger states to enumerate here. The real divergence surface in this model
is per-event: each AMBIGUOUS event has a finite set of anchor candidates
already visible in history, and exactly one ANCHOR_FIELD to inject one
into. This module computes that set and classifies each candidate by
reusing the same anchor-injection + witness-contract-replay mechanism that
event.disambiguated itself uses — no new resolution primitives, no
heuristic inference from event meaning.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ledger import Ledger, LedgerState
from .topics import extract_topic, normalize_topic
from .types import WitnessResult
from .witness_contracts import ANCHOR_FIELD, WITNESS_CONTRACTS, evaluate


@dataclass
class AnchorCandidate:
    anchor_id: str
    would_resolve: WitnessResult


@dataclass
class AmbiguityHotspot:
    event_id: str
    event_type: str
    topic_key: str
    candidates: list[AnchorCandidate] = field(default_factory=list)

    @property
    def collapse_anchors(self) -> list[str]:
        """Anchors that would actually resolve this hotspot to VALID."""
        return [c.anchor_id for c in self.candidates if c.would_resolve == WitnessResult.VALID]


@dataclass
class DivergenceReport:
    hotspots: list[AmbiguityHotspot] = field(default_factory=list)

    @property
    def collapse_paths(self) -> dict[str, list[str]]:
        """event_id -> anchors that would resolve it to VALID, for hotspots that have one."""
        return {h.event_id: h.collapse_anchors for h in self.hotspots if h.collapse_anchors}


def _raw_candidates(event_type: str, topic_key: str, state: LedgerState) -> list[str]:
    if event_type == "loop.closed":
        return [loop.loop_id for loop in state.open_loops_for_topic(topic_key)]
    if event_type == "decision.superseded":
        return [decision.event_id for decision in state.decisions_for_topic(topic_key)]
    return []


def find_hotspots(ledger: Ledger) -> list[AmbiguityHotspot]:
    """
    Re-evaluate every quarantined event against the current ledger and keep
    only the ones currently classified AMBIGUOUS (history-dependent
    ambiguity, not INSUFFICIENT_CONTEXT). For each, enumerate the anchor
    candidates visible in history right now and classify what witness
    result choosing each one would produce.
    """
    hotspots = []
    for event_id, event in ledger.quarantine.items():
        topic_key = normalize_topic(extract_topic(event["payload"]))
        if not isinstance(topic_key, str):
            continue
        outcome = evaluate(event, topic_key, ledger)
        if outcome.result != WitnessResult.AMBIGUOUS:
            continue

        anchor_field = ANCHOR_FIELD[event["type"]]
        contract = WITNESS_CONTRACTS[event["type"]]
        candidates = [
            AnchorCandidate(
                anchor_id=candidate_id,
                would_resolve=contract(
                    {**event, "payload": {**event["payload"], anchor_field: candidate_id}},
                    topic_key,
                    ledger,
                ).result,
            )
            for candidate_id in _raw_candidates(event["type"], topic_key, ledger.state)
        ]
        hotspots.append(
            AmbiguityHotspot(event_id=event_id, event_type=event["type"], topic_key=topic_key, candidates=candidates)
        )
    return sorted(hotspots, key=lambda h: h.event_id)


def analyze(ledger: Ledger) -> DivergenceReport:
    return DivergenceReport(hotspots=find_hotspots(ledger))
