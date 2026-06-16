"""
Universe C: Artifact space — provenance-carrying outputs.

Every artifact is a Σ-type: (records, WitnessProvenance).
Artifacts carry comonadic structure over the witness base.

Comonadic operations:
    extract  : Artifact → WitnessView       (yield witness context)
    duplicate: Artifact → (Artifact, Artifact) (partition, preserve provenance)
    map_payload: (bytes → bytes) → Artifact → Artifact (lift pure fn over payload)

INVARIANT: Provenance hash covers witness tokens only, not payload content.
           map_payload preserves provenance_hash — provenance is structural context,
           not a function of what transformation was applied to the payload.

INVARIANT: WitnessRef tokens are opaque — only Universe A (pcp_kernel) mints them.
           Import WitnessRef from pcp_witness_ref for type annotations; never
           construct one directly.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

from .pcp_witness_ref import WitnessRef


@dataclass(frozen=True)
class ArtifactRecord:
    """Single witnessed payload: an opaque kernel token + the derived bytes."""
    address: WitnessRef
    payload: bytes


@dataclass(frozen=True)
class WitnessView:
    """
    Extracted witness context from an artifact.
    Returned by Artifact.extract() — the comonadic counit.
    """
    witness_refs: tuple[WitnessRef, ...]
    provenance_hash: bytes


@dataclass(frozen=True)
class Artifact:
    """
    Σ-type: (records, provenance).

    Comonadic coalgebra over the trace base:
    - extract  → WitnessView (counit ε)
    - duplicate → (Artifact, Artifact) (split preserving provenance context)
    - map_payload → Artifact (functor map over payloads, witness refs invariant)

    provenance_hash is computed over witness tokens only.
    It is structural context — it survives payload transformations.
    """
    records: tuple[ArtifactRecord, ...]
    provenance_range: tuple[WitnessRef, WitnessRef]
    provenance_hash: bytes
    source_term_hash: str

    def extract(self) -> WitnessView:
        """Counit ε: yield the witness context of this artifact."""
        return WitnessView(
            witness_refs=tuple(r.address for r in self.records),
            provenance_hash=self.provenance_hash,
        )

    def duplicate(self) -> tuple[Artifact, Artifact]:
        """
        Partition records into two halves, both sharing the original provenance.
        Not a categorical duplicate (W A → W(W A)), but a practical split
        that preserves provenance context across both halves.
        """
        mid = max(1, len(self.records) // 2)
        left = Artifact(
            records=self.records[:mid],
            provenance_range=self.provenance_range,
            provenance_hash=self.provenance_hash,
            source_term_hash=self.source_term_hash,
        )
        right = Artifact(
            records=self.records[mid:] if len(self.records) > mid else self.records[mid:],
            provenance_range=self.provenance_range,
            provenance_hash=self.provenance_hash,
            source_term_hash=self.source_term_hash,
        )
        return (left, right)

    def map_payload(self, f: Callable[[bytes], bytes]) -> Artifact:
        """
        Lift a pure function over artifact payloads.
        Witness refs are untouched — provenance is preserved by construction.
        f must be pure (no IO, no time, no side effects); this is a caller contract,
        not enforced at the Python level (enforcement lives at the certification boundary).
        """
        return Artifact(
            records=tuple(
                ArtifactRecord(address=r.address, payload=f(r.payload))
                for r in self.records
            ),
            provenance_range=self.provenance_range,
            provenance_hash=self.provenance_hash,
            source_term_hash=self.source_term_hash,
        )
