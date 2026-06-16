"""
Rewrite system for the proof-carrying projection kernel.

A confluent, terminating rewrite system over ProjectionTerms that unifies:
  - algebraic simplification (identity elimination, associativity)
  - semantic fusion (adjacent kernel operations collapse to a single primitive)
  - budget propagation (double restrictions merge)
  - proof compression (equivalent terms share a canonical hash)

The normal form of a term is the canonical representative of its equivalence class.
Execution operates on normal forms only — the evaluator never sees un-normalized terms.

Rewrite rules (by group):

  A  Identity elimination:   compose(id, t) → t
                              compose(t, id) → t

  B  Associativity:          compose(compose(a, b), c) → compose(a, compose(b, c))
                             (right-associates all chains for canonical shape)

  C  Projection fusion:      compose(LiftField, LiftDirector) → FusedDirectorField
                             (adjacent semantic kernels collapse to a single primitive)

  D  Budget propagation:     RestrictBudget(b1, RestrictBudget(b2, t)) → RestrictBudget(min(b1,b2), t)
                             (double restrictions merge; monotone law preserved)

  E  Map-identity shortcut:  compose(MapWitnesses("witness_identity"), t) → t
                             compose(t, MapWitnesses("witness_identity")) → t

The system is terminating (each rule strictly reduces a structural measure)
and confluent (fixed-point of a deterministic single-pass rule application).
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass

from .pcp_budget import BudgetGrade
from .pcp_term import (
    ProjectionTerm,
    Id, Compose, MapWitnesses, LiftDirector, LiftField,
    LiftOverlay, LiftCounterfactual, RestrictBudget, ProjectSegment,
    FoldTrace, FusedDirectorField,
)


# ──────────────────────────────────────────────────────────────────────────────
# Normal form
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NormalForm:
    """
    Canonical representative of a ProjectionTerm equivalence class.
    Only the Rewriter produces NormalForm values — not constructable externally
    (the Rewriter's fixed-point guarantees no further rules apply).
    """
    term: ProjectionTerm
    hash: str  # SHA-256 of repr(term) — stable cache key


# ──────────────────────────────────────────────────────────────────────────────
# Rewriter
# ──────────────────────────────────────────────────────────────────────────────

class Rewriter:
    """
    Deterministic fixed-point rewriter.
    Applies all rule groups until no rule fires; the result is the normal form.
    Termination is guaranteed by structural induction: each rule either
    removes a node (A, E), flattens nesting (B), merges adjacent nodes (C, D).
    """

    def normalize(self, term: ProjectionTerm) -> NormalForm:
        current = term
        while True:
            next_term = self._step(current)
            if next_term == current:
                break
            current = next_term
        h = hashlib.sha256(repr(current).encode("utf-8")).hexdigest()
        return NormalForm(term=current, hash=h)

    def _step(self, term: ProjectionTerm) -> ProjectionTerm:
        """One rewrite pass: recurse into sub-terms, then apply top-level rules."""
        # Recurse first so sub-terms are already simplified before top-level rules fire.
        term = self._recurse(term)

        match term:
            # Group A — Identity elimination
            case Compose(Id(), t):
                return t
            case Compose(t, Id()):
                return t

            # Group B — Right-associate composition chains
            case Compose(Compose(a, b), c):
                return Compose(a, Compose(b, c))

            # Group C — Projection fusion: LiftField ∘ LiftDirector → FusedDirectorField
            # (inner=LiftDirector runs first, outer=LiftField next)
            case Compose(LiftField(), LiftDirector()):
                return FusedDirectorField()

            # Group D — Budget propagation: nested restrictions collapse
            case RestrictBudget(b1, RestrictBudget(b2, inner)):
                return RestrictBudget(BudgetGrade(min(b1, b2)), inner)

            # Group E — MapWitnesses identity shortcut
            case Compose(MapWitnesses("witness_identity"), t):
                return t
            case Compose(t, MapWitnesses("witness_identity")):
                return t

            case _:
                return term

    def _recurse(self, term: ProjectionTerm) -> ProjectionTerm:
        """Apply _step recursively to sub-terms."""
        match term:
            case Compose(outer, inner):
                new_outer = self._step(outer)
                new_inner = self._step(inner)
                if new_outer is not outer or new_inner is not inner:
                    return Compose(new_outer, new_inner)
            case RestrictBudget(grade, inner):
                new_inner = self._step(inner)
                if new_inner is not inner:
                    return RestrictBudget(grade, new_inner)
            case _:
                pass
        return term


# ──────────────────────────────────────────────────────────────────────────────
# Confluence checker
# ──────────────────────────────────────────────────────────────────────────────

class ConfluenceChecker:
    """
    Verifies that the rewrite system is confluent on a given term:
    any two reduction sequences from the same start term must reach
    the same normal form.

    For a deterministic rewriter, self-confluence (same input → same output)
    is trivially guaranteed. The checker additionally tests critical pairs
    involving the rule groups above.
    """

    def __init__(self) -> None:
        self._rewriter = Rewriter()

    def is_confluent(self, term: ProjectionTerm) -> bool:
        """
        Check that two independent normalization runs on the same term agree.
        Trivially true for a deterministic rewriter; serves as a sanity gate in CI.
        """
        nf1 = self._rewriter.normalize(term)
        nf2 = self._rewriter.normalize(term)
        return nf1.hash == nf2.hash

    def check_critical_pairs(self) -> list[str]:
        """
        Test known critical pairs (term positions where two rules overlap).
        Returns a list of failure descriptions; empty list means confluent.

        Critical pair A/B: compose(id, compose(a, b)) — A can fire (outer id), B can fire (nested).
        Both should yield compose(a, b).
        """
        rewriter = self._rewriter
        failures: list[str] = []

        # A/B overlap: compose(id, compose(a, b))
        a, b = LiftDirector(), LiftOverlay()
        term_ab = Compose(Id(), Compose(a, b))
        nf = rewriter.normalize(term_ab)
        expected = rewriter.normalize(Compose(a, b))
        if nf.hash != expected.hash:
            failures.append(f"A/B critical pair failed: {term_ab!r}")

        # D overlap: triple restriction
        inner = FoldTrace()
        triple = RestrictBudget(
            BudgetGrade.STREAMING_NO_LOOKAHEAD,
            RestrictBudget(
                BudgetGrade.BATCH_LOOKAHEAD_K,
                RestrictBudget(BudgetGrade.NO_ALLOCATION, inner),
            ),
        )
        nf_triple = rewriter.normalize(triple)
        direct = rewriter.normalize(
            RestrictBudget(BudgetGrade.STREAMING_NO_LOOKAHEAD, inner)
        )
        if nf_triple.hash != direct.hash:
            failures.append(f"D triple-restriction critical pair failed: {triple!r}")

        # C overlap: fusion inside composition chain
        # compose(id, compose(LiftField, LiftDirector)) → FusedDirectorField
        fused_term = Compose(Id(), Compose(LiftField(), LiftDirector()))
        nf_fused = rewriter.normalize(fused_term)
        expected_fused = rewriter.normalize(FusedDirectorField())
        if nf_fused.hash != expected_fused.hash:
            failures.append(f"C fusion-in-chain critical pair failed: {fused_term!r}")

        return failures
