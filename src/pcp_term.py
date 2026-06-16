"""
Universe B: ProjectionTerm — pure syntax, zero semantics.

HARD WALL: This module defines NO evaluation, interpretation, reduction,
or execution primitives. B cannot define semantics. Only Universe A (pcp_kernel)
can evaluate. B is not permitted to hold a run/fold/reduce/interpret/exec method.

The algebra is CLOSED: the constructor set is finite and frozen.
No user-defined constructors. No closures. No extensibility leak.
New constructors require a kernel-reviewed primitive + versioned compiler update.

Composition in the projection algebra follows the coKleisli law:
    g ★ f = g ∘ T(f) ∘ δ
encoded here as Compose(outer, inner) where inner runs first.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Union

from .pcp_budget import BudgetGrade

# Kernel-approved map function symbols. Validated by the certifier; never evaluated here.
KERNEL_MAP_FN_SYMBOLS: frozenset[str] = frozenset({
    "witness_identity",
    "witness_restrict",
    "witness_dedup",
    "witness_canonicalize",
})

# Allowed characters in segment identifiers.
_SEGMENT_ID_CHARS: frozenset[str] = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789_"
)


# ── Basis morphisms ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Id:
    """Identity morphism. Preserves all witness structure."""


@dataclass(frozen=True)
class Compose:
    """
    Sequential composition. inner runs first, outer second.
    Budget grade = max(grade(outer), grade(inner)).
    Encodes coKleisli composition: g ★ f = g ∘ T(f) ∘ δ.
    """
    outer: "ProjectionTerm"
    inner: "ProjectionTerm"


@dataclass(frozen=True)
class MapWitnesses:
    """
    Apply a kernel-approved function symbol over the witness set.
    fn_symbol must be in KERNEL_MAP_FN_SYMBOLS — no closures, no user code.
    """
    fn_symbol: str


@dataclass(frozen=True)
class LiftDirector:
    """Project trace into director segment structure (chunked by address)."""


@dataclass(frozen=True)
class LiftField:
    """Project witnessed events into a vector field (requires lookahead)."""


@dataclass(frozen=True)
class LiftOverlay:
    """Project trace delta into overlay structure (streaming)."""


@dataclass(frozen=True)
class LiftCounterfactual:
    """Project trace into a counterfactual branch (full index required)."""


@dataclass(frozen=True)
class RestrictBudget:
    """
    Declare that the inner term must operate within grade cap.
    cap must be <= grade(inner): only DOWNCAST is permitted.
    Raising the cap (amplification) is rejected by the certifier.
    """
    grade: BudgetGrade
    inner: "ProjectionTerm"


@dataclass(frozen=True)
class ProjectSegment:
    """Project a specific named segment from the trace."""
    segment_id: str  # alphanumeric + underscore only, validated by certifier


@dataclass(frozen=True)
class FoldTrace:
    """Fold the full trace into an aggregate artifact (requires batch lookahead)."""


@dataclass(frozen=True)
class FusedDirectorField:
    """
    Fusion product of LiftDirector ∘ LiftField.
    Emitted by the rewriter; never constructed externally.
    Budget grade = BATCH_LOOKAHEAD_K (max of constituent grades).
    This is a kernel primitive added via versioned compiler update — not user extensibility.
    """


# ── Closed algebra ────────────────────────────────────────────────────────────

ProjectionTerm = Union[
    Id, Compose, MapWitnesses, LiftDirector, LiftField,
    LiftOverlay, LiftCounterfactual, RestrictBudget, ProjectSegment,
    FoldTrace, FusedDirectorField,
]

# The complete, frozen set of valid constructor types.
# Membership here is the definition of "belongs to the projection algebra."
_TERM_CONSTRUCTORS: frozenset[type] = frozenset({
    Id, Compose, MapWitnesses, LiftDirector, LiftField,
    LiftOverlay, LiftCounterfactual, RestrictBudget, ProjectSegment,
    FoldTrace, FusedDirectorField,
})
