"""
Partial observer scenario: observer O sees only N1's write; N2's write is hidden.
Oracle output: CannotExpress.

3 type-closure assertions:
  1. v_ref runner satisfies type closure (CannotExpress over visible events only)
  2. crdt runner violates type closure (ignores visibility, returns HealingTranscript)
  3. kafka runner information-leakage: type matches oracle but exposes hidden event
"""
import json
from pathlib import Path

from src.types import CannotExpress, HealingTranscript
from src.validator import check_type_closure
from tests.runners import crdt, kafka, v_ref

SCENARIO = json.loads(
    (Path(__file__).parent / "scenarios" / "partial_observer_001.json").read_bytes()
)


def test_v_ref_runner_satisfies_type_closure():
    result = check_type_closure(v_ref.run, "v_ref", SCENARIO)
    assert result.closed, result.violation
    assert result.oracle_type is CannotExpress


def test_crdt_runner_violates_type_closure():
    """CRDT ignores observer visibility, processes both writes, returns HealingTranscript."""
    result = check_type_closure(crdt.run, "crdt", SCENARIO)
    assert not result.closed, "crdt must fail type closure on partial_observer"
    assert result.oracle_type is CannotExpress
    assert result.runner_output_type is HealingTranscript


def test_kafka_runner_leaks_hidden_event():
    """
    Kafka returns CannotExpress (type matches oracle) but its partial_observations
    include event e2 which observer O cannot see — information-leakage violation.
    The oracle correctly excludes e2; Kafka does not.
    """
    oracle_output = v_ref.run(SCENARIO)
    kafka_output = kafka.run(SCENARIO)

    assert isinstance(oracle_output, CannotExpress)
    assert isinstance(kafka_output, CannotExpress)

    oracle_ids = {e["event_id"] for e in oracle_output.partial_observations}
    kafka_ids = {e["event_id"] for e in kafka_output.partial_observations}

    leaked = kafka_ids - oracle_ids
    assert leaked, (
        f"Kafka must leak hidden events to demonstrate information-leakage; "
        f"oracle_ids={oracle_ids}, kafka_ids={kafka_ids}"
    )
