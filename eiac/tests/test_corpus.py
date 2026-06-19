"""EIAC Reference Corpus v0.1 -- named ground-truth cases for Extract(v0).

Each test below corresponds to one named case from the proposed corpus.
Three proposed cases are deliberately NOT implemented here, because they
require semantics Extract(v0) does not have:

- REJECT_COUPLE_01 -- would require validate(witness, env): evaluating
  whether a coupling witness's *claim* actually holds against an Env
  (e.g. a BudgetWitness whose observed value violates the Env's budget
  limit). Extract(v0) only checks that a witness is well-typed and
  canon-decodable (schema §7), never that its claim is true.
- REJECT_INTERSECTION_02 -- would require evaluating adapter-local
  admissibility (A_a) and an intersection-emptiness predicate across
  adapters. Extract(v0) never evaluates A_a; LocalProof payloads are
  opaque bytes by design (schema §4).
- ACCEPT_OVERSPEC_01 ("harmless extra fields are ignored") -- contradicts
  schema §1.4.3 directly: canon(x)/H(x) have no notion of an "ignorable"
  field. Any field difference changes canon(x) and therefore H(x); there
  is no backward-compatible equivalence class to land in.

REJECT_SCHEMA_01 is implemented in the reframed form consistent with
§1.4.3 (fail-closed on a schema_tag that doesn't match its expected
per-object constant), not the originally proposed
"bundle.schema_tag != env.schema_tag" form, which is incoherent since
those tags are intentionally different by construction (domain
separation).
"""
import dataclasses

from eiac.canon import hash_of
from eiac.extract import (
    REASON_BUNDLE_HASH_MISMATCH,
    REASON_ENV_HASH_MISMATCH,
    REASON_GLUE_PARTITION_INVALID,
    REASON_LOCAL_PROOF_INVALID,
    REASON_COUPLING_WITNESS_INVALID,
    REASON_SCHEMA_TAG_MISMATCH,
    extract,
)
from eiac.schema import BudgetWitness, LocalProof
from eiac.tests.fixtures import bundle_minimal, bundle_with_ops, env_full, env_minimal, proof_for


def test_ACCEPT_SIMPLE_01():
    env, bundle = env_minimal(), bundle_minimal()
    result = extract(env, bundle, proof_for(env, bundle))
    assert result.status == "ACCEPT"


def test_ACCEPT_MULTI_02():
    env, bundle = env_full(), bundle_with_ops()
    result = extract(env, bundle, proof_for(env, bundle))
    assert result.status == "ACCEPT"


def test_ACCEPT_BOUNDARY_01():
    # No env constraints at all (caps/budgets/zones all empty), but a
    # multi-adapter bundle with ops still verifies structurally.
    env, bundle = env_minimal(), bundle_with_ops()
    result = extract(env, bundle, proof_for(env, bundle))
    assert result.status == "ACCEPT"


def test_ACCEPT_REDUNDANCY_03():
    # An extra, well-typed coupling witness that adds no new structural
    # information is still ACCEPT -- Extract(v0) never evaluates whether
    # witnesses are *necessary* or *non-redundant*, only well-typed.
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    redundant = BudgetWitness(
        budget="tokens", observed=5, op_ids=tuple(op.op_id for op in bundle.ops)
    )
    tampered = dataclasses.replace(proof, coupling=proof.coupling + (redundant,))
    result = extract(env, bundle, tampered)
    assert result.status == "ACCEPT"


def test_REJECT_HASH_01():
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    tampered = dataclasses.replace(proof, env_hash=b"\x00" * 32)
    result = extract(env, bundle, tampered)
    assert result.status == "REJECT"
    assert result.reason == REASON_ENV_HASH_MISMATCH


def test_REJECT_LOCAL_01():
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    bad_local = (
        LocalProof(adapter=proof.local[0].adapter, payload_tag="X", payload="not-bytes"),
    ) + proof.local[1:]
    tampered = dataclasses.replace(proof, local=bad_local)
    result = extract(env, bundle, tampered)
    assert result.status == "REJECT"
    assert result.reason == REASON_LOCAL_PROOF_INVALID


def test_REJECT_GLUE_01():
    # op_partition's claimed adapter does not match the op's real
    # adapter in the bundle -- the adapter labels are swapped between
    # the two partition entries while adapter set and op_id set both
    # still check out, so only the new ownership-consistency check
    # catches it.
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    reversed_adapters = list(reversed([part["adapter"] for part in proof.glue.op_partition]))
    relabeled = tuple(
        {"adapter": swapped_adapter, "op_ids": part["op_ids"]}
        for part, swapped_adapter in zip(proof.glue.op_partition, reversed_adapters)
    )
    bad_glue = dataclasses.replace(proof.glue, op_partition=relabeled)
    tampered = dataclasses.replace(proof, glue=bad_glue)
    result = extract(env, bundle, tampered)
    assert result.status == "REJECT"
    assert result.reason == REASON_GLUE_PARTITION_INVALID


def test_REJECT_KTYPE_01():
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


def test_REJECT_SCHEMA_01():
    env, bundle = env_full(), bundle_with_ops()
    proof = proof_for(env, bundle)
    tampered_env = dataclasses.replace(env, schema_tag="EIAC/ENV/v2")
    result = extract(tampered_env, bundle, proof)
    assert result.status == "REJECT"
    assert result.reason == REASON_SCHEMA_TAG_MISMATCH
