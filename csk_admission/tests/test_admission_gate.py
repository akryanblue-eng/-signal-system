from csk_admission.admission_gate import admit
from csk_admission.types import AdmissionStatus


def make_event(event_id="e1", event_type="decision.made", payload=None, ts="2026-06-18T00:00:00Z", v=1):
    if payload is None:
        payload = {"topic": "pricing"}
    return {"v": v, "id": event_id, "type": event_type, "ts": ts, "payload": payload}


def test_admits_well_formed_event():
    result = admit(make_event(), seen_ids=set())
    assert result.status == AdmissionStatus.ADMITTED
    assert result.topic_key == "pricing"


def test_rejects_missing_field():
    event = make_event()
    del event["ts"]
    result = admit(event, seen_ids=set())
    assert result.status == AdmissionStatus.REJECTED
    assert "missing field" in result.reasons[0]


def test_rejects_unknown_schema_version():
    result = admit(make_event(v=2), seen_ids=set())
    assert result.status == AdmissionStatus.REJECTED
    assert "schema version" in result.reasons[0]


def test_rejects_non_unique_id():
    result = admit(make_event(event_id="dup"), seen_ids={"dup"})
    assert result.status == AdmissionStatus.REJECTED
    assert "non-unique id" in result.reasons[0]


def test_rejects_unknown_event_type():
    result = admit(make_event(event_type="nonsense.event"), seen_ids=set())
    assert result.status == AdmissionStatus.REJECTED
    assert "unknown event type" in result.reasons[0]


def test_rejects_invalid_timestamp():
    result = admit(make_event(ts="not-a-timestamp"), seen_ids=set())
    assert result.status == AdmissionStatus.REJECTED
    assert "invalid timestamp" in result.reasons[0]


def test_rejects_non_object_payload():
    event = make_event()
    event["payload"] = "not-an-object"
    result = admit(event, seen_ids=set())
    assert result.status == AdmissionStatus.REJECTED


def test_rejects_missing_topic():
    result = admit(make_event(payload={}), seen_ids=set())
    assert result.status == AdmissionStatus.REJECTED
    assert "topic resolution failed" in result.reasons[0]


def test_rejects_ambiguous_multi_topic():
    result = admit(make_event(payload={"topics": ["pricing", "staffing"]}), seen_ids=set())
    assert result.status == AdmissionStatus.REJECTED
    assert "ambiguous" in result.reasons[0]


def test_topic_normalization():
    result = admit(make_event(payload={"topic": "  Pricing   Strategy  "}), seen_ids=set())
    assert result.status == AdmissionStatus.ADMITTED
    assert result.topic_key == "pricing strategy"
