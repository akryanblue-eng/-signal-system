"""
V_ref axiomatic definitions.

Fork rule:        exists e1, e2 in CER chain where e1.key == e2.key,
                  e1.value != e2.value, and e1 || e2 (concurrent VCs)
                  -> ForkCertificate

Healing rule:     fork(E) AND merge(e1, e2) converges to a unique fixed point
                  -> HealingTranscript

CannotExpress:    observer visibility is a strict subset of events AND
                  hidden writes could change the type outcome
                  -> CannotExpress
"""
from __future__ import annotations

from ..types import CER


def vector_clock_concurrent(vc1: dict[str, int], vc2: dict[str, int]) -> bool:
    """True iff vc1 and vc2 are incomparable (neither happened-before the other)."""
    all_nodes = set(vc1) | set(vc2)
    vc1_leq = all(vc1.get(n, 0) <= vc2.get(n, 0) for n in all_nodes)
    vc2_leq = all(vc2.get(n, 0) <= vc1.get(n, 0) for n in all_nodes)
    return not vc1_leq and not vc2_leq


def find_fork_pairs(chain: list[CER]) -> list[tuple[CER, CER]]:
    """Return all pairs of concurrent conflicting writes in the CER chain."""
    writes = [c for c in chain if c.event_type == "write"]
    pairs: list[tuple[CER, CER]] = []
    for i, c1 in enumerate(writes):
        for c2 in writes[i + 1:]:
            if (
                c1.key == c2.key
                and c1.value != c2.value
                and vector_clock_concurrent(c1.clock, c2.clock)
            ):
                pairs.append((c1, c2))
    return pairs


def observer_sees_all(scenario: dict) -> bool:
    """True iff every event in the scenario is visible to the declared observer."""
    observer = scenario.get("observer")
    if observer is None:
        return True
    for event in scenario.get("events", []):
        visible_to = event.get("visible_to")
        if visible_to is not None and observer not in visible_to:
            return False
    return True


def visible_events(scenario: dict) -> list[dict]:
    """Return events visible to the observer (all events if no observer declared)."""
    observer = scenario.get("observer")
    if observer is None:
        return scenario.get("events", [])
    return [
        e for e in scenario.get("events", [])
        if e.get("visible_to") is None or observer in e.get("visible_to", [])
    ]


def merge_convergent(c1: CER, c2: CER) -> dict | None:
    """
    Attempt to merge two conflicting write CERs.
    Returns merged value if convergent, None if the conflict is non-mergeable.
    delete vs update is structurally non-mergeable.
    """
    v1, v2 = c1.value, c2.value
    if isinstance(v1, dict) and isinstance(v2, dict):
        if {v1.get("op"), v2.get("op")} == {"delete", "update"}:
            return None
    return None
