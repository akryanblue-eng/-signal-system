"""
Proof v1 — Frozen Proof Schema

The proof artifact is NIC's ABI: the thing one implementation emits and any
other implementation's verifier consumes. `proof + verifier` must be
sufficient for validation — never `proof + verifier + external
configuration`. hash_alg_id is therefore embedded in the proof itself
rather than negotiated out-of-band.

Fields are either required forever or explicitly versioned by bumping
spec_version; there are no optional fields. The verifier is fail-closed in
both directions:

  unknown field          => FAIL
  missing required field => FAIL
  hash_alg_id mismatch   => FAIL
  unrecognized value in any closed-vocabulary field => FAIL
"""
import hashlib
import json
from dataclasses import dataclass

from src.nic_v1 import DIGEST_LEN_BYTES, HASH_ALG

SPEC_VERSION = "nic.proof.v1"

_SNAPSHOT_MODES = frozenset({"git_tree", "manifest"})
_RESULTS = frozenset({"PASS", "FAIL"})

_REQUIRED_FIELDS = frozenset({
    "spec_version", "hash_alg_id", "snapshot_mode", "snapshot_id",
    "extractor_version", "result", "proof_payload",
})


class ProofError(Exception):
    pass


@dataclass(frozen=True)
class ProofV1:
    spec_version: str
    hash_alg_id: str
    snapshot_mode: str
    snapshot_id: str
    extractor_version: str
    result: str
    proof_payload: dict


def make_proof(
    *,
    snapshot_mode: str,
    snapshot_id: str,
    extractor_version: str,
    result: str,
    proof_payload: dict,
) -> ProofV1:
    if snapshot_mode not in _SNAPSHOT_MODES:
        raise ProofError(
            f"Unknown snapshot_mode {snapshot_mode!r} — must be one of {sorted(_SNAPSHOT_MODES)}"
        )
    if result not in _RESULTS:
        raise ProofError(f"Unknown result {result!r} — must be one of {sorted(_RESULTS)}")
    if not isinstance(proof_payload, dict):
        raise ProofError(
            f"proof_payload must be an object, got {type(proof_payload).__name__!r}"
        )
    return ProofV1(
        spec_version=SPEC_VERSION,
        hash_alg_id=HASH_ALG,
        snapshot_mode=snapshot_mode,
        snapshot_id=snapshot_id,
        extractor_version=extractor_version,
        result=result,
        proof_payload=proof_payload,
    )


def verify_proof_schema(obj: dict) -> bool:
    """
    Fail-closed structural + vocabulary check. Returns True iff `obj` is a
    well-formed nic.proof.v1 object: exactly the required fields, no
    extras, and every closed-vocabulary field holds a recognized value.
    """
    if not isinstance(obj, dict):
        return False

    keys = set(obj.keys())
    if keys != _REQUIRED_FIELDS:
        return False

    if obj["spec_version"] != SPEC_VERSION:
        return False
    if obj["hash_alg_id"] != HASH_ALG:
        return False
    if obj["snapshot_mode"] not in _SNAPSHOT_MODES:
        return False
    if obj["result"] not in _RESULTS:
        return False
    if not isinstance(obj["snapshot_id"], str) or not obj["snapshot_id"]:
        return False
    if not isinstance(obj["extractor_version"], str) or not obj["extractor_version"]:
        return False
    if not isinstance(obj["proof_payload"], dict):
        return False
    return True


def proof_to_dict(proof: ProofV1) -> dict:
    return {
        "spec_version": proof.spec_version,
        "hash_alg_id": proof.hash_alg_id,
        "snapshot_mode": proof.snapshot_mode,
        "snapshot_id": proof.snapshot_id,
        "extractor_version": proof.extractor_version,
        "result": proof.result,
        "proof_payload": proof.proof_payload,
    }


def compute_proof_id(proof: ProofV1) -> str:
    """Content-addressed id over the canonical proof bytes — same hash domain rule as NIC."""
    canonical = json.dumps(
        proof_to_dict(proof), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    digest = hashlib.sha256(canonical)
    assert digest.digest_size == DIGEST_LEN_BYTES
    return digest.hexdigest()


def schema_descriptor() -> dict:
    """
    Canonical description of the frozen schema surface — the field set and
    every closed vocabulary. Used to derive proof_schema_hash so a manifest
    can attest "validated against schema X" without embedding source code.
    """
    return {
        "spec_version": SPEC_VERSION,
        "hash_alg_id": HASH_ALG,
        "required_fields": sorted(_REQUIRED_FIELDS),
        "snapshot_modes": sorted(_SNAPSHOT_MODES),
        "results": sorted(_RESULTS),
    }


def compute_proof_schema_hash() -> str:
    canonical = json.dumps(
        schema_descriptor(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
