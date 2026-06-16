"""
Kafka mock runner: append-only log, no fork detection.

Returns CannotExpress over the full event log regardless of observer
visibility or conflict structure. Type closure violations:
  - non_mergeable: returns CannotExpress, oracle expects ForkCertificate
Information leakage violation:
  - partial_observer: returns all events including hidden ones
"""
from src.types import CannotExpress


def run(scenario: dict) -> CannotExpress:
    return CannotExpress(
        scenario_id=scenario["scenario_id"],
        reason="kafka_append_only_log",
        partial_observations=scenario.get("events", []),
    )
