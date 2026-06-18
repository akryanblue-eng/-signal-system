"""
Adversarial / fuzz testing over the full pipeline.

This does not add new semantics — it stress-tests the invariants the spec
already claims, using randomly generated event sequences instead of
hand-picked scenarios:

  - admission + witness evaluation never raises, for any structurally valid
    envelope shape
  - disposition/result pairs always match the documented commit table
    (csk_admission/ledger.py docstring): VALID/CONTRADICTION -> COMMITTED,
    AMBIGUOUS/INSUFFICIENT_CONTEXT -> QUARANTINED
  - CONTRADICTION and quarantine never mutate LedgerState
  - committed and quarantined event ids are always disjoint
  - replay(events) converges to the same state regardless of the order the
    committed event set is replayed in
  - divergence.analyze / ambiguity_debt.compute_debt never raise and stay
    internally consistent with the quarantine store
  - witness contracts are pure: evaluating the same quarantined event twice
    against the same ledger gives the same result both times

Anchors (`supersedes`, `loop_id`, disambiguation targets) are deliberately
drawn from a mix of real prior ids, garbage ids, and omitted values, and the
topic pool is kept small (3 topics) relative to event count, so collisions
land squarely on the VALID/CONTRADICTION/AMBIGUOUS/INSUFFICIENT_CONTEXT
boundaries instead of mostly missing them.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from csk_admission.ambiguity_debt import compute_debt
from csk_admission.divergence import analyze
from csk_admission.ledger import replay
from csk_admission.pipeline import EventAdmissionPipeline
from csk_admission.topics import extract_topic, normalize_topic
from csk_admission.types import Disposition, WitnessResult
from csk_admission.witness_contracts import evaluate

TOPICS = ["alpha", "beta", "gamma"]
BASE_TS = datetime(2026, 1, 1)
SEEDS = range(150)
EVENTS_PER_RUN = 40


def _ts(rng: random.Random) -> str:
    return (BASE_TS + timedelta(seconds=rng.randint(0, 100_000))).strftime("%Y-%m-%dT%H:%M:%SZ")


def _anchor(rng: random.Random, known_ids: list[str]) -> str | None:
    """None (implicit fallback), a real known id (valid target), or a garbage id (unresolvable)."""
    roll = rng.random()
    if roll < 0.34 or not known_ids:
        return None
    if roll < 0.67:
        return rng.choice(known_ids)
    return f"ghost-{rng.randint(0, 999)}"


def _gen_event(
    rng: random.Random, i: int, decision_ids: list[str], loop_ids: list[str], quarantined_ids: list[str]
) -> dict:
    topic = rng.choice(TOPICS)
    event_id = f"e{i}"
    ts = _ts(rng)
    kind = rng.choice(
        [
            "decision.made", "decision.made",
            "decision.superseded", "decision.superseded",
            "loop.opened", "loop.opened",
            "loop.closed", "loop.closed",
            "event.disambiguated",
        ]
    )

    if kind in ("decision.made", "decision.superseded"):
        payload = {"topic": topic}
        anchor = _anchor(rng, decision_ids)
        if anchor:
            payload["supersedes"] = anchor
    elif kind == "loop.opened":
        payload = {"topic": topic}
    elif kind == "loop.closed":
        payload = {"topic": topic}
        anchor = _anchor(rng, loop_ids)
        if anchor:
            payload["loop_id"] = anchor
    else:  # event.disambiguated
        if not quarantined_ids:
            return {"v": 1, "id": event_id, "type": "loop.opened", "ts": ts, "payload": {"topic": topic}}
        target = rng.choice(quarantined_ids)
        candidate_pool = decision_ids + loop_ids
        chosen = rng.choice(candidate_pool) if candidate_pool and rng.random() < 0.8 else f"ghost-{rng.randint(0, 999)}"
        payload = {"topic": topic, "target_event_id": target, "chosen_anchor_id": chosen}

    return {"v": 1, "id": event_id, "type": kind, "ts": ts, "payload": payload}


def _snapshot(state) -> dict:
    """Full externally-observable surface of LedgerState -- there is no other mutation target."""
    return {
        "active": {t: (state.active_decision(t).event_id if state.active_decision(t) else None) for t in TOPICS},
        "decisions": {t: [(d.event_id, d.active) for d in state.decisions_for_topic(t)] for t in TOPICS},
        "open_loops": {t: sorted(l.loop_id for l in state.open_loops_for_topic(t)) for t in TOPICS},
    }


def test_fuzz_invariants_hold_across_random_sequences():
    for seed in SEEDS:
        rng = random.Random(seed)
        pipeline = EventAdmissionPipeline()
        decision_ids: list[str] = []
        loop_ids: list[str] = []
        quarantined_ids: list[str] = []

        for i in range(EVENTS_PER_RUN):
            event = _gen_event(rng, i, decision_ids, loop_ids, quarantined_ids)
            pre = _snapshot(pipeline.ledger.state)

            result = pipeline.ingest(event)  # must never raise

            if result.disposition == Disposition.REJECTED:
                assert result.witness is None
            elif result.disposition == Disposition.COMMITTED:
                assert result.witness.result in (WitnessResult.VALID, WitnessResult.CONTRADICTION)
                if result.witness.result == WitnessResult.CONTRADICTION:
                    assert _snapshot(pipeline.ledger.state) == pre, f"seed={seed} i={i}: CONTRADICTION mutated state"
            elif result.disposition == Disposition.QUARANTINED:
                assert result.witness.result in (WitnessResult.AMBIGUOUS, WitnessResult.INSUFFICIENT_CONTEXT)
                assert _snapshot(pipeline.ledger.state) == pre, f"seed={seed} i={i}: quarantine mutated state"

            if result.witness is not None and result.witness.result == WitnessResult.VALID:
                if event["type"] == "decision.made":
                    decision_ids.append(event["id"])
                elif event["type"] == "loop.opened":
                    loop_ids.append(event["id"])
                elif event["type"] == "event.disambiguated":
                    target = event["payload"]["target_event_id"]
                    if target in quarantined_ids:
                        quarantined_ids.remove(target)
            if result.disposition == Disposition.QUARANTINED:
                quarantined_ids.append(event["id"])

        committed_ids = {e["id"] for e in pipeline.ledger.events}
        assert committed_ids.isdisjoint(pipeline.ledger.quarantine.keys()), f"seed={seed}: non-disjoint terminal state"

        committed_events = list(pipeline.ledger.events)
        canonical = _snapshot(replay(committed_events))
        for _ in range(5):
            shuffled = committed_events[:]
            rng.shuffle(shuffled)
            assert _snapshot(replay(shuffled)) == canonical, f"seed={seed}: replay order-dependence detected"

        report = analyze(pipeline.ledger)
        for hotspot in report.hotspots:
            assert hotspot.event_id in pipeline.ledger.quarantine
            for candidate in hotspot.candidates:
                assert isinstance(candidate.would_resolve, WitnessResult)

        debt = compute_debt(pipeline.ledger)
        assert debt["total_hotspots"] == len(report.hotspots)
        assert debt["stuck_hotspots"] <= debt["total_hotspots"]
        assert set(debt["stuck_event_ids"]) <= {h.event_id for h in report.hotspots}

        hotspot_ids = {h.event_id for h in report.hotspots}
        for event_id, quarantined_event in pipeline.ledger.quarantine.items():
            topic_key = normalize_topic(extract_topic(quarantined_event["payload"]))
            first = evaluate(quarantined_event, topic_key, pipeline.ledger)
            second = evaluate(quarantined_event, topic_key, pipeline.ledger)
            assert first.result == second.result
            assert first.reasons == second.reasons

            # find_hotspots() re-derives AMBIGUOUS internally; cross-check that
            # derivation independently against the same witness contract so a
            # bug in its filtering can't silently suppress or fabricate hotspots.
            is_ambiguous = first.result == WitnessResult.AMBIGUOUS
            assert (event_id in hotspot_ids) == is_ambiguous, (
                f"seed={seed}: hotspot/witness mismatch for {event_id} "
                f"(in hotspots={event_id in hotspot_ids}, witness AMBIGUOUS={is_ambiguous})"
            )
