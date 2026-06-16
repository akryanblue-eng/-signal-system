"""
CRDT mock runner using Last-Write-Wins (max node ID).

Ignores observer visibility and vector-clock concurrency structure.
Merges all multi-write keys deterministically, returning HealingTranscript
for any conflict. Type closure violations:
  - equivocation: returns HealingTranscript, oracle expects ForkCertificate
  - partial_observer: returns HealingTranscript, oracle expects CannotExpress
  - non_mergeable: returns HealingTranscript, oracle expects ForkCertificate
"""
from src.types import CannotExpress, HealingTranscript


def run(scenario: dict) -> object:
    scenario_id = scenario["scenario_id"]
    events = scenario.get("events", [])
    writes = [e for e in events if e.get("type") == "write"]

    by_key: dict[str, list[dict]] = {}
    for w in writes:
        by_key.setdefault(w["key"], []).append(w)

    merged_state: dict = {}
    healing_steps: list[str] = []
    pre_state: dict = {}

    for key, ws in by_key.items():
        if len(ws) == 1:
            merged_state[key] = ws[0]["value"]
        else:
            winner = max(ws, key=lambda w: w["node"])
            merged_state[key] = winner["value"]
            pre_state[key] = [w["value"] for w in ws]
            healing_steps.append(f"LWW on key={key!r}: winner=node:{winner['node']!r}")

    if healing_steps:
        return HealingTranscript(
            scenario_id=scenario_id,
            pre_state=pre_state,
            post_state=merged_state,
            healing_steps=healing_steps,
            convergent=True,
        )
    return CannotExpress(
        scenario_id=scenario_id,
        reason="crdt_no_conflicts",
        partial_observations=events,
    )
