import platform
from pathlib import Path

from cvp_transition.witness import compute_candidate_digest, is_admissible, validate_witness
from edge_runtime.witness_runner import run_witness

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MORPHISM_PATH = REPO_ROOT / "transition_morphism.json"


def test_run_witness_against_real_morphism_exits_clean():
    _, exit_code = run_witness(MORPHISM_PATH, REPO_ROOT)
    assert exit_code == 0


def test_run_witness_is_schema_valid():
    witness, _ = run_witness(MORPHISM_PATH, REPO_ROOT)
    assert validate_witness(witness) == []


def test_run_witness_is_admissible_for_current_candidate():
    witness, _ = run_witness(MORPHISM_PATH, REPO_ROOT)
    digest = compute_candidate_digest(MORPHISM_PATH)
    ok, msg = is_admissible(witness, digest)
    assert ok, msg


def test_run_witness_records_this_machine_architecture():
    witness, _ = run_witness(MORPHISM_PATH, REPO_ROOT)
    assert witness["environment"]["architecture"] == platform.machine()


def test_run_witness_does_not_modify_morphism_file():
    before = MORPHISM_PATH.read_bytes()
    run_witness(MORPHISM_PATH, REPO_ROOT)
    after = MORPHISM_PATH.read_bytes()
    assert before == after
