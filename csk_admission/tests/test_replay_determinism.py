"""
System invariant: replay(events) must produce a deterministic state
independent of ingestion order, assuming identical admitted events.
"""
from csk_admission.ledger import replay
from csk_admission.pipeline import EventAdmissionPipeline


def decision_event(event_id, ts, topic="pricing"):
    return {"v": 1, "id": event_id, "type": "decision.made", "ts": ts, "payload": {"topic": topic}}


def test_replay_is_independent_of_ingestion_order():
    e1 = decision_event("e1", "2026-06-18T00:00:00Z")
    e2 = decision_event("e2", "2026-06-18T01:00:00Z")

    # Ingest in chronological order: e1 wins admission-time VALID.
    p1 = EventAdmissionPipeline()
    p1.ingest(e1)
    p1.ingest(e2)

    # Ingest in reverse order: e2 wins admission-time VALID instead.
    p2 = EventAdmissionPipeline()
    p2.ingest(e2)
    p2.ingest(e1)

    assert {e["id"] for e in p1.ledger.events} == {e["id"] for e in p2.ledger.events} == {"e1", "e2"}

    # Despite differing ingestion order (and differing admission-time VALID
    # assignment above), replay over the committed set is order-independent
    # and always converges on the canonical (ts, id) ordering: e1 first.
    state1 = replay(p1.ledger.events)
    state2 = replay(p2.ledger.events)

    assert state1.active_decision("pricing").event_id == "e1"
    assert state2.active_decision("pricing").event_id == "e1"


def test_replay_of_shuffled_event_list_matches_sorted_list():
    e1 = decision_event("e1", "2026-06-18T00:00:00Z")
    e2 = decision_event("e2", "2026-06-18T01:00:00Z", topic="staffing")
    e3 = decision_event("e3", "2026-06-18T02:00:00Z")  # supersedes nothing -> contradicts e1 on "pricing"

    forward = replay([e1, e2, e3])
    shuffled = replay([e3, e1, e2])
    reversed_ = replay([e3, e2, e1])

    for state in (forward, shuffled, reversed_):
        assert state.active_decision("pricing").event_id == "e1"
        assert state.active_decision("staffing").event_id == "e2"
