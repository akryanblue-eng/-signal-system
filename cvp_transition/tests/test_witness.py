"""
Witness validator test suite — exercises every classification branch.

Uses synthetic records with a real candidate_digest (sha256 of the committed
transition_morphism.json). These records are test fixtures only: they prove
the validator logic is correct, not that external corroboration has occurred.
No synthetic record should ever appear in transition_morphism.independent_execution.
"""
import json
import pytest
from pathlib import Path
from cvp_transition.witness import (
    validate_witness,
    is_admissible,
    are_independent,
    evaluate_gate4,
    compute_candidate_digest,
    REQUIRED_WITNESS_FIELDS,
)

# Real digest of the committed transition_morphism.json.
# Recompute if the morphism file changes: sha256(transition_morphism.json bytes).
REAL_DIGEST = "e5786e884f6fec9e86f6f8f2691562901185c0252463f74715c54d82c89d1997"
WRONG_DIGEST = "a" * 64


def _make_witness(
    *,
    witness_id: str = "11111111-0000-4000-8000-000000000001",
    candidate_digest: str = REAL_DIGEST,
    runner_type: str = "github_actions",
    os: str = "Linux 6.18.5 / Ubuntu 22.04",
    architecture: str = "x86_64",
    python_version: str = "3.11.15",
    verdict: str = "OK",
    gate_1: str = "PASS",
    gate_2: str = "PASS",
    gate_3: str = "PASS",
    exit_code: int = 0,
) -> dict:
    return {
        "schema_version": "1.0",
        "witness_id": witness_id,
        "timestamp_utc": "2026-06-12T00:00:00Z",
        "candidate_digest": candidate_digest,
        "validator_version": "73da03d",
        "environment": {
            "os": os,
            "architecture": architecture,
            "python_version": python_version,
            "runner_type": runner_type,
        },
        "execution": {
            "command": "python -m cvp_transition transition_morphism.json",
            "exit_code": exit_code,
        },
        "results": {
            "gate_1": gate_1,
            "gate_2": gate_2,
            "gate_3": gate_3,
            "gate_3b_byte_exact": "PASS",
            "gate_4": "PENDING",
        },
        "verdict": verdict,
        "artifacts": {
            "compat_json_sha256": "b" * 64,
            "log_sha256": "c" * 64,
        },
    }


# ── validate_witness ───────────────────────────────────────────────────────

class TestValidateWitness:
    def test_clean_record_is_valid(self):
        assert validate_witness(_make_witness()) == []

    def test_wrong_schema_version(self):
        w = _make_witness()
        w["schema_version"] = "0.9"
        errs = validate_witness(w)
        assert any("schema_version" in e for e in errs)

    def test_missing_candidate_digest(self):
        w = _make_witness()
        del w["candidate_digest"]
        errs = validate_witness(w)
        assert any("candidate_digest" in e for e in errs)

    def test_old_field_name_rejected(self):
        # Verifies rename from transition_manifest_sha256 → candidate_digest.
        w = _make_witness()
        del w["candidate_digest"]
        w["transition_manifest_sha256"] = REAL_DIGEST
        errs = validate_witness(w)
        assert any("candidate_digest" in e for e in errs)

    def test_malformed_timestamp(self):
        w = _make_witness()
        w["timestamp_utc"] = "2026-06-12 00:00:00"
        errs = validate_witness(w)
        assert any("timestamp_utc" in e for e in errs)

    def test_invalid_verdict(self):
        w = _make_witness()
        w["verdict"] = "MAYBE"
        errs = validate_witness(w)
        assert any("verdict" in e for e in errs)

    def test_invalid_runner_type(self):
        w = _make_witness()
        w["environment"]["runner_type"] = "docker"
        errs = validate_witness(w)
        assert any("runner_type" in e for e in errs)

    def test_exit_code_must_be_int(self):
        w = _make_witness()
        w["execution"]["exit_code"] = "0"
        errs = validate_witness(w)
        assert any("exit_code" in e for e in errs)

    def test_missing_artifact_hash(self):
        w = _make_witness()
        del w["artifacts"]["log_sha256"]
        errs = validate_witness(w)
        assert any("log_sha256" in e for e in errs)


# ── is_admissible ──────────────────────────────────────────────────────────

class TestIsAdmissible:
    def test_clean_record_admitted(self):
        ok, _ = is_admissible(_make_witness(), REAL_DIGEST)
        assert ok

    def test_digest_mismatch_rejected(self):
        ok, msg = is_admissible(_make_witness(), WRONG_DIGEST)
        assert not ok
        assert "candidate_digest mismatch" in msg

    def test_nonzero_exit_code_rejected(self):
        ok, msg = is_admissible(_make_witness(exit_code=1), REAL_DIGEST)
        assert not ok
        assert "exit_code" in msg

    def test_failed_gate_rejected(self):
        ok, msg = is_admissible(_make_witness(gate_1="FAIL"), REAL_DIGEST)
        assert not ok
        assert "gate_1" in msg

    def test_verdict_fail_rejected(self):
        ok, msg = is_admissible(_make_witness(verdict="FAIL"), REAL_DIGEST)
        assert not ok
        assert "verdict" in msg

    def test_empty_validator_version_rejected(self):
        w = _make_witness()
        w["validator_version"] = ""
        ok, msg = is_admissible(w, REAL_DIGEST)
        assert not ok
        assert "validator_version" in msg


# ── are_independent ────────────────────────────────────────────────────────

class TestAreIndependent:
    def _w(self, witness_id: str, runner_type: str = "github_actions", **env):
        return _make_witness(witness_id=witness_id, runner_type=runner_type, **env)

    def test_replay_rejected(self):
        # Rule 1: same witness_id always rejected.
        w = self._w("aaaa-0001")
        ok, msg = are_independent(w, w)
        assert not ok
        assert "replay" in msg

    def test_same_fingerprint_both_local_rejected(self):
        # Rule 2: same os/arch/python + runner_type=local on both = same machine.
        w1 = self._w("aaaa-0001", runner_type="local")
        w2 = self._w("aaaa-0002", runner_type="local")
        ok, msg = are_independent(w1, w2)
        assert not ok
        assert "same-machine" in msg

    def test_same_fingerprint_github_actions_accepted(self):
        # Rule 3: github_actions VMs are guaranteed distinct by GitHub.
        w1 = self._w("aaaa-0001", runner_type="github_actions")
        w2 = self._w("aaaa-0002", runner_type="github_actions")
        ok, msg = are_independent(w1, w2)
        assert ok
        assert "github_actions" in msg

    def test_same_fingerprint_mixed_runner_types_accepted(self):
        # Same fingerprint but different runner_types (local vs github_actions).
        w1 = self._w("aaaa-0001", runner_type="local")
        w2 = self._w("aaaa-0002", runner_type="github_actions")
        ok, _ = are_independent(w1, w2)
        assert ok

    def test_different_fingerprints_accepted(self):
        # Rule 4: distinct os/arch/python = distinguishable machine classes.
        w1 = self._w("aaaa-0001", runner_type="local",
                     os="Linux 6.18.5 / Ubuntu 22.04", architecture="x86_64",
                     python_version="3.11.15")
        w2 = self._w("aaaa-0002", runner_type="local",
                     os="macOS 14.5", architecture="arm64",
                     python_version="3.12.3")
        ok, msg = are_independent(w1, w2)
        assert ok
        assert "fingerprints" in msg


# ── evaluate_gate4 ─────────────────────────────────────────────────────────

class TestEvaluateGate4:
    def test_no_witnesses_fails(self):
        ok, msg = evaluate_gate4([], REAL_DIGEST)
        assert not ok
        assert "no witnesses" in msg

    def test_single_admissible_witness_fails(self):
        ok, msg = evaluate_gate4([_make_witness()], REAL_DIGEST)
        assert not ok
        assert "need ≥2" in msg
        assert "got 1" in msg

    def test_schema_invalid_witness_excluded(self):
        w = _make_witness()
        del w["candidate_digest"]
        ok, msg = evaluate_gate4([w], REAL_DIGEST)
        assert not ok
        assert "schema invalid" in msg

    def test_digest_mismatch_excluded_from_admitted(self):
        w = _make_witness(candidate_digest=WRONG_DIGEST)
        ok, msg = evaluate_gate4([w], REAL_DIGEST)
        assert not ok
        assert "inadmissible" in msg

    def test_two_identical_records_rejected_as_replay(self):
        # Two schema-valid + admissible but same witness_id → not independent.
        w = _make_witness(witness_id="aaaa-0001", runner_type="github_actions")
        ok, msg = evaluate_gate4([w, w], REAL_DIGEST)
        assert not ok
        assert "independent" in msg or "replay" in msg

    def test_two_local_same_machine_rejected(self):
        w1 = _make_witness(witness_id="aaaa-0001", runner_type="local")
        w2 = _make_witness(witness_id="aaaa-0002", runner_type="local")
        ok, msg = evaluate_gate4([w1, w2], REAL_DIGEST)
        assert not ok
        assert "independent" in msg or "same-machine" in msg

    def test_two_github_actions_same_image_passes(self):
        # Formal predicate satisfied: same fingerprint, both github_actions.
        w1 = _make_witness(witness_id="aaaa-0001", runner_type="github_actions")
        w2 = _make_witness(witness_id="aaaa-0002", runner_type="github_actions")
        ok, msg = evaluate_gate4([w1, w2], REAL_DIGEST)
        assert ok
        assert "PASS" in msg

    def test_two_different_machine_classes_passes(self):
        # Formal predicate satisfied: distinct fingerprints.
        w1 = _make_witness(
            witness_id="aaaa-0001", runner_type="local",
            os="Linux 6.18.5 / Ubuntu 22.04", architecture="x86_64",
            python_version="3.11.15",
        )
        w2 = _make_witness(
            witness_id="aaaa-0002", runner_type="local",
            os="macOS 14.5", architecture="arm64",
            python_version="3.12.3",
        )
        ok, msg = evaluate_gate4([w1, w2], REAL_DIGEST)
        assert ok
        assert "PASS" in msg

    def test_one_bad_one_good_insufficient(self):
        # Only one admissible witness after filtering — gate fails.
        bad = _make_witness(witness_id="aaaa-0001", exit_code=1)
        good = _make_witness(witness_id="aaaa-0002", runner_type="github_actions")
        ok, msg = evaluate_gate4([bad, good], REAL_DIGEST)
        assert not ok
        assert "need ≥2" in msg

    def test_verdict_ok_required_for_admission(self):
        w1 = _make_witness(witness_id="aaaa-0001", verdict="FAIL")
        w2 = _make_witness(witness_id="aaaa-0002", runner_type="github_actions")
        ok, _ = evaluate_gate4([w1, w2], REAL_DIGEST)
        assert not ok


# ── Invariant: digest is witness-independent ───────────────────────────────

MORPHISM_ROOT = Path(__file__).parent.parent.parent


class TestDigestWitnessIndependence:
    """
    Adding or removing witnesses must not change compute_candidate_digest().
    Witnesses attest to identity; they must not constitute it.
    """

    def _write(self, tmp_path: Path, witnesses: list) -> Path:
        morphism = {
            "from_version": "1.2",
            "to_version": "1.3",
            "transition_type": "EXTENSION",
            "artifact_mapping": {
                "cvl1_extraction": "unchanged",
                "drift_engine": "unchanged",
                "verify_kernel": "unchanged",
                "artifact_schema": "unchanged",
            },
            "invariants_preserved": [],
            "invariants_added": [],
            "breaking_changes": [],
            "independent_execution": witnesses,
        }
        p = tmp_path / "morphism.json"
        p.write_text(json.dumps(morphism, sort_keys=True))
        return p

    def test_empty_witnesses_same_digest_as_one_witness(self, tmp_path):
        d_empty = compute_candidate_digest(self._write(tmp_path, []))
        d_one   = compute_candidate_digest(self._write(tmp_path, [_make_witness()]))
        assert d_empty == d_one

    def test_digest_stable_as_witness_array_grows(self, tmp_path):
        d_base = compute_candidate_digest(self._write(tmp_path, []))
        for n in range(1, 4):
            ws = [_make_witness(witness_id=f"aaaa-{n:04d}") for _ in range(n)]
            d = compute_candidate_digest(self._write(tmp_path, ws))
            assert d == d_base, f"digest changed with {n} witness(es)"

    def test_witness_candidate_digest_matches_spec_only_hash(self):
        path = MORPHISM_ROOT / "transition_morphism.json"
        morphism = json.loads(path.read_bytes())
        spec_digest = compute_candidate_digest(path)
        for i, w in enumerate(morphism.get("independent_execution", [])):
            assert w["candidate_digest"] == spec_digest, (
                f"witness[{i}].candidate_digest does not match spec-only hash"
            )


# ── Invariant: schema.py and witness.py use the same field set ─────────────

class TestSchemaFieldConsistency:
    """
    schema.py must iterate over REQUIRED_WITNESS_FIELDS from witness.py.
    A schema-valid witness record (per witness.py) must always pass the
    morphism-level schema check (per schema.py) with no witness-related errors.
    """

    def test_shared_constant_drives_schema_py(self):
        from cvp_transition.schema import validate_schema
        w = _make_witness()
        assert validate_witness(w) == [], "fixture must be witness.py-valid"

        morphism = {
            "from_version": "1.2",
            "to_version": "1.3",
            "transition_type": "EXTENSION",
            "artifact_mapping": {
                "cvl1_extraction": "unchanged",
                "drift_engine": "unchanged",
                "verify_kernel": "unchanged",
                "artifact_schema": "unchanged",
            },
            "invariants_preserved": [],
            "invariants_added": [],
            "breaking_changes": [],
            "independent_execution": [w],
        }
        errs = validate_schema(morphism)
        witness_errs = [e for e in errs if "independent_execution" in e]
        assert witness_errs == [], (
            f"witness.py-valid record failed schema.py: {witness_errs}"
        )

    def test_required_witness_fields_constant_is_complete(self):
        required = set(REQUIRED_WITNESS_FIELDS)
        assert "schema_version" in required
        assert "witness_id" in required
        assert "candidate_digest" in required
        assert "validator_version" in required
        assert "environment" in required
        assert "execution" in required
        assert "results" in required
        assert "verdict" in required
        assert "artifacts" in required

    def test_removing_any_required_field_fails_both_validators(self):
        from cvp_transition.schema import validate_schema

        base_morphism = {
            "from_version": "1.2",
            "to_version": "1.3",
            "transition_type": "EXTENSION",
            "artifact_mapping": {
                "cvl1_extraction": "unchanged",
                "drift_engine": "unchanged",
                "verify_kernel": "unchanged",
                "artifact_schema": "unchanged",
            },
            "invariants_preserved": [],
            "invariants_added": [],
            "breaking_changes": [],
        }
        for field in REQUIRED_WITNESS_FIELDS:
            w = _make_witness()
            del w[field]

            witness_errs = validate_witness(w)
            assert any(field in e for e in witness_errs), (
                f"witness.py did not catch missing {field!r}"
            )

            morphism = {**base_morphism, "independent_execution": [w]}
            schema_errs = validate_schema(morphism)
            assert any(field in e for e in schema_errs), (
                f"schema.py did not catch missing {field!r}"
            )


# ── Invariant: bootstrap witnesses in transition_morphism.json are live ────

class TestBootstrapWitnessesAdmissible:
    """
    The actual witnesses in transition_morphism.json must satisfy Gate 4
    using the spec-only digest. This test fails if witnesses go stale or
    the morphism spec drifts without updating them.
    """

    def test_bootstrap_witnesses_pass_gate4(self):
        path = MORPHISM_ROOT / "transition_morphism.json"
        morphism = json.loads(path.read_bytes())
        digest = compute_candidate_digest(path)
        witnesses = morphism.get("independent_execution", [])
        ok, msg = evaluate_gate4(witnesses, digest)
        assert ok, f"bootstrap witnesses failed Gate 4: {msg}"

    def test_at_least_two_witnesses_present(self):
        path = MORPHISM_ROOT / "transition_morphism.json"
        morphism = json.loads(path.read_bytes())
        witnesses = morphism.get("independent_execution", [])
        assert len(witnesses) >= 2, (
            f"expected ≥2 bootstrap witnesses, found {len(witnesses)}"
        )

    def test_all_witnesses_schema_valid(self):
        path = MORPHISM_ROOT / "transition_morphism.json"
        morphism = json.loads(path.read_bytes())
        for i, w in enumerate(morphism.get("independent_execution", [])):
            errs = validate_witness(w)
            assert errs == [], f"witness[{i}] schema errors: {errs}"
