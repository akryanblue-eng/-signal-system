from csk_admission.ledger import Ledger, apply_committed_event
from csk_admission.types import WitnessResult
from csk_admission.witness_contracts import evaluate


def decision_event(event_id, topic="pricing", supersedes=None, ts="2026-06-18T00:00:00Z"):
    payload = {"topic": topic}
    if supersedes:
        payload["supersedes"] = supersedes
    return {"v": 1, "id": event_id, "type": "decision.made", "ts": ts, "payload": payload}


def supersede_event(event_id, topic="pricing", supersedes=None, ts="2026-06-18T00:00:00Z"):
    payload = {"topic": topic}
    if supersedes:
        payload["supersedes"] = supersedes
    return {"v": 1, "id": event_id, "type": "decision.superseded", "ts": ts, "payload": payload}


def loop_opened_event(event_id, topic="ops", ts="2026-06-18T00:00:00Z"):
    return {"v": 1, "id": event_id, "type": "loop.opened", "ts": ts, "payload": {"topic": topic}}


def loop_closed_event(event_id, topic="ops", loop_id=None, ts="2026-06-18T00:00:00Z"):
    payload = {"topic": topic}
    if loop_id:
        payload["loop_id"] = loop_id
    return {"v": 1, "id": event_id, "type": "loop.closed", "ts": ts, "payload": payload}


def commit(ledger, event, topic_key):
    apply_committed_event(ledger.state, event, topic_key)


def test_decision_made_first_decision_is_valid():
    ledger = Ledger()
    outcome = evaluate(decision_event("e1"), "pricing", ledger)
    assert outcome.result == WitnessResult.VALID


def test_decision_made_competing_decision_is_contradiction():
    ledger = Ledger()
    commit(ledger, decision_event("e1"), "pricing")
    outcome = evaluate(decision_event("e2"), "pricing", ledger)
    assert outcome.result == WitnessResult.CONTRADICTION


def test_decision_made_explicit_supersede_is_valid():
    ledger = Ledger()
    commit(ledger, decision_event("e1"), "pricing")
    outcome = evaluate(decision_event("e2", supersedes="e1"), "pricing", ledger)
    assert outcome.result == WitnessResult.VALID


def test_decision_superseded_no_history_no_anchor_is_insufficient_context():
    ledger = Ledger()
    outcome = evaluate(supersede_event("e1"), "pricing", ledger)
    assert outcome.result == WitnessResult.INSUFFICIENT_CONTEXT


def test_decision_superseded_unknown_reference_is_insufficient_context():
    ledger = Ledger()
    outcome = evaluate(supersede_event("e1", supersedes="ghost"), "pricing", ledger)
    assert outcome.result == WitnessResult.INSUFFICIENT_CONTEXT


def test_decision_superseded_inactive_target_is_contradiction():
    ledger = Ledger()
    commit(ledger, decision_event("e1"), "pricing")
    commit(ledger, decision_event("e2", supersedes="e1"), "pricing")  # deactivates e1
    outcome = evaluate(supersede_event("e3", supersedes="e1"), "pricing", ledger)
    assert outcome.result == WitnessResult.CONTRADICTION


def test_decision_superseded_topic_mismatch_is_contradiction():
    ledger = Ledger()
    commit(ledger, decision_event("e1", topic="pricing"), "pricing")
    outcome = evaluate(supersede_event("e2", topic="staffing", supersedes="e1"), "staffing", ledger)
    assert outcome.result == WitnessResult.CONTRADICTION


def test_decision_superseded_clean_resolution_is_valid():
    ledger = Ledger()
    commit(ledger, decision_event("e1"), "pricing")
    outcome = evaluate(supersede_event("e2", supersedes="e1"), "pricing", ledger)
    assert outcome.result == WitnessResult.VALID


def test_decision_superseded_single_implicit_candidate_is_valid():
    ledger = Ledger()
    commit(ledger, decision_event("e1"), "pricing")
    outcome = evaluate(supersede_event("e2"), "pricing", ledger)  # no anchor, exactly one candidate
    assert outcome.result == WitnessResult.VALID


def test_decision_superseded_multiple_candidates_no_anchor_is_ambiguous():
    ledger = Ledger()
    commit(ledger, decision_event("e1"), "pricing")
    commit(ledger, decision_event("e2", supersedes="e1"), "pricing")  # second decision on same topic
    outcome = evaluate(supersede_event("e3"), "pricing", ledger)  # no anchor, two candidates in history
    assert outcome.result == WitnessResult.AMBIGUOUS


def test_loop_opened_is_always_valid_even_with_existing_open_loop():
    ledger = Ledger()
    commit(ledger, loop_opened_event("e1"), "ops")
    outcome = evaluate(loop_opened_event("e2"), "ops", ledger)
    assert outcome.result == WitnessResult.VALID


def test_loop_closed_no_open_loops_is_contradiction():
    ledger = Ledger()
    outcome = evaluate(loop_closed_event("e1"), "ops", ledger)
    assert outcome.result == WitnessResult.CONTRADICTION


def test_loop_closed_single_open_loop_implicit_is_valid():
    ledger = Ledger()
    commit(ledger, loop_opened_event("e1"), "ops")
    outcome = evaluate(loop_closed_event("e2"), "ops", ledger)
    assert outcome.result == WitnessResult.VALID


def test_loop_closed_multiple_open_loops_no_anchor_is_ambiguous():
    ledger = Ledger()
    commit(ledger, loop_opened_event("e1"), "ops")
    commit(ledger, loop_opened_event("e2"), "ops")
    outcome = evaluate(loop_closed_event("e3"), "ops", ledger)
    assert outcome.result == WitnessResult.AMBIGUOUS


def test_loop_closed_explicit_anchor_resolves_ambiguity():
    ledger = Ledger()
    commit(ledger, loop_opened_event("e1"), "ops")
    commit(ledger, loop_opened_event("e2"), "ops")
    outcome = evaluate(loop_closed_event("e3", loop_id="e1"), "ops", ledger)
    assert outcome.result == WitnessResult.VALID


def test_loop_closed_unknown_anchor_is_insufficient_context():
    ledger = Ledger()
    outcome = evaluate(loop_closed_event("e1", loop_id="ghost"), "ops", ledger)
    assert outcome.result == WitnessResult.INSUFFICIENT_CONTEXT


def test_loop_closed_anchor_wrong_topic_is_contradiction():
    ledger = Ledger()
    commit(ledger, loop_opened_event("e1", topic="ops"), "ops")
    outcome = evaluate(loop_closed_event("e2", topic="pricing", loop_id="e1"), "pricing", ledger)
    assert outcome.result == WitnessResult.CONTRADICTION


def test_loop_closed_anchor_already_closed_is_contradiction():
    ledger = Ledger()
    commit(ledger, loop_opened_event("e1"), "ops")
    commit(ledger, loop_closed_event("e2", loop_id="e1"), "ops")
    outcome = evaluate(loop_closed_event("e3", loop_id="e1"), "ops", ledger)
    assert outcome.result == WitnessResult.CONTRADICTION
