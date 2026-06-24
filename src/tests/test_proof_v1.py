"""
Tests for Proof v1 — the frozen proof schema (NIC's ABI).
"""
import pytest

from src.nic_v1 import HASH_ALG
from src.proof_v1 import (
    SPEC_VERSION,
    ProofError,
    compute_proof_id,
    make_proof,
    proof_to_dict,
    verify_proof_schema,
)


def _valid_kwargs(**overrides):
    base = dict(
        snapshot_mode="git_tree",
        snapshot_id="a" * 40,
        extractor_version="b" * 64,
        result="PASS",
        proof_payload={"set_hash": "c" * 64},
    )
    base.update(overrides)
    return base


class TestMakeProof:
    def test_embeds_hash_alg_id_from_registry(self):
        proof = make_proof(**_valid_kwargs())
        assert proof.hash_alg_id == HASH_ALG

    def test_embeds_spec_version(self):
        proof = make_proof(**_valid_kwargs())
        assert proof.spec_version == SPEC_VERSION

    def test_rejects_unknown_snapshot_mode(self):
        with pytest.raises(ProofError, match="snapshot_mode"):
            make_proof(**_valid_kwargs(snapshot_mode="manifest_v2"))

    def test_rejects_unknown_result(self):
        with pytest.raises(ProofError, match="result"):
            make_proof(**_valid_kwargs(result="MAYBE"))

    def test_rejects_non_dict_payload(self):
        with pytest.raises(ProofError, match="proof_payload"):
            make_proof(**_valid_kwargs(proof_payload="not-a-dict"))

    def test_manifest_snapshot_mode_accepted(self):
        proof = make_proof(**_valid_kwargs(snapshot_mode="manifest"))
        assert proof.snapshot_mode == "manifest"

    def test_fail_result_accepted(self):
        proof = make_proof(**_valid_kwargs(result="FAIL"))
        assert proof.result == "FAIL"


class TestVerifyProofSchema:
    def test_valid_proof_passes(self):
        proof = make_proof(**_valid_kwargs())
        assert verify_proof_schema(proof_to_dict(proof)) is True

    def test_missing_required_field_fails(self):
        obj = proof_to_dict(make_proof(**_valid_kwargs()))
        del obj["extractor_version"]
        assert verify_proof_schema(obj) is False

    def test_unknown_extra_field_fails(self):
        obj = proof_to_dict(make_proof(**_valid_kwargs()))
        obj["extra_field"] = "surprise"
        assert verify_proof_schema(obj) is False

    def test_wrong_spec_version_fails(self):
        obj = proof_to_dict(make_proof(**_valid_kwargs()))
        obj["spec_version"] = "nic.proof.v2"
        assert verify_proof_schema(obj) is False

    def test_wrong_hash_alg_id_fails(self):
        obj = proof_to_dict(make_proof(**_valid_kwargs()))
        obj["hash_alg_id"] = "sha1"
        assert verify_proof_schema(obj) is False

    def test_invalid_result_value_fails(self):
        obj = proof_to_dict(make_proof(**_valid_kwargs()))
        obj["result"] = "MAYBE"
        assert verify_proof_schema(obj) is False

    def test_non_string_snapshot_id_fails(self):
        obj = proof_to_dict(make_proof(**_valid_kwargs()))
        obj["snapshot_id"] = 12345
        assert verify_proof_schema(obj) is False

    def test_non_dict_input_fails(self):
        assert verify_proof_schema("not a dict") is False

    def test_no_external_configuration_needed(self):
        """proof + verifier alone must be sufficient — no extra args to verify_proof_schema."""
        proof = make_proof(**_valid_kwargs())
        obj = proof_to_dict(proof)
        assert verify_proof_schema(obj) is True


class TestComputeProofId:
    def test_deterministic(self):
        proof = make_proof(**_valid_kwargs())
        assert compute_proof_id(proof) == compute_proof_id(proof)

    def test_changes_with_payload(self):
        p1 = make_proof(**_valid_kwargs(proof_payload={"set_hash": "c" * 64}))
        p2 = make_proof(**_valid_kwargs(proof_payload={"set_hash": "d" * 64}))
        assert compute_proof_id(p1) != compute_proof_id(p2)

    def test_is_64_char_hex(self):
        proof = make_proof(**_valid_kwargs())
        proof_id = compute_proof_id(proof)
        assert len(proof_id) == 64
        int(proof_id, 16)
