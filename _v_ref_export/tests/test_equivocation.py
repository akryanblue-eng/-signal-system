"""
Equivocation scenario: two concurrent writes to the same key.
Oracle output: ForkCertificate.

3 type-closure assertions:
  1. v_ref runner satisfies type closure (returns ForkCertificate)
  2. crdt runner violates type closure (LWW merge returns HealingTranscript)
  3. cvp bridge satisfies type closure (returns ForkCertificate)
"""
import json
from pathlib import Path

from src.types import ForkCertificate, HealingTranscript
from src.validator import check_type_closure
from tests.runners import crdt, cvp, v_ref

SCENARIO = json.loads(
    (Path(__file__).parent / "scenarios" / "equivocation_001.json").read_bytes()
)


def test_v_ref_runner_satisfies_type_closure():
    result = check_type_closure(v_ref.run, "v_ref", SCENARIO)
    assert result.closed, result.violation
    assert result.oracle_type is ForkCertificate


def test_crdt_runner_violates_type_closure():
    """CRDT merges concurrent writes via LWW instead of certifying the fork."""
    result = check_type_closure(crdt.run, "crdt", SCENARIO)
    assert not result.closed, "crdt must fail type closure on equivocation"
    assert result.oracle_type is ForkCertificate
    assert result.runner_output_type is HealingTranscript


def test_cvp_bridge_satisfies_type_closure():
    result = check_type_closure(cvp.run, "cvp_bridge", SCENARIO)
    assert result.closed, result.violation
    assert result.oracle_type is ForkCertificate
