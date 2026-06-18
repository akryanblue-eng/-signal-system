from csk_admission.ambiguity_debt import check, compute_debt, load_ledger
from csk_admission.pipeline import EventAdmissionPipeline


def loop_opened(event_id, ts="2026-06-18T00:00:00Z"):
    return {"v": 1, "id": event_id, "type": "loop.opened", "ts": ts, "payload": {"topic": "ops"}}


def loop_closed(event_id, ts="2026-06-18T00:00:00Z"):
    return {"v": 1, "id": event_id, "type": "loop.closed", "ts": ts, "payload": {"topic": "ops"}}


def decision_made(event_id, supersedes=None, ts="2026-06-18T00:00:00Z"):
    payload = {"topic": "pricing"}
    if supersedes:
        payload["supersedes"] = supersedes
    return {"v": 1, "id": event_id, "type": "decision.made", "ts": ts, "payload": payload}


def decision_superseded(event_id, supersedes=None, ts="2026-06-18T00:00:00Z"):
    payload = {"topic": "pricing"}
    if supersedes:
        payload["supersedes"] = supersedes
    return {"v": 1, "id": event_id, "type": "decision.superseded", "ts": ts, "payload": payload}


def test_recoverable_ambiguity_is_zero_debt():
    # two open loops, one ambiguous close -> hotspot exists but both anchors
    # would resolve cleanly, so this is backlog, not debt.
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(loop_opened("e1"))
    pipeline.ingest(loop_opened("e2"))
    pipeline.ingest(loop_closed("e3"))

    debt = compute_debt(pipeline.ledger)
    assert debt["total_hotspots"] == 1
    assert debt["stuck_hotspots"] == 0
    assert debt["stuck_event_ids"] == []


def test_ambiguity_with_no_viable_anchor_is_debt():
    # e1, e2 both end up inactive (e1 superseded by e2, e2 explicitly
    # superseded by e3) before the ambiguous e4 arrives with no active
    # decision left at all -> both historical candidates resolve to
    # CONTRADICTION, so this hotspot is genuinely stuck.
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(decision_made("e1"))
    pipeline.ingest(decision_made("e2", supersedes="e1"))
    pipeline.ingest(decision_superseded("e3", supersedes="e2"))
    result = pipeline.ingest(decision_superseded("e4"))  # 2 historical candidates, no anchor -> AMBIGUOUS

    debt = compute_debt(pipeline.ledger)
    assert result.witness.result.value == "AMBIGUOUS"
    assert debt["total_hotspots"] == 1
    assert debt["stuck_hotspots"] == 1
    assert debt["stuck_event_ids"] == ["e4"]


def test_persist_then_load_round_trips_into_same_debt(tmp_path):
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(loop_opened("e1"))
    pipeline.ingest(loop_opened("e2"))
    pipeline.ingest(loop_closed("e3"))

    pipeline.persist(tmp_path)
    reloaded = load_ledger(tmp_path)

    direct_debt = compute_debt(pipeline.ledger)
    reloaded_debt = compute_debt(reloaded)
    assert direct_debt == reloaded_debt


def test_check_passes_when_debt_equals_baseline(tmp_path):
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(loop_opened("e1"))
    pipeline.persist(tmp_path)

    passed, current = check(tmp_path, baseline={"stuck_hotspots": 0})
    assert passed
    assert current["stuck_hotspots"] == 0


def test_check_fails_when_debt_increases_over_baseline(tmp_path):
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(decision_made("e1"))
    pipeline.ingest(decision_made("e2", supersedes="e1"))
    pipeline.ingest(decision_superseded("e3", supersedes="e2"))
    pipeline.ingest(decision_superseded("e4"))  # stuck: no active candidate left
    pipeline.persist(tmp_path)

    passed, current = check(tmp_path, baseline={"stuck_hotspots": 1})
    assert current["stuck_hotspots"] == 1
    assert passed  # equal to baseline is allowed

    passed, current = check(tmp_path, baseline={"stuck_hotspots": 0})
    assert not passed  # any increase over baseline fails
