"""Extract(v0) -- the structural proof verifier (docs/eiac-schema-v1.0.md §7).

Extract(env, p, proof) -> ACCEPT | REJECT(reason)

This performs only the minimum checks listed in schema §7: hash binding,
glue partition correctness, local-proof well-formedness/tagging, and
coupling-witness well-typedness. It does not:

- evaluate adapter-local admissibility semantics (A_a) -- LocalProof
  payloads are opaque bytes by design (schema §4);
- evaluate K-witness *validity* against an Env (budgets/locks/zones/edges
  actually holding) -- only that each witness is well-typed and
  canon-decodable;
- run vPNF normalization -- undefined for v1.0;
- search for, rank, or invent any proof material.

It only checks consistency of an already-fully-formed Proof object against
an Env and an ExecutionBundle that the caller supplies in full (schema
§1.4.5: no hash-only references, no partial reconstruction).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from eiac.canon import hash_of
from eiac.schema import Env, ExecutionBundle, KNOWN_WITNESS_TAGS, Proof

REASON_ENV_HASH_MISMATCH = "ENV_HASH_MISMATCH"
REASON_BUNDLE_HASH_MISMATCH = "BUNDLE_HASH_MISMATCH"
REASON_GLUE_ADAPTER_SET_MISMATCH = "GLUE_ADAPTER_SET_MISMATCH"
REASON_GLUE_PARTITION_INVALID = "GLUE_PARTITION_INVALID"
REASON_LOCAL_PROOF_INVALID = "LOCAL_PROOF_INVALID"
REASON_COUPLING_WITNESS_INVALID = "COUPLING_WITNESS_INVALID"


@dataclass(frozen=True)
class ExtractResult:
    status: str  # "ACCEPT" | "REJECT"
    reason: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status == "ACCEPT"


def _accept() -> ExtractResult:
    return ExtractResult(status="ACCEPT")


def _reject(reason: str) -> ExtractResult:
    return ExtractResult(status="REJECT", reason=reason)


def extract(env: Env, p: ExecutionBundle, proof: Proof) -> ExtractResult:
    if proof.env_hash != hash_of(env):
        return _reject(REASON_ENV_HASH_MISMATCH)

    if proof.bundle_hash != hash_of(p):
        return _reject(REASON_BUNDLE_HASH_MISMATCH)

    local_adapters = [lp.adapter for lp in proof.local]
    if len(set(local_adapters)) != len(local_adapters):
        return _reject(REASON_LOCAL_PROOF_INVALID)
    for lp in proof.local:
        if lp.schema_tag != "EIAC/LOCAL_PROOF/v1" or not isinstance(lp.payload, bytes):
            return _reject(REASON_LOCAL_PROOF_INVALID)

    if set(proof.glue.adapters) != set(local_adapters):
        return _reject(REASON_GLUE_ADAPTER_SET_MISMATCH)

    bundle_op_ids = {op.op_id for op in p.ops}
    partition_op_ids: list[str] = []
    for part in proof.glue.op_partition:
        partition_op_ids.extend(part["op_ids"])
    if len(set(partition_op_ids)) != len(partition_op_ids):
        return _reject(REASON_GLUE_PARTITION_INVALID)
    if set(partition_op_ids) != bundle_op_ids:
        return _reject(REASON_GLUE_PARTITION_INVALID)

    for witness in proof.coupling:
        if witness.schema_tag not in KNOWN_WITNESS_TAGS:
            return _reject(REASON_COUPLING_WITNESS_INVALID)
        try:
            witness.to_canon()
        except (TypeError, ValueError):
            return _reject(REASON_COUPLING_WITNESS_INVALID)

    return _accept()
