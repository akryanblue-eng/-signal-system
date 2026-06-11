"""
registry/binding.py — Registry Binding Block (RBB) v0.1

Single entrypoint for RBB population across all artifact writers.

DISCIPLINE RULES:
  1. Timestamp rule: bindings_timestamp_iso is metadata, not identity.
     Never use it in AEC derivation, CSSR grouping, or hash computation.
  2. Single source rule: build_registry_binding() is the ONLY code path
     allowed to populate the RBB field in any artifact
     (CVC / CRE / CSSR / Canary / SIPMG / MAG).

AEC (Artifact Equivalence Class):
  aec_id = f"{registry_hash}:{move_set_hash}:{schema_major}"
  Two artifacts are in the same AEC iff their aec_id matches.
  CSSR aggregation must never span AEC boundaries.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from registry.runtime import RegistrySnapshot
from registry.hash import get_registry_version_hash, _major


@dataclass
class RegistryBinding:
    """
    Immutable identity header stamped on every artifact at write time.

    Fields:
      registry_hash         — sha256 of RegistrySnapshot (event taxonomy + grammar + knobs)
      move_set_hash         — sha256 of the move set (knob names + ranges + grammar list)
      schema_major          — breaking-change schema version integer
      is_stable             — True if registry + move_set are frozen for this run
      bindings_timestamp_iso — ISO 8601 wall-clock stamp (metadata only, not identity)
      vcl_hash              — sha256 prefix of all instrument scripts at write time
    """
    registry_hash: str
    move_set_hash: str
    schema_major: int
    is_stable: bool
    bindings_timestamp_iso: str
    vcl_hash: str

    @property
    def aec_id(self) -> str:
        """Artifact Equivalence Class identifier."""
        return f"{self.registry_hash}:{self.move_set_hash}:{self.schema_major}"


def _compute_move_set_hash(move_set: Dict[str, Any]) -> str:
    raw = json.dumps(move_set, sort_keys=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:24]}"


def build_registry_binding(
    registry_snapshot: RegistrySnapshot,
    move_set: Dict[str, Any],
    vcl_hash: str,
    schema_version: str = "0.1",
    is_stable: bool = True,
) -> RegistryBinding:
    """
    Construct a RegistryBinding from a RegistrySnapshot and move set.

    Args:
        registry_snapshot: Current world registry state (event taxonomy, grammar, knobs).
        move_set:          Knob registry + grammar list defining the search space.
        vcl_hash:          VCL hash from sipmg.compute_vcl_hash() or equivalent.
        schema_version:    Schema version string (e.g. "0.1"). Major extracted via _major().
        is_stable:         Whether registry + move_set are frozen for this production run.
    """
    return RegistryBinding(
        registry_hash=get_registry_version_hash(registry_snapshot),
        move_set_hash=_compute_move_set_hash(move_set),
        schema_major=_major(schema_version),
        is_stable=is_stable,
        bindings_timestamp_iso=datetime.now(timezone.utc).isoformat(),
        vcl_hash=vcl_hash,
    )


def inject_rbb(artifact: Dict[str, Any], binding: RegistryBinding) -> Dict[str, Any]:
    """
    Return a copy of artifact with an 'rbb' field injected.

    Does not mutate the input dict.
    """
    enriched = dict(artifact)
    enriched["rbb"] = asdict(binding)
    return enriched


def dumps_artifact_json(
    artifact: Dict[str, Any],
    binding: RegistryBinding,
    **json_kwargs: Any,
) -> str:
    """Serialize artifact to JSON with RBB injected. Convenience wrapper."""
    return json.dumps(inject_rbb(artifact, binding), **json_kwargs)
