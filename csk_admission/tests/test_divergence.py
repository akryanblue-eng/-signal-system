from csk_admission.divergence import analyze
from csk_admission.pipeline import EventAdmissionPipeline
from csk_admission.types import WitnessResult


def loop_opened(event_id, ts="2026-06-18T00:00:00Z"):
    return {"v": 1, "id": event_id, "type": "loop.opened", "ts": ts, "payload": {"topic": "ops"}}


def loop_closed(event_id, loop_id=None, ts="2026-06-18T00:00:00Z"):
    payload = {"topic": "ops"}
    if loop_id:
        payload["loop_id"] = loop_id
    return {"v": 1, "id": event_id, "type": "loop.closed", "ts": ts, "payload": payload}


def decision_made(event_id, supersedes=None, ts="2026-06-18T00:00:00Z"):
    payload = {"topic": "pricing"}
    if supersedes:
        payload["supersedes"] = supersedes
    return {"v": 1, "id": event_id, "type": "decision.made", "ts": ts, "payload": payload}


def decision_superseded(event_id, ts="2026-06-18T00:00:00Z"):
    return {"v": 1, "id": event_id, "type": "decision.superseded", "ts": ts, "payload": {"topic": "pricing"}}


def test_no_hotspots_when_quarantine_empty():
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(loop_opened("e1"))
    report = analyze(pipeline.ledger)
    assert report.hotspots == []
    assert report.collapse_paths == {}


def test_loop_closed_ambiguity_surfaces_both_open_loops_as_collapsing_anchors():
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(loop_opened("e1"))
    pipeline.ingest(loop_opened("e2"))
    pipeline.ingest(loop_closed("e3"))  # quarantined: AMBIGUOUS

    report = analyze(pipeline.ledger)
    assert len(report.hotspots) == 1
    hotspot = report.hotspots[0]
    assert hotspot.event_id == "e3"
    assert hotspot.event_type == "loop.closed"
    assert sorted(c.anchor_id for c in hotspot.candidates) == ["e1", "e2"]
    assert all(c.would_resolve == WitnessResult.VALID for c in hotspot.candidates)
    assert sorted(hotspot.collapse_anchors) == ["e1", "e2"]
    assert report.collapse_paths == {"e3": sorted(report.collapse_paths["e3"])}


def test_decision_superseded_ambiguity_excludes_inactive_candidate_from_collapse_anchors():
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(decision_made("e1"))
    pipeline.ingest(decision_made("e2", supersedes="e1"))  # e1 now inactive, e2 active
    pipeline.ingest(decision_superseded("e3"))  # no anchor, 2 historical candidates -> AMBIGUOUS

    report = analyze(pipeline.ledger)
    assert len(report.hotspots) == 1
    hotspot = report.hotspots[0]
    assert hotspot.event_id == "e3"
    candidates_by_id = {c.anchor_id: c.would_resolve for c in hotspot.candidates}
    assert candidates_by_id == {"e1": WitnessResult.CONTRADICTION, "e2": WitnessResult.VALID}
    assert hotspot.collapse_anchors == ["e2"]
    assert report.collapse_paths == {"e3": ["e2"]}


def test_resolving_one_hotspot_via_disambiguation_removes_it_from_report():
    pipeline = EventAdmissionPipeline()
    pipeline.ingest(loop_opened("e1"))
    pipeline.ingest(loop_opened("e2"))
    pipeline.ingest(loop_closed("e3"))  # quarantined: AMBIGUOUS

    pipeline.ingest(
        {
            "v": 1, "id": "e4", "type": "event.disambiguated", "ts": "2026-06-18T00:00:00Z",
            "payload": {"topic": "ops", "target_event_id": "e3", "chosen_anchor_id": "e1"},
        }
    )

    report = analyze(pipeline.ledger)
    assert report.hotspots == []
