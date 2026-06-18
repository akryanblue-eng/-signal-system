"""
EventTypeRegistry — single source of truth for admissible event types.

An event.type not present here is rejected at the admission gate. This is the
mechanism that prevents semantic drift injection: new event semantics can
only enter the system by being declared here first.
"""

EVENT_TYPE_REGISTRY: frozenset[str] = frozenset({
    "decision.made",
    "decision.superseded",
    "loop.opened",
    "loop.closed",
    "event.disambiguated",
})


def is_known_type(event_type: str) -> bool:
    return event_type in EVENT_TYPE_REGISTRY
