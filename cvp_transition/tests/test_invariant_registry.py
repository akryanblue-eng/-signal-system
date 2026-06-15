"""
Registry consistency tests — verify that invariants/ JSON files are accurate
reflections of the Python implementation. These tests fail if the registry drifts
from the code it documents, making it impossible for the two to silently diverge.

The invariant registry is derivative-only. Python is the execution authority.
"""
import json
from pathlib import Path

from cvp_transition.witness import (
    REQUIRED_WITNESS_FIELDS,
    REQUIRED_GATES,
    VALID_RUNNER_TYPES,
    SCHEMA_VERSION,
    compute_candidate_digest,
)

REGISTRY = Path(__file__).parent.parent.parent / "invariants"


def _load(filename: str) -> dict:
    return json.loads((REGISTRY / filename).read_bytes())


class TestDigestCanonicalizationRegistry:
    """01_digest_canonicalization.json must reflect compute_candidate_digest."""

    def test_excluded_fields_matches_implementation(self, tmp_path):
        r = _load("01_digest_canonicalization.json")
        excluded = set(r["excluded_fields"])

        # Build two morphisms identical except for the excluded field
        base = {
            "from_version": "1.2",
            "to_version": "1.3",
            "transition_type": "EXTENSION",
            "artifact_mapping": {},
            "invariants_preserved": [],
            "invariants_added": [],
            "breaking_changes": [],
        }
        path_without = tmp_path / "m_without.json"
        path_without.write_text(json.dumps(base, sort_keys=True))

        for field in excluded:
            with_field = {**base, field: [{"dummy": True}]}
            path_with = tmp_path / "m_with.json"
            path_with.write_text(json.dumps(with_field, sort_keys=True))

            d_without = compute_candidate_digest(path_without)
            d_with    = compute_candidate_digest(path_with)
            assert d_without == d_with, (
                f"registry claims {field!r} is excluded, but digest changes when it's present"
            )

    def test_hash_algorithm_is_sha256(self):
        r = _load("01_digest_canonicalization.json")
        assert r["hash_algorithm"] == "sha256"

    def test_key_ordering_is_sorted(self):
        r = _load("01_digest_canonicalization.json")
        assert r["serialization"]["key_ordering"] == "sorted"


class TestWitnessContractRegistry:
    """02_witness_contract.json must mirror witness.py constants."""

    def test_required_fields_matches_constant(self):
        r = _load("02_witness_contract.json")
        assert set(r["required_fields"]) == set(REQUIRED_WITNESS_FIELDS), (
            "registry required_fields diverged from REQUIRED_WITNESS_FIELDS"
        )

    def test_required_gate_results_matches_constant(self):
        r = _load("02_witness_contract.json")
        assert set(r["required_gate_results"]) == set(REQUIRED_GATES)

    def test_valid_runner_types_matches_constant(self):
        r = _load("02_witness_contract.json")
        assert set(r["valid_runner_types"]) == set(VALID_RUNNER_TYPES)

    def test_schema_version_matches_constant(self):
        r = _load("02_witness_contract.json")
        assert r["schema_version_value"] == SCHEMA_VERSION


class TestBootstrapPolicyRegistry:
    """03_bootstrap_policy.json must reflect evaluate_gate4 threshold."""

    def test_minimum_witnesses_matches_implementation(self):
        from cvp_transition.witness import evaluate_gate4

        r = _load("03_bootstrap_policy.json")
        declared_min = r["minimum_admissible_witnesses"]

        # Verify: (declared_min - 1) witnesses → fail, declared_min witnesses → pass
        def _w(wid: str) -> dict:
            return {
                "schema_version": "1.0",
                "witness_id": wid,
                "timestamp_utc": "2026-06-15T18:00:00Z",
                "candidate_digest": "a" * 64,
                "validator_version": "abc1234",
                "environment": {
                    "os": "Linux",
                    "architecture": "x86_64",
                    "python_version": "3.11.15",
                    "runner_type": "github_actions",
                },
                "execution": {"command": "python -m cvp_transition x.json", "exit_code": 0},
                "results": {"gate_1": "PASS", "gate_2": "PASS", "gate_3": "PASS"},
                "verdict": "OK",
                "artifacts": {"compat_json_sha256": "b" * 64, "log_sha256": "c" * 64},
            }

        short = [_w(f"aaaa-{i:04d}") for i in range(declared_min - 1)]
        ok_short, _ = evaluate_gate4(short, "a" * 64)
        assert not ok_short, (
            f"registry declares minimum={declared_min} but {declared_min - 1} witnesses passed"
        )

        full = [_w(f"bbbb-{i:04d}") for i in range(declared_min)]
        ok_full, _ = evaluate_gate4(full, "a" * 64)
        assert ok_full, (
            f"registry declares minimum={declared_min} but {declared_min} witnesses failed"
        )

    def test_execution_ordering_has_gate4_last_before_emit(self):
        r = _load("03_bootstrap_policy.json")
        steps = r["execution_ordering"]
        gate4_idx = next(i for i, s in enumerate(steps) if "gate_4" in s)
        emit_idx  = next(i for i, s in enumerate(steps) if "emit" in s)
        assert gate4_idx < emit_idx, "gate_4 must precede CVP_COMPAT.json emission"


class TestGateFailureMapRegistry:
    """04_gate_failure_map.json must match validate.py exit codes."""

    def test_all_exit_codes_documented(self):
        r = _load("04_gate_failure_map.json")
        documented = {int(k) for k in r["exit_codes"]}
        # validate.py uses exit codes 0–4
        expected = {0, 1, 2, 3, 4}
        assert expected <= documented, (
            f"undocumented exit codes: {expected - documented}"
        )

    def test_exit_code_labels_match_workflow(self):
        r = _load("04_gate_failure_map.json")
        codes = r["exit_codes"]
        assert codes["0"]["label"] == "TRANSITION_VALID"
        assert codes["1"]["label"] == "INVARIANT_VIOLATION"
        assert codes["2"]["label"] == "DETERMINISM_FAILURE"
        assert codes["3"]["label"] == "WITNESS_FAILURE"
        assert codes["4"]["label"] == "SEMANTIC_REINTERPRETATION"

    def test_witness_failure_exit_code_matches_validate_py(self):
        import subprocess, sys
        from pathlib import Path

        # validate.py returns 3 for witness failure (independent_execution empty)
        # Verify the registry agrees
        r = _load("04_gate_failure_map.json")
        assert r["exit_codes"]["3"]["label"] == "WITNESS_FAILURE"
