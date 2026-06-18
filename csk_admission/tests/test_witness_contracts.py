from csk_admission.ledger import LedgerState, apply_committed_event
from csk_admission.types import WitnessResult
from csk_admission.witness_contracts import evaluate


def decision_event(event_id, topic="pricing", supersedes=None):
    payload = {"topic": topic}
    if supersedes:
        payload["supersedes"] = supersedes
    return {"v": 1, "id": event_id, "type": "decision.made", "ts": "2026-06-18T00:00:00Z", "payload": payload}


def supersede_event(event_id, topic="pricing", supersedes=None):
    payload = {"topic": topic}
    if supersedes:
        payload["supersedes"] = supersedes
    return {"v": 1, "id": event_id, "type": "decision.superseded", "ts": "2026-06-18T00:00:00Z", "payload": payload}


def loop_event(event_id, event_type, loop_id="loop-1"):
    return {"v": 1, "id": event_id, "type": event_type, "ts": "2026-06-18T00:00:00Z", "payload": {"loop_id": loop_id}}


def test_decision_made_first_decision_is_valid():
    state = LedgerState()
    outcome = evaluate(decision_event("e1"), "pricing", state)
    assert outcome.result == WitnessResult.VALID


def test_decision_made_competing_decision_is_contradiction():
    state = LedgerState()
    apply_committed_event(state, decision_event("e1"), "pricing")
    outcome = evaluate(decision_event("e2"), "pricing", state)
    assert outcome.result == WitnessResult.CONTRADICTION


def test_decision_made_explicit_supersede_is_valid():
    state = LedgerState()
    apply_committed_event(state, decision_event("e1"), "pricing")
    outcome = evaluate(decision_event("e2", supersedes="e1"), "pricing", state)
    assert outcome.result == WitnessResult.VALID


def test_decision_superseded_missing_reference_is_insufficient_context():
    state = LedgerState()
    outcome = evaluate(supersede_event("e1"), "pricing", state)
    assert outcome.result == WitnessResult.INSUFFICIENT_CONTEXT


def test_decision_superseded_unknown_reference_is_insufficient_context():
    state = LedgerState()
    outcome = evaluate(supersede_event("e1", supersedes="ghost"), "pricing", state)
    assert outcome.result == WitnessResult.INSUFFICIENT_CONTEXT


def test_decision_superseded_inactive_target_is_contradiction():
    state = LedgerState()
    apply_committed_event(state, decision_event("e1"), "pricing")
    apply_committed_event(state, decision_event("e2", supersedes="e1"), "pricing")  # deactivates e1
    outcome = evaluate(supersede_event("e3", supersedes="e1"), "pricing", state)
    assert outcome.result == WitnessResult.CONTRADICTION


def test_decision_superseded_topic_mismatch_is_contradiction():
    state = LedgerState()
    apply_committed_event(state, decision_event("e1", topic="pricing"), "pricing")
    outcome = evaluate(supersede_event("e2", topic="staffing", supersedes="e1"), "staffing", state)
    assert outcome.result == WitnessResult.CONTRADICTION


def test_decision_superseded_clean_resolution_is_valid():
    state = LedgerState()
    apply_committed_event(state, decision_event("e1"), "pricing")
    outcome = evaluate(supersede_event("e2", supersedes="e1"), "pricing", state)
    assert outcome.result == WitnessResult.VALID


def test_loop_opened_fresh_is_valid():
    state = LedgerState()
    outcome = evaluate(loop_event("e1", "loop.opened"), "loop-1", state)
    assert outcome.result == WitnessResult.VALID


def test_loop_opened_already_open_is_contradiction():
    state = LedgerState()
    apply_committed_event(state, loop_event("e1", "loop.opened"), "loop-1")
    outcome = evaluate(loop_event("e2", "loop.opened"), "loop-1", state)
    assert outcome.result == WitnessResult.CONTRADICTION


def test_loop_closed_non_open_is_contradiction():
    state = LedgerState()
    outcome = evaluate(loop_event("e1", "loop.closed"), "loop-1", state)
    assert outcome.result == WitnessResult.CONTRADICTION


def test_loop_closed_open_loop_is_valid():
    state = LedgerState()
    apply_committed_event(state, loop_event("e1", "loop.opened"), "loop-1")
    outcome = evaluate(loop_event("e2", "loop.closed"), "loop-1", state)
    assert outcome.result == WitnessResult.VALID
