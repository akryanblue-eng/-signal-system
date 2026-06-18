"""
event.disambiguated is the only sanctioned path out of AMBIGUOUS quarantine.
CSK never infers an anchor on its own.
"""
from csk_admission.pipeline import EventAdmissionPipeline
from csk_admission.types import Disposition, WitnessResult


def loop_opened(event_id, ts="2026-06-18T00:00:00Z"):
    return {"v": 1, "id": event_id, "type": "loop.opened", "ts": ts, "payload": {"topic": "ops"}}


def loop_closed(event_id, ts="2026-06-18T00:00:00Z"):
    return {"v": 1, "id": event_id, "type": "loop.closed", "ts": ts, "payload": {"topic": "ops"}}


def disambiguated(event_id, target_event_id, chosen_anchor_id, ts="2026-06-18T00:00:00Z"):
    return {
        "v": 1, "id": event_id, "type": "event.disambiguated", "ts": ts,
        "payload": {"topic": "ops", "target_event_id": target_event_id, "chosen_anchor_id": chosen_anchor_id},
    }


def test_ambiguous_close_is_quarantined_until_disambiguated():
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(loop_opened("e1"))
    pipeline.ingest(loop_opened("e2"))

    result = pipeline.ingest(loop_closed("e3"))
    assert result.witness.result == WitnessResult.AMBIGUOUS
    assert result.disposition == Disposition.QUARANTINED
    assert "e3" in pipeline.ledger.quarantine
    assert pipeline.ledger.state.loop("e1").status == "OPEN"
    assert pipeline.ledger.state.loop("e2").status == "OPEN"


def test_disambiguation_promotes_target_and_applies_resolved_anchor():
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(loop_opened("e1"))
    pipeline.ingest(loop_opened("e2"))
    pipeline.ingest(loop_closed("e3"))  # quarantined as AMBIGUOUS

    result = pipeline.ingest(disambiguated("e4", target_event_id="e3", chosen_anchor_id="e1"))

    assert result.disposition == Disposition.COMMITTED
    assert "e3" not in pipeline.ledger.quarantine
    assert pipeline.ledger.state.loop("e1").status == "CLOSED"
    assert pipeline.ledger.state.loop("e2").status == "OPEN"

    # both the disambiguation event and the resolved original are in the committed log
    committed_ids = [e["id"] for e in pipeline.ledger.events]
    assert "e4" in committed_ids
    assert "e3" in committed_ids
    resolved = next(e for e in pipeline.ledger.events if e["id"] == "e3")
    assert resolved["payload"]["loop_id"] == "e1"


def test_disambiguation_with_invalid_anchor_is_contradiction_and_target_stays_quarantined():
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(loop_opened("e1"))
    pipeline.ingest(loop_opened("e2"))
    pipeline.ingest(loop_closed("e3"))  # quarantined as AMBIGUOUS

    result = pipeline.ingest(disambiguated("e4", target_event_id="e3", chosen_anchor_id="not-a-loop"))

    assert result.witness.result == WitnessResult.CONTRADICTION
    assert "e3" in pipeline.ledger.quarantine
    assert pipeline.ledger.state.loop("e1").status == "OPEN"
    assert pipeline.ledger.state.loop("e2").status == "OPEN"


def test_disambiguation_of_unknown_target_is_insufficient_context():
    pipeline = EventAdmissionPipeline()
    result = pipeline.ingest(disambiguated("e1", target_event_id="ghost", chosen_anchor_id="anything"))
    assert result.witness.result == WitnessResult.INSUFFICIENT_CONTEXT
    assert result.disposition == Disposition.QUARANTINED
