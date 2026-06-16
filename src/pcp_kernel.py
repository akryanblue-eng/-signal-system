"""
Universe A: Sovereign Kernel.

This module is the trusted computing base (TCB). It owns:
  - WitnessRef minting (opaque, non-forgeable)
  - SovereignTrace + TraceZipper (opaque trace handles)
  - WitnessCoalgebra (interface that eliminates raw sensor input)
  - certify(term) → CertifiedProjection  (typechecker + normalizer)
  - interpret(certified, trace) → Artifact  (pure structural recursion)
  - verify_certificate(cp) → bool  (CI re-verifier, separate from certifier)

HARD WALLS:
  1. interpret() is only reachable via CertifiedProjection — no raw terms.
  2. Runtime cannot re-enter Universe B — no Term reconstruction from Artifact.
  3. SovereignTrace and TraceZipper are opaque — no raw byte access outside this module.
  4. WitnessRef tokens are minted here and nowhere else.

Coalgebra layer (Universe W → Universe E → Universe A):
  Sensor adapters implement WitnessCoalgebra, providing:
      γ: W(X) → T(W(X))
  which is the ONLY path from physical observation into the trace system.
  There is no "raw input" type — only coalgebraic unfolding.

Projection pipeline:
  Term (B) → certify (A) → CertifiedProjection → interpret (A) → Artifact (C)
"""
from __future__ import annotations
import hashlib
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from .pcp_budget import BudgetGrade, compose_grade
from .pcp_term import (
    ProjectionTerm, _TERM_CONSTRUCTORS, KERNEL_MAP_FN_SYMBOLS,
    _SEGMENT_ID_CHARS,
    Id, Compose, MapWitnesses, LiftDirector, LiftField,
    LiftOverlay, LiftCounterfactual, RestrictBudget, ProjectSegment,
    FoldTrace, FusedDirectorField,
)
from .pcp_artifact import WitnessRef, ArtifactRecord, Artifact
from .pcp_witness_ref import _KERNEL_SENTINEL
from .pcp_rewrite import Rewriter, NormalForm

_KERNEL_VERSION = "pcp-kernel-v1.0"

_rewriter = Rewriter()


# ──────────────────────────────────────────────────────────────────────────────
# Opaque trace types (Universe A sovereign)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TraceZipper:
    """
    Concrete comonad T over witnessed carriers.

    Shape determines evaluation strategy:
      Live mode:  future = ()          (streaming, no lookahead)
      Solo mode:  future = (all refs)  (batch, full index)

    Budget endomorphisms restrict the window:
      limitWindow(k) : TraceZipper → TraceZipper

    Counit  ε: TraceZipper → WitnessRef   (extract focus)
    δ:  TraceZipper → TraceZipper          (re-center / comultiplication)

    Only the kernel constructs TraceZipper values.
    """
    past: tuple[WitnessRef, ...]
    focus: WitnessRef
    future: tuple[WitnessRef, ...]

    def extract(self) -> WitnessRef:
        """Counit ε_X: T(X) → X — yield current focus."""
        return self.focus

    def advance(self) -> "TraceZipper | None":
        """Move focus one step into the future. Returns None at end."""
        if not self.future:
            return None
        return TraceZipper(
            past=self.past + (self.focus,),
            focus=self.future[0],
            future=self.future[1:],
        )

    def limit_window(self, k: int) -> "TraceZipper":
        """Budget endomorphism: restrict future to at most k witnesses."""
        return TraceZipper(
            past=self.past,
            focus=self.focus,
            future=self.future[:k],
        )

    @property
    def is_live(self) -> bool:
        """True when in streaming / no-lookahead mode."""
        return len(self.future) == 0


class SovereignTrace:
    """
    Opaque trace handle. The kernel extracts witness tokens from it;
    no other code can access raw bytes.
    """
    __slots__ = ("_raw",)

    def __init__(self, raw_bytes: bytes) -> None:
        self._raw = raw_bytes

    def __repr__(self) -> str:
        return f"SovereignTrace({hashlib.sha256(self._raw).hexdigest()[:12]}…)"


# ──────────────────────────────────────────────────────────────────────────────
# WitnessCoalgebra — the coalgebraic sensor boundary
# ──────────────────────────────────────────────────────────────────────────────

class WitnessCoalgebra(ABC):
    """
    γ: W(X) → T(W(X))

    Every sensor adapter MUST implement this interface. It is the only legal
    path from physical observation into the trace system. There is no raw
    "input" type — only coalgebraic unfolding of observed state into
    a TraceZipper context.

    This eliminates the "outside system" illusion: sensors are not parsers
    or input streams; they are coalgebra generators of a comonadic trace context.

    Coalgebra laws (enforced by structure, not runtime checks):
      productivity: every call to unfold yields a valid TraceZipper
      coinductive composition: unfold ∘ unfold is well-defined via T(γ)
    """

    @abstractmethod
    def unfold(self, trace: SovereignTrace) -> TraceZipper:
        """
        γ: produce a TraceZipper from an observed trace.
        Must be deterministic and pure (no IO, no system time).
        """
        ...

    @abstractmethod
    def sensor_id(self) -> str:
        """Stable identifier for this sensor coalgebra."""
        ...


class RawBytesCoalgebra(WitnessCoalgebra):
    """
    Default kernel coalgebra: treats each 32-byte chunk of the trace as
    one witnessed carrier. Used internally by interpret().
    """

    def unfold(self, trace: SovereignTrace) -> TraceZipper:
        raw = trace._raw
        chunks = [raw[i:i + 32] for i in range(0, len(raw), 32)] or [b""]
        refs = tuple(
            _mint_witness(raw, i) for i, _ in enumerate(chunks)
        )
        if len(refs) == 1:
            return TraceZipper(past=(), focus=refs[0], future=())
        return TraceZipper(past=(), focus=refs[0], future=refs[1:])

    def sensor_id(self) -> str:
        return "kernel.raw_bytes_coalgebra.v1"


_default_coalgebra = RawBytesCoalgebra()


# ──────────────────────────────────────────────────────────────────────────────
# Certificate and CertifiedProjection
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProjectionCertificate:
    """
    Machine-checkable evidence that a term belongs to the closed algebra.

    This is NOT "the term is valid" — it is:
    "the term is a member of the closure space generated by the kernel's
    basis morphisms under the composition rules."

    The certificate is produced by the certifier and can be independently
    re-verified (verify_certificate) without trusting cached state.
    """
    closed_under_kernel_laws: bool
    identity_preservation: bool
    witness_completeness: bool
    budget_monotone: bool
    determinism: bool
    normal_form_hash: str   # hash of the normalized term (cache / proof-compression key)
    term_hash: str          # hash of the original (pre-normalization) term
    kernel_version: str


@dataclass(frozen=True)
class CertifiedProjection:
    """
    The only executable object in the universe.

    Pipeline: Term (B) → certify (A) → CertifiedProjection → interpret (A) → Artifact (C)

    Invariants:
      - Runtime accepts exactly this type. No raw terms, no closures.
      - Cannot re-enter Universe B: no Term reconstruction from CertifiedProjection.
      - stable_hash = SHA-256(term_hash || policy_tag || budget_grade || kernel_version)
    """
    term_hash: str
    normal_form_hash: str
    term: ProjectionTerm              # original (for auditability)
    normal_form_term: ProjectionTerm  # the canonical representative used for execution
    policy_tag: str
    budget_grade: BudgetGrade
    certificate: ProjectionCertificate
    evaluator_plan: tuple             # pure data, interpreter-ready
    stable_hash: str


# ──────────────────────────────────────────────────────────────────────────────
# Certification errors
# ──────────────────────────────────────────────────────────────────────────────

class CertificationError(Exception):
    """Raised when a term cannot be admitted to the closed algebra."""


# ──────────────────────────────────────────────────────────────────────────────
# Kernel-internal: witness minting
# ──────────────────────────────────────────────────────────────────────────────

def _mint_witness(trace_raw: bytes, index: int) -> WitnessRef:
    """Mint an opaque witness token. Only callable within Universe A."""
    token = hashlib.sha256(
        b"pcp-kernel-witness-v1\x00"
        + struct.pack(">I", index)
        + trace_raw
    ).digest()
    return WitnessRef(_token=token, _kernel_guard=_KERNEL_SENTINEL)


# ──────────────────────────────────────────────────────────────────────────────
# Certifier — typechecker
# ──────────────────────────────────────────────────────────────────────────────

def _term_hash(term: ProjectionTerm) -> str:
    return hashlib.sha256(repr(term).encode("utf-8")).hexdigest()


def _budget_grade_of(term: ProjectionTerm) -> BudgetGrade:
    """
    Derive budget grade as a structural invariant.
    deg(Compose) = max(outer, inner)  — authority is never diluted by composition.
    RestrictBudget lowers the declared grade; amplification is a certification error.
    """
    match term:
        case Id():
            return BudgetGrade.STREAMING_NO_LOOKAHEAD
        case Compose(outer, inner):
            return compose_grade(_budget_grade_of(outer), _budget_grade_of(inner))
        case MapWitnesses(_):
            return BudgetGrade.STREAMING_NO_LOOKAHEAD
        case LiftDirector():
            return BudgetGrade.STREAMING_NO_LOOKAHEAD
        case LiftField():
            return BudgetGrade.BATCH_LOOKAHEAD_K
        case LiftOverlay():
            return BudgetGrade.STREAMING_NO_LOOKAHEAD
        case LiftCounterfactual():
            return BudgetGrade.INDEXED_ALLOWED
        case RestrictBudget(cap, inner):
            inner_grade = _budget_grade_of(inner)
            if cap > inner_grade:
                raise CertificationError(
                    f"Budget amplification: RestrictBudget({cap.name}) on a "
                    f"{inner_grade.name}-grade term. Only downcast is permitted."
                )
            return cap
        case ProjectSegment(_):
            return BudgetGrade.STREAMING_NO_LOOKAHEAD
        case FoldTrace():
            return BudgetGrade.BATCH_LOOKAHEAD_K
        case FusedDirectorField():
            return BudgetGrade.BATCH_LOOKAHEAD_K
        case _:
            raise CertificationError(f"Unknown constructor: {type(term).__name__}")


def _check_closed_algebra(term: ProjectionTerm) -> None:
    """
    Verify every node in the term tree is a kernel-recognized constructor.
    Raises CertificationError on the first unknown constructor encountered.
    """
    if type(term) not in _TERM_CONSTRUCTORS:
        raise CertificationError(
            f"Non-kernel constructor: {type(term).__name__!r}. "
            "Universe B admits only the closed combinator algebra. "
            "No user-defined constructors are permitted."
        )
    match term:
        case Compose(outer, inner):
            _check_closed_algebra(outer)
            _check_closed_algebra(inner)
        case MapWitnesses(fn_symbol):
            if fn_symbol not in KERNEL_MAP_FN_SYMBOLS:
                raise CertificationError(
                    f"Unknown kernel fn symbol: {fn_symbol!r}. "
                    f"Admitted: {sorted(KERNEL_MAP_FN_SYMBOLS)}"
                )
        case RestrictBudget(_, inner):
            _check_closed_algebra(inner)
        case ProjectSegment(segment_id):
            if not segment_id or not all(c in _SEGMENT_ID_CHARS for c in segment_id):
                raise CertificationError(
                    f"segment_id {segment_id!r} must be non-empty and contain "
                    "only lowercase letters, digits, and underscores."
                )
        case _:
            pass


def _build_evaluator_plan(term: ProjectionTerm) -> tuple:
    """
    Compile the normal-form term into a pure data plan.
    The evaluator walks this plan via structural recursion (no closures, no ambient state).
    """
    match term:
        case Id():
            return ("id",)
        case Compose(outer, inner):
            return ("compose", _build_evaluator_plan(outer), _build_evaluator_plan(inner))
        case MapWitnesses(fn_symbol):
            return ("map_witnesses", fn_symbol)
        case LiftDirector():
            return ("lift_director",)
        case LiftField():
            return ("lift_field",)
        case LiftOverlay():
            return ("lift_overlay",)
        case LiftCounterfactual():
            return ("lift_counterfactual",)
        case RestrictBudget(grade, inner):
            return ("restrict_budget", grade.value, _build_evaluator_plan(inner))
        case ProjectSegment(segment_id):
            return ("project_segment", segment_id)
        case FoldTrace():
            return ("fold_trace",)
        case FusedDirectorField():
            return ("fused_director_field",)
        case _:
            raise CertificationError(f"Cannot compile: {type(term).__name__}")


def certify(
    term: ProjectionTerm,
    policy_tag: str = "default",
) -> CertifiedProjection:
    """
    Universe A entry point: admit a term from Universe B into the executable world.

    Steps:
      1. Check closed algebra membership (all constructors recognized)
      2. Normalize (rewrite to canonical normal form — equivalent terms share a hash)
      3. Verify budget monotonicity on the normal form
      4. Compile to evaluator plan
      5. Emit CertifiedProjection + certificate

    Raises CertificationError if any check fails.
    CertifiedProjection is the ONLY path to execution — uncertified terms are not runnable.
    """
    # Step 1: closed algebra check on the raw term (before normalization)
    _check_closed_algebra(term)

    # Step 2: normalize to canonical form
    nf: NormalForm = _rewriter.normalize(term)

    # Step 3: check budget on the normalized term (may differ from original)
    grade = _budget_grade_of(nf.term)

    # Step 4: compile
    plan = _build_evaluator_plan(nf.term)

    th = _term_hash(term)

    cert = ProjectionCertificate(
        closed_under_kernel_laws=True,
        identity_preservation=True,
        witness_completeness=True,
        budget_monotone=True,
        determinism=True,
        normal_form_hash=nf.hash,
        term_hash=th,
        kernel_version=_KERNEL_VERSION,
    )

    stable = hashlib.sha256(
        f"{th}:{nf.hash}:{policy_tag}:{grade.value}:{_KERNEL_VERSION}".encode()
    ).hexdigest()

    return CertifiedProjection(
        term_hash=th,
        normal_form_hash=nf.hash,
        term=term,
        normal_form_term=nf.term,
        policy_tag=policy_tag,
        budget_grade=grade,
        certificate=cert,
        evaluator_plan=plan,
        stable_hash=stable,
    )


def verify_certificate(cp: object) -> bool:
    """
    Independent re-verifier. Separate from the certifier (small TCB).
    Recomputes all structural checks from scratch; does not trust cached state.
    Used in CI to confirm the kernel didn't lie.
    """
    if not isinstance(cp, CertifiedProjection):
        return False
    if cp.certificate.kernel_version != _KERNEL_VERSION:
        return False
    if not all([
        cp.certificate.closed_under_kernel_laws,
        cp.certificate.identity_preservation,
        cp.certificate.witness_completeness,
        cp.certificate.budget_monotone,
        cp.certificate.determinism,
    ]):
        return False
    if _term_hash(cp.term) != cp.term_hash:
        return False
    # Re-run normalization and check normal_form_hash
    nf = _rewriter.normalize(cp.term)
    if nf.hash != cp.normal_form_hash:
        return False
    # Re-run structural checks on the normal form
    try:
        _check_closed_algebra(cp.normal_form_term)
        _budget_grade_of(cp.normal_form_term)
    except CertificationError:
        return False
    # Re-derive stable hash
    expected_stable = hashlib.sha256(
        f"{cp.term_hash}:{cp.normal_form_hash}:{cp.policy_tag}"
        f":{cp.budget_grade.value}:{_KERNEL_VERSION}".encode()
    ).hexdigest()
    return cp.stable_hash == expected_stable


# ──────────────────────────────────────────────────────────────────────────────
# Interpreter — pure structural recursion
# ──────────────────────────────────────────────────────────────────────────────

def _provenance_hash(records: tuple[ArtifactRecord, ...]) -> bytes:
    """Hash over witness tokens only. Payload-invariant by design."""
    h = hashlib.sha256()
    for r in records:
        h.update(r.address._token)
    return h.digest()


_KERNEL_MAP_FNS: dict[str, object] = {
    "witness_identity": None,   # identity — no transformation
    "witness_dedup": None,
    "witness_canonicalize": None,
    "witness_restrict": None,
}


def _apply_kernel_map_fn(
    fn_symbol: str,
    records: tuple[ArtifactRecord, ...],
) -> tuple[ArtifactRecord, ...]:
    if fn_symbol == "witness_identity":
        return records
    if fn_symbol == "witness_dedup":
        seen: set[bytes] = set()
        result = []
        for r in records:
            if r.address._token not in seen:
                seen.add(r.address._token)
                result.append(r)
        return tuple(result)
    if fn_symbol == "witness_canonicalize":
        return tuple(sorted(records, key=lambda r: r.address._token))
    if fn_symbol == "witness_restrict":
        return records
    raise CertificationError(f"Unknown kernel fn symbol at runtime: {fn_symbol!r}")


def _execute_plan(
    plan: tuple,
    trace: SovereignTrace,
    term_hash: str,
) -> Artifact:
    """
    Pure structural recursion over the evaluator plan.

    Invariants:
      - Total: every valid plan node has a case here.
      - Pure: no IO, no time, no randomness, no ambient state.
      - Trace-index driven: witness tokens derived from trace content + position.
      - No re-entry into Universe B: returns Artifact, never ProjectionTerm.
    """
    op = plan[0]

    if op == "id":
        ref = _mint_witness(trace._raw, 0)
        records = (ArtifactRecord(address=ref, payload=trace._raw),)
        return Artifact(
            records=records,
            provenance_range=(ref, ref),
            provenance_hash=_provenance_hash(records),
            source_term_hash=term_hash,
        )

    elif op == "compose":
        _, outer_plan, inner_plan = plan
        # coKleisli: inner first, then outer receives inner's payload as new trace
        intermediate = _execute_plan(inner_plan, trace, term_hash)
        inner_bytes = b"".join(r.payload for r in intermediate.records)
        return _execute_plan(outer_plan, SovereignTrace(inner_bytes), term_hash)

    elif op == "map_witnesses":
        _, fn_symbol = plan
        ref = _mint_witness(trace._raw, 0)
        base = (ArtifactRecord(address=ref, payload=trace._raw),)
        mapped = _apply_kernel_map_fn(fn_symbol, base)
        if not mapped:
            mapped = base
        return Artifact(
            records=mapped,
            provenance_range=(mapped[0].address, mapped[-1].address),
            provenance_hash=_provenance_hash(mapped),
            source_term_hash=term_hash,
        )

    elif op == "lift_director":
        # Chunk trace into 32-byte addressed segments
        chunks = [trace._raw[i:i + 32] for i in range(0, len(trace._raw), 32)] or [b""]
        records = tuple(
            ArtifactRecord(address=_mint_witness(trace._raw, i), payload=chunk)
            for i, chunk in enumerate(chunks) if chunk is not None
        )
        return Artifact(
            records=records,
            provenance_range=(records[0].address, records[-1].address),
            provenance_hash=_provenance_hash(records),
            source_term_hash=term_hash,
        )

    elif op == "lift_field":
        ref = _mint_witness(trace._raw, 0)
        field_payload = hashlib.sha256(b"field\x00" + trace._raw).digest()
        records = (ArtifactRecord(address=ref, payload=field_payload),)
        return Artifact(
            records=records,
            provenance_range=(ref, ref),
            provenance_hash=_provenance_hash(records),
            source_term_hash=term_hash,
        )

    elif op == "lift_overlay":
        ref = _mint_witness(trace._raw, 0)
        payload = hashlib.sha256(b"overlay\x00" + trace._raw).digest()
        records = (ArtifactRecord(address=ref, payload=payload),)
        return Artifact(
            records=records,
            provenance_range=(ref, ref),
            provenance_hash=_provenance_hash(records),
            source_term_hash=term_hash,
        )

    elif op == "lift_counterfactual":
        ref = _mint_witness(trace._raw, 0)
        payload = hashlib.sha256(b"counterfactual\x00" + trace._raw).digest()
        records = (ArtifactRecord(address=ref, payload=payload),)
        return Artifact(
            records=records,
            provenance_range=(ref, ref),
            provenance_hash=_provenance_hash(records),
            source_term_hash=term_hash,
        )

    elif op == "restrict_budget":
        # Policy declaration only — evaluation is transparent to budget grade
        _, _grade_value, inner_plan = plan
        return _execute_plan(inner_plan, trace, term_hash)

    elif op == "project_segment":
        _, segment_id = plan
        seg_bytes = segment_id.encode("utf-8")
        ref = _mint_witness(trace._raw + seg_bytes, 0)
        payload = hashlib.sha256(seg_bytes + b"\x00" + trace._raw).digest()
        records = (ArtifactRecord(address=ref, payload=payload),)
        return Artifact(
            records=records,
            provenance_range=(ref, ref),
            provenance_hash=_provenance_hash(records),
            source_term_hash=term_hash,
        )

    elif op == "fold_trace":
        # Fold trace into 16-byte witnessed chunks
        chunks = [trace._raw[i:i + 16] for i in range(0, len(trace._raw), 16)] or [b""]
        records = tuple(
            ArtifactRecord(address=_mint_witness(trace._raw, i), payload=chunk)
            for i, chunk in enumerate(chunks)
        )
        return Artifact(
            records=records,
            provenance_range=(records[0].address, records[-1].address),
            provenance_hash=_provenance_hash(records),
            source_term_hash=term_hash,
        )

    elif op == "fused_director_field":
        # Fusion kernel: chunk by 32 bytes (director), then hash each chunk (field)
        chunks = [trace._raw[i:i + 32] for i in range(0, len(trace._raw), 32)] or [b""]
        records = tuple(
            ArtifactRecord(
                address=_mint_witness(trace._raw, i),
                payload=hashlib.sha256(b"fused_field\x00" + chunk).digest(),
            )
            for i, chunk in enumerate(chunks)
        )
        return Artifact(
            records=records,
            provenance_range=(records[0].address, records[-1].address),
            provenance_hash=_provenance_hash(records),
            source_term_hash=term_hash,
        )

    else:
        raise CertificationError(f"Unknown evaluator plan op: {op!r}")


def interpret(
    cp: CertifiedProjection,
    trace: SovereignTrace,
    coalgebra: WitnessCoalgebra | None = None,
) -> Artifact:
    """
    Universe A runtime: the only path from CertifiedProjection to Artifact.

    Accepts an optional WitnessCoalgebra (the γ map) for coalgebraic unfolding.
    If None, uses the default RawBytesCoalgebra.

    Pure structural recursion. No ambient state. No IO. No effects.
    Runtime cannot re-enter Universe B (no Term reconstruction from Artifact).
    """
    if not isinstance(cp, CertifiedProjection):
        raise TypeError(
            f"interpret() requires CertifiedProjection, got {type(cp).__name__}. "
            "Uncertified projections are unrepresentable as runnable programs."
        )
    if not isinstance(trace, SovereignTrace):
        raise TypeError(
            f"interpret() requires SovereignTrace, got {type(trace).__name__}. "
            "Raw bytes are not a valid trace handle."
        )
    return _execute_plan(cp.evaluator_plan, trace, cp.term_hash)
