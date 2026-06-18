from csk_admission.ledger import Ledger
from csk_admission.pipeline import EventAdmissionPipeline
from csk_admission.types import Disposition, WitnessOutcome, WitnessResult


def decision_event(event_id, topic="pricing", supersedes=None, ts="2026-06-18T00:00:00Z"):
    payload = {"topic": topic}
    if supersedes:
        payload["supersedes"] = supersedes
    return {"v": 1, "id": event_id, "type": "decision.made", "ts": ts, "payload": payload}


def test_valid_event_commits_without_drift():
    pipeline = EventAdmissionPipeline()
    result = pipeline.ingest(decision_event("e1"))
    assert result.disposition == Disposition.COMMITTED
    assert result.drift_event is None
    assert pipeline.ledger.events == [decision_event("e1")]


def test_contradiction_commits_and_emits_drift():
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(decision_event("e1"))
    result = pipeline.ingest(decision_event("e2"))

    assert result.witness.result == WitnessResult.CONTRADICTION
    assert result.disposition == Disposition.COMMITTED
    assert result.drift_event is not None
    assert result.drift_event.type == "drift.detected"
    assert result.drift_event.topic_key == "pricing"
    assert len(pipeline.ledger.events) == 2
    assert len(pipeline.ledger.drift_events) == 1


def test_malformed_event_is_rejected_and_never_reaches_ledger():
    pipeline = EventAdmissionPipeline()
    bad_event = {"v": 1, "id": "e1", "type": "decision.made", "ts": "garbage", "payload": {"topic": "x"}}
    result = pipeline.ingest(bad_event)
    assert result.disposition == Disposition.REJECTED
    assert pipeline.ledger.events == []


def test_insufficient_context_is_quarantined():
    pipeline = EventAdmissionPipeline()
    event = {
        "v": 1, "id": "e1", "type": "decision.superseded",
        "ts": "2026-06-18T00:00:00Z", "payload": {"topic": "pricing"},  # no 'supersedes'
    }
    result = pipeline.ingest(event)
    assert result.witness.result == WitnessResult.INSUFFICIENT_CONTEXT
    assert result.disposition == Disposition.QUARANTINED
    assert pipeline.ledger.events == []
    assert len(pipeline.ledger.quarantine) == 1


def test_witness_chain_records_all_stages_on_commit():
    pipeline = EventAdmissionPipeline()
    result = pipeline.ingest(decision_event("e1"))
    assert result.witness_chain == ["admission_gate:v1", "witness_contract:decision.made:v1", "ledger_commit:v1"]


def test_witness_chain_stops_at_admission_on_rejection():
    pipeline = EventAdmissionPipeline()
    bad_event = {"v": 1, "id": "e1", "type": "nonsense", "ts": "2026-06-18T00:00:00Z", "payload": {"topic": "x"}}
    result = pipeline.ingest(bad_event)
    assert result.witness_chain == ["admission_gate:v1"]


def test_ledger_commit_rule_table_for_all_witness_results():
    rules = {
        WitnessResult.VALID: Disposition.COMMITTED,
        WitnessResult.CONTRADICTION: Disposition.COMMITTED,
        WitnessResult.AMBIGUOUS: Disposition.QUARANTINED,
        WitnessResult.INSUFFICIENT_CONTEXT: Disposition.QUARANTINED,
    }
    for i, (result, expected_disposition) in enumerate(rules.items()):
        ledger = Ledger()
        event = decision_event(f"e{i}")
        disposition, _ = ledger.commit_or_quarantine(event, "pricing", WitnessOutcome(result=result))
        assert disposition == expected_disposition
