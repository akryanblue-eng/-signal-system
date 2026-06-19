"""Extract(v0) acceptance and every rejection branch (schema §7)."""
import dataclasses

from eiac.canon import hash_of
from eiac.extract import (
    REASON_BUNDLE_HASH_MISMATCH,
    REASON_COUPLING_WITNESS_INVALID,
    REASON_ENV_HASH_MISMATCH,
    REASON_GLUE_ADAPTER_SET_MISMATCH,
    REASON_GLUE_PARTITION_INVALID,
    REASON_LOCAL_PROOF_INVALID,
    extract,
)
from eiac.schema import GlueTrace, LocalProof
from eiac.tests.fixtures import bundle_with_ops, env_full, proof_for


def test_accept_on_well_formed_proof():
    env, bundle = env_full(), bundle_with_ops()
    result = extract(env, bundle, proof_for(env, bundle))
    assert result.ok
    assert result.status == "ACCEPT"
    assert result.reason is None


def test_reject_env_hash_mismatch():
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    tampered = dataclasses.replace(proof, env_hash=b"\x00" * 32)
    result = extract(env, bundle, tampered)
    assert result.status == "REJECT"
    assert result.reason == REASON_ENV_HASH_MISMATCH


def test_reject_bundle_hash_mismatch():
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    tampered = dataclasses.replace(proof, bundle_hash=b"\x00" * 32)
    result = extract(env, bundle, tampered)
    assert result.status == "REJECT"
    assert result.reason == REASON_BUNDLE_HASH_MISMATCH


def test_reject_duplicate_local_adapter():
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    doubled = proof.local + (proof.local[0],)
    tampered = dataclasses.replace(proof, local=doubled)
    result = extract(env, bundle, tampered)
    assert result.status == "REJECT"
    assert result.reason == REASON_LOCAL_PROOF_INVALID


def test_reject_local_proof_with_non_bytes_payload():
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    bad_local = (LocalProof(adapter=proof.local[0].adapter, payload_tag="X", payload="not-bytes"),) + proof.local[1:]
    tampered = dataclasses.replace(proof, local=bad_local)
    result = extract(env, bundle, tampered)
    assert result.status == "REJECT"
    assert result.reason == REASON_LOCAL_PROOF_INVALID


def test_reject_glue_adapter_set_mismatch():
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    bad_glue = dataclasses.replace(proof.glue, adapters=proof.glue.adapters + ("ghost/adapter",))
    tampered = dataclasses.replace(proof, glue=bad_glue)
    result = extract(env, bundle, tampered)
    assert result.status == "REJECT"
    assert result.reason == REASON_GLUE_ADAPTER_SET_MISMATCH


def test_reject_glue_partition_missing_op():
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    shrunk_partition = tuple(
        {"adapter": p["adapter"], "op_ids": p["op_ids"][:-1] if p["op_ids"] else p["op_ids"]}
        for p in proof.glue.op_partition
    )
    bad_glue = dataclasses.replace(proof.glue, op_partition=shrunk_partition)
    tampered = dataclasses.replace(proof, glue=bad_glue)
    result = extract(env, bundle, tampered)
    assert result.status == "REJECT"
    assert result.reason == REASON_GLUE_PARTITION_INVALID


def test_reject_glue_partition_duplicate_op():
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    first = proof.glue.op_partition[0]
    duplicated_partition = proof.glue.op_partition + (first,)
    bad_glue = dataclasses.replace(proof.glue, op_partition=duplicated_partition)
    tampered = dataclasses.replace(proof, glue=bad_glue)
    result = extract(env, bundle, tampered)
    assert result.status == "REJECT"
    assert result.reason == REASON_GLUE_PARTITION_INVALID


def test_reject_unknown_coupling_witness_tag():
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)

    class FakeWitness:
        schema_tag = "EIAC/K/NOT_REAL/v1"

        def sort_key(self):
            return (self.schema_tag,)

        def to_canon(self):
            return {"schema_tag": self.schema_tag}

    tampered = dataclasses.replace(proof, coupling=proof.coupling + (FakeWitness(),))
    result = extract(env, bundle, tampered)
    assert result.status == "REJECT"
    assert result.reason == REASON_COUPLING_WITNESS_INVALID


def test_reject_when_env_does_not_match_supplied_env():
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    other_env = dataclasses.replace(env, env_id="env/different")
    result = extract(other_env, bundle, proof)
    assert result.status == "REJECT"
    assert result.reason == REASON_ENV_HASH_MISMATCH
