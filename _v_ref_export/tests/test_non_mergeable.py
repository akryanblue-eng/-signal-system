"""
Non-mergeable scenario: concurrent delete vs update; merge_function is null.
Oracle output: ForkCertificate.

3 type-closure assertions:
  1. v_ref runner satisfies type closure (ForkCertificate)
  2. crdt runner violates type closure (LWW on delete/update returns HealingTranscript)
  3. kafka runner violates type closure (append-only returns CannotExpress)
"""
import json
from pathlib import Path

from src.types import CannotExpress, ForkCertificate, HealingTranscript
from src.validator import check_type_closure
from tests.runners import crdt, kafka, v_ref

SCENARIO = json.loads(
    (Path(__file__).parent / "scenarios" / "non_mergeable_001.json").read_bytes()
)


def test_v_ref_runner_satisfies_type_closure():
    result = check_type_closure(v_ref.run, "v_ref", SCENARIO)
    assert result.closed, result.violation
    assert result.oracle_type is ForkCertificate


def test_crdt_runner_claims_spurious_healing():
    """CRDT applies LWW to a delete/update conflict it cannot actually resolve."""
    result = check_type_closure(crdt.run, "crdt", SCENARIO)
    assert not result.closed, "crdt must fail type closure on non_mergeable"
    assert result.oracle_type is ForkCertificate
    assert result.runner_output_type is HealingTranscript


def test_kafka_runner_violates_type_closure():
    """Kafka emits CannotExpress (append-only) instead of ForkCertificate."""
    result = check_type_closure(kafka.run, "kafka", SCENARIO)
    assert not result.closed, "kafka must fail type closure on non_mergeable"
    assert result.oracle_type is ForkCertificate
    assert result.runner_output_type is CannotExpress
