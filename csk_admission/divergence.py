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

from .anchor_rules import ANCHOR_RULES
from .ledger import Ledger
from .topics import extract_topic, normalize_topic
from .types import WitnessResult
from .witness_contracts import WITNESS_CONTRACTS, evaluate


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

        rule = ANCHOR_RULES[event["type"]]
        contract = WITNESS_CONTRACTS[event["type"]]
        raw_candidates = [
            rule.record_id(record) for record in rule.candidates_for_topic(ledger.state, topic_key)
        ]
        candidates = [
            AnchorCandidate(
                anchor_id=candidate_id,
                would_resolve=contract(
                    {**event, "payload": {**event["payload"], rule.anchor_field: candidate_id}},
                    topic_key,
                    ledger,
                ).result,
            )
            for candidate_id in raw_candidates
        ]
        hotspots.append(
            AmbiguityHotspot(event_id=event_id, event_type=event["type"], topic_key=topic_key, candidates=candidates)
        )
    return sorted(hotspots, key=lambda h: h.event_id)


def analyze(ledger: Ledger) -> DivergenceReport:
    return DivergenceReport(hotspots=find_hotspots(ledger))
