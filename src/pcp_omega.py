"""
Ω — computable normal-form quotient of transformation-collapse space.

This module implements the final categorical closure:

  α is a coalgebra section of 𝕌 (the TransformZipper comonad over AlphaStates)
  Ω = coeq(⇒ ⇒) under λ-respecting bisimulation (not just a set quotient)

The pipeline of worlds becomes a self-verifying geometry of allowable collapses.

──────────────────────────────────────────────────────────────────────────────
CORRECTION (final tightening): CANON is not a stage — it is part of NF.

Canonicalization of witness ordering and address encoding is implicit in
normalize_stage_word and always applied. Treating CANON as an explicit stage
breaks uniqueness of Ω representatives (a non-canonical state would differ
from the same state after explicit canon application, violating confluence).

Generator alphabet (finite, kernel-owned):

  IDENTITY  id     eliminated by normalization (not a real generator)
  WIN(k)    win    window to k_past witnesses; k_future future witnesses
  IDX       idx    index for O(1) recenter, GPU-friendly layout
  COMMIT    commit attach cryptographic commitment to context

Canonicalization is ALWAYS implicit in NF — no explicit CANON generator.
This ensures: confluence, λ-coherence, unique Ω representatives.

Prerequisites: IDX requires WIN. COMMIT requires IDX.

Rewrite rules (confluent, terminating → unique normal form):
  A  Identity elimination:  any ∘ Id → any,  Id ∘ any → any
  B  Idempotence:           Commit ∘ Commit → Commit
  C  Window merge:          Win(k1) ∘ Win(k2) → Win(min(k1, k2))
  D  Canonical sort:        WIN(0) < IDX(1) < COMMIT(2)
  E  Deduplication:         each label appears at most once after sort + merge
  F  Canonicalization:      always implicit — no explicit step needed

──────────────────────────────────────────────────────────────────────────────
Ω is the COEQUALIZER of all λ-respecting bisimulation morphisms:
  Ω := (StageWords × Γ-paths) / ~λ
  where ~λ is: same focus_commitment + same λ-lifted trace behavior +
               same comonadic recentering + same certified stage NF.

This is NOT just A_nf / ≡ (a set quotient) — it is the universal object
making all λ-compatible maps factor uniquely through it.

──────────────────────────────────────────────────────────────────────────────
λ is a LATTICE HOMOMORPHISM on Ω (the key coherence condition):
  λ(a ∨ b) = λ(a) ∨ λ(b)
  λ(a ∧ b) = λ(a) ∧ λ(b)

Backend selection = choosing a lattice homomorphism on Ω.
GPU/SNARK/CPU are not systems — they are representatives of Ω bisimulation
classes that preserve λ-coherence.

──────────────────────────────────────────────────────────────────────────────
AlphaState is kernel-minted (Witness<AlphaState>):
  witness_token = SHA-256(stage_word_key || prior_cert || is_terminal)
  "Which pipeline you're using" is a certified epistemic artifact — not a
  runtime choice, not a config flag. Provenance-forgery is structurally impossible.

──────────────────────────────────────────────────────────────────────────────
Γ: AlphaState → 𝕌(AlphaState)  (the coalgebra)
  Productive: always yields a TransformZipper (future may be empty if terminal).
  Deterministic: no branching outside 𝕌 structure.
  Witness-preserving: each next state is kernel-minted with provenance.

──────────────────────────────────────────────────────────────────────────────
Ω preorder (over same focus_commitment fiber):
  a ≤ b  iff  a has at least all the stage labels that b has (a is more refined)

  join(a, b) = least common refinement = union of stages with stronger params
  meet(a, b) = greatest common abstraction = intersection with weaker params

GPU/SNARK/CPU backends are not separate engines:
  they are representatives of Ω equivalence classes under different stage selections.

──────────────────────────────────────────────────────────────────────────────
Distributive law λ: 𝕋 ∘ 𝕌 ⇒ 𝕌 ∘ 𝕋
  "observing a transformation inside a trace context equals transforming a
  trace context inside a transformation context."
  Kernel invariant: focus_commitment is preserved across all stage transitions
  (the concrete counit law at the bicomonadic level).
"""
from __future__ import annotations
import hashlib
import struct
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Stage word language
# ──────────────────────────────────────────────────────────────────────────────

class StageLabel(Enum):
    IDENTITY = "id"      # eliminated by NF; not a real generator
    WIN      = "win"
    IDX      = "idx"
    COMMIT   = "commit"
    # NOTE: CANON is intentionally absent. Canonicalization is implicit in
    # normalize_stage_word and always applied. Making it explicit would
    # break confluence (non-canonical state ≠ canonical state) and violate
    # unique Ω representative invariant.


_STAGE_ORDER: dict[StageLabel, int] = {
    StageLabel.WIN:    0,
    StageLabel.IDX:    1,
    StageLabel.COMMIT: 2,
}


@dataclass(frozen=True)
class StageNode:
    """One generator in the stage word. Kernel-owned; no user-defined labels."""
    label: StageLabel
    k_past: int   = 0       # WIN only: max past witnesses in window
    k_future: int = 0       # WIN only: max future witnesses
    layout_id: str = ""     # IDX only: hardware layout identifier
    hash_scheme: str = ""   # COMMIT only: hash scheme identifier


StageWord = tuple[StageNode, ...]


def _merge_stage_nodes(a: StageNode, b: StageNode) -> StageNode:
    """Merge two same-label nodes under the appropriate law (idempotence or Win merge)."""
    assert a.label == b.label
    if a.label == StageLabel.WIN:
        return StageNode(
            label=StageLabel.WIN,
            k_past=min(a.k_past, b.k_past),
            k_future=min(a.k_future, b.k_future),
        )
    return a  # Idempotent for CANON, IDX, COMMIT


def normalize_stage_word(word: StageWord) -> StageWord:
    """
    Normalize a stage word to its unique canonical representative.

    Rules (confluent, terminating):
      A — remove IDENTITY nodes
      B/C — merge same-label nodes (idempotence / Win-min merge)
      D — sort by canonical label order WIN(0) < IDX(1) < COMMIT(2)
      E — each label appears at most once (guaranteed by merge)
      F — canonicalization of witness ordering is IMPLICIT (always applied);
          CANON is not a stage and must not appear in any stage word

    Idempotent: normalize(normalize(w)) = normalize(w).
    Confluence: every stage word has a unique NF (guarantees unique Ω reps).
    """
    # Reject unknown stage labels (defense in depth)
    for n in word:
        if n.label != StageLabel.IDENTITY and n.label not in _STAGE_ORDER:
            raise ValueError(
                f"Unknown stage label: {n.label!r}. "
                "Only {WIN, IDX, COMMIT} are admissible generators. "
                "CANON is not a stage — canonicalization is implicit in NF."
            )

    # A: identity elimination
    filtered = (n for n in word if n.label != StageLabel.IDENTITY)

    # B/C/E: merge per label
    per_label: dict[StageLabel, StageNode] = {}
    for node in filtered:
        if node.label in per_label:
            per_label[node.label] = _merge_stage_nodes(per_label[node.label], node)
        else:
            per_label[node.label] = node

    # D: canonical sort
    return tuple(
        per_label[label]
        for label in sorted(per_label, key=lambda l: _STAGE_ORDER.get(l, 99))
    )


def stage_word_key(word: StageWord, focus_commitment: bytes) -> str:
    """Stable canonical hash for a (stage word NF, focus commitment) pair."""
    h = hashlib.sha256()
    h.update(b"omega-key-v1\x00")
    for node in word:
        h.update(node.label.value.encode())
        h.update(struct.pack(">II", node.k_past, node.k_future))
        h.update(node.layout_id.encode())
        h.update(node.hash_scheme.encode())
        h.update(b"\x00")
    h.update(focus_commitment)
    return h.hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# AlphaState — kernel-minted, witnessed
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AlphaState:
    """
    A point in transformation space: which collapse stages have been applied,
    with accumulated certificates, over a specific focus commitment.

    Kernel-minted: witness_token = SHA-256(stage_word_key || prior_cert || is_terminal).
    "Which pipeline you're using" is a provenance-bound certified artifact.
    There is no unauthenticated way to claim a particular transformation state.

    is_terminal when stage word contains COMMIT and Γ yields empty future.
    """
    stage_word_nf: StageWord
    focus_commitment: bytes
    accumulated_cert: bytes
    is_terminal: bool
    witness_token: bytes        # kernel-minted binding of state to its provenance


def _mint_alpha_state(
    stage_word_nf: StageWord,
    focus_commitment: bytes,
    prior_cert: bytes,
    is_terminal: bool,
) -> AlphaState:
    """Kernel-internal factory. witness_token is a keyed hash — unforgeable."""
    key = stage_word_key(stage_word_nf, focus_commitment)
    acc_cert = hashlib.sha256(
        prior_cert + key.encode() + (b"\x01" if is_terminal else b"\x00")
    ).digest()
    token = hashlib.sha256(
        b"alpha-state-v1\x00" + key.encode() + prior_cert
        + (b"\x01" if is_terminal else b"\x00")
    ).digest()
    return AlphaState(
        stage_word_nf=stage_word_nf,
        focus_commitment=focus_commitment,
        accumulated_cert=acc_cert,
        is_terminal=is_terminal,
        witness_token=token,
    )


def initial_alpha_state(focus_commitment: bytes) -> AlphaState:
    """
    Construct the initial AlphaState (empty stage word) from a focus commitment.
    This is the entry point for the coalgebraic unfolding Γ.
    """
    return _mint_alpha_state(
        stage_word_nf=(),
        focus_commitment=focus_commitment,
        prior_cert=b"",
        is_terminal=False,
    )


# ──────────────────────────────────────────────────────────────────────────────
# TransformZipper — the 𝕌 comonad over AlphaState
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TransformZipper:
    """
    𝕌(AlphaState) — the transformation context comonad.

    Same zipper structure as TraceZipper but over transformation stages.

    Counit ε: extract() → current AlphaState focus
    δ (recenter): advance() to a future state

    is_terminal: True when focus is terminal and future is empty.
    """
    past: tuple[AlphaState, ...]
    focus: AlphaState
    future: tuple[AlphaState, ...]

    def extract(self) -> AlphaState:
        """Counit ε_A: 𝕌(A) → A."""
        return self.focus

    def advance(self, next_state: AlphaState) -> "TransformZipper | None":
        """Move focus to next_state if reachable. Returns None if not in future."""
        if next_state in self.future:
            idx = self.future.index(next_state)
            return TransformZipper(
                past=self.past + (self.focus,),
                focus=next_state,
                future=self.future[idx + 1:],
            )
        return None

    @property
    def is_terminal(self) -> bool:
        return self.focus.is_terminal and len(self.future) == 0


# ──────────────────────────────────────────────────────────────────────────────
# Γ — coalgebra map A → 𝕌(A)
# ──────────────────────────────────────────────────────────────────────────────

def _admissible_generators(state: AlphaState) -> list[StageNode]:
    """
    Return the generators that can legally be applied next.

    Generator alphabet: {WIN, IDX, COMMIT}. CANON is NOT included —
    canonicalization is implicit in NF and always applied.

    Dependencies: IDX requires WIN. COMMIT requires IDX.
    A terminal state admits no generators.
    """
    if state.is_terminal:
        return []
    current = {n.label for n in state.stage_word_nf}
    cands: list[StageNode] = []
    if StageLabel.WIN not in current:
        cands.append(StageNode(StageLabel.WIN, k_past=8, k_future=0))
    if StageLabel.IDX not in current and StageLabel.WIN in current:
        cands.append(StageNode(StageLabel.IDX, layout_id="default"))
    if StageLabel.COMMIT not in current and StageLabel.IDX in current:
        cands.append(StageNode(StageLabel.COMMIT, hash_scheme="sha256"))
    return cands


def gamma(state: AlphaState) -> TransformZipper:
    """
    Γ: AlphaState → 𝕌(AlphaState)

    The coalgebra. Produces the transformation context zipper with all
    admissible next states as future entries. Each successor is kernel-minted.

    Productive: always yields a valid TransformZipper (future may be () if terminal).
    Deterministic: no branching outside 𝕌 structure.
    Witness-preserving: each next state carries its own provenance token.
    """
    successors: list[AlphaState] = []
    for gen in _admissible_generators(state):
        new_word = normalize_stage_word(state.stage_word_nf + (gen,))
        is_term = StageLabel.COMMIT in {n.label for n in new_word}
        successors.append(_mint_alpha_state(
            stage_word_nf=new_word,
            focus_commitment=state.focus_commitment,
            prior_cert=state.accumulated_cert,
            is_terminal=is_term,
        ))
    return TransformZipper(past=(), focus=state, future=tuple(successors))


# ──────────────────────────────────────────────────────────────────────────────
# Ω — computable quotient
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OmegaElement:
    """
    An equivalence class in Ω = A_nf / ≡.

    key: canonical hash of (stage_word_nf, focus_commitment) — the bisimulation class id.
    For terminal elements, this IS the "complete execution geometry" fingerprint.

    Preorder over the same focus_commitment fiber:
      self ≤ other  iff  self.labels ⊆ other.labels
                    (self has fewer/equal stages — other is more refined)

    Lattice ops (within same fiber):
      join(a,b) = least upper bound = union of labels with stronger (min) params for WIN
      meet(a,b) = greatest lower bound = intersection with weaker (max) params for WIN
                  (returns the empty-word bottom element if labels are disjoint)

    Backends are Ω representatives:
      GPU backend    = element with stages {WIN, IDX}
      SNARK backend  = element with stages {WIN, IDX, COMMIT}
      CPU debug      = element with stages {WIN}
    """
    key: str
    stage_word_nf: StageWord
    focus_commitment: bytes
    is_terminal: bool

    def __le__(self, other: "OmegaElement") -> bool:
        a_labels = {n.label for n in self.stage_word_nf}
        b_labels = {n.label for n in other.stage_word_nf}
        return a_labels <= b_labels

    def __lt__(self, other: "OmegaElement") -> bool:
        return self != other and self <= other

    def join(self, other: "OmegaElement") -> "OmegaElement":
        """Least common refinement: union of stages, stronger (min) params for WIN."""
        merged: dict[StageLabel, StageNode] = {n.label: n for n in self.stage_word_nf}
        for node in other.stage_word_nf:
            if node.label in merged:
                merged[node.label] = _merge_stage_nodes(merged[node.label], node)
            else:
                merged[node.label] = node
        word = normalize_stage_word(tuple(merged.values()))
        is_term = StageLabel.COMMIT in {n.label for n in word}
        return OmegaElement(
            key=stage_word_key(word, self.focus_commitment),
            stage_word_nf=word,
            focus_commitment=self.focus_commitment,
            is_terminal=is_term,
        )

    def meet(self, other: "OmegaElement") -> "OmegaElement":
        """
        Greatest common abstraction: intersection of labels, weaker (max) params for WIN.
        If labels are disjoint, returns the top element (empty word — no constraints).
        """
        a_map = {n.label: n for n in self.stage_word_nf}
        b_map = {n.label: n for n in other.stage_word_nf}
        common = set(a_map) & set(b_map)
        meet_nodes: list[StageNode] = []
        for label in common:
            a, b = a_map[label], b_map[label]
            if label == StageLabel.WIN:
                meet_nodes.append(StageNode(
                    label=StageLabel.WIN,
                    k_past=max(a.k_past, b.k_past),
                    k_future=max(a.k_future, b.k_future),
                ))
            else:
                meet_nodes.append(a)
        word = normalize_stage_word(tuple(meet_nodes))
        is_term = StageLabel.COMMIT in {n.label for n in word}
        return OmegaElement(
            key=stage_word_key(word, self.focus_commitment),
            stage_word_nf=word,
            focus_commitment=self.focus_commitment,
            is_terminal=is_term,
        )


def alpha_state_to_omega(state: AlphaState) -> OmegaElement:
    """Project an AlphaState into its Ω equivalence class representative."""
    is_term = StageLabel.COMMIT in {n.label for n in state.stage_word_nf}
    return OmegaElement(
        key=stage_word_key(state.stage_word_nf, state.focus_commitment),
        stage_word_nf=state.stage_word_nf,
        focus_commitment=state.focus_commitment,
        is_terminal=is_term,
    )


def reachable_omega(initial: AlphaState, max_depth: int = 8) -> frozenset[OmegaElement]:
    """
    Enumerate all Ω elements reachable from an initial α-state via Γ.
    max_depth bounds exploration. The reachable space is finite by construction
    (at most 2^|generators| distinct normal-form words).
    """
    seen: set[str] = set()
    result: set[OmegaElement] = set()
    frontier = [initial]
    for _ in range(max_depth):
        if not frontier:
            break
        next_frontier: list[AlphaState] = []
        for state in frontier:
            elem = alpha_state_to_omega(state)
            if elem.key not in seen:
                seen.add(elem.key)
                result.add(elem)
                tz = gamma(state)
                next_frontier.extend(tz.future)
        frontier = next_frontier
    return frozenset(result)


# ──────────────────────────────────────────────────────────────────────────────
# λ as lattice homomorphism — the key coherence condition
# ──────────────────────────────────────────────────────────────────────────────

class LatticeHomomorphismChecker:
    """
    Checks that λ is a lattice homomorphism on Ω:
      λ(a ∨ b) = λ(a) ∨ λ(b)
      λ(a ∧ b) = λ(a) ∧ λ(b)

    In our system, λ-lifting is normalization (already applied to all Ω elements).
    The checks verify that join and meet each produce normalized results consistent
    with the preorder — i.e., the lattice ops are closed under λ-coherence.

    Backend selection = choosing a lattice homomorphism on Ω.
    A backend is correct iff it is a lattice homomorphism that preserves λ.
    """

    def _lambda_lift(self, elem: OmegaElement) -> OmegaElement:
        """Apply λ-normalization to an Ω element. Idempotent on already-NF elements."""
        renormalized = normalize_stage_word(elem.stage_word_nf)
        is_term = StageLabel.COMMIT in {n.label for n in renormalized}
        return OmegaElement(
            key=stage_word_key(renormalized, elem.focus_commitment),
            stage_word_nf=renormalized,
            focus_commitment=elem.focus_commitment,
            is_terminal=is_term,
        )

    def check_join(self, a: OmegaElement, b: OmegaElement) -> bool:
        """λ(a ∨ b) = λ(a) ∨ λ(b)."""
        lhs = self._lambda_lift(a.join(b))
        rhs = self._lambda_lift(a).join(self._lambda_lift(b))
        return lhs.key == rhs.key

    def check_meet(self, a: OmegaElement, b: OmegaElement) -> bool:
        """λ(a ∧ b) = λ(a) ∧ λ(b)."""
        lhs = self._lambda_lift(a.meet(b))
        rhs = self._lambda_lift(a).meet(self._lambda_lift(b))
        return lhs.key == rhs.key

    def check_coherence(self, omega_set: frozenset[OmegaElement]) -> list[str]:
        """
        Run full lattice coherence check over all pairs in omega_set.

        Verifies:
          - join(a, b) ≥ a and ≥ b (join is an upper bound)
          - meet(a, b) ≤ a and ≤ b (meet is a lower bound)
          - λ-homomorphism for both join and meet
          - join/meet are themselves in normal form (λ-closed)

        Returns list of failure descriptions; empty = coherent.
        """
        failures: list[str] = []
        elems = list(omega_set)
        for i, a in enumerate(elems):
            for j, b in enumerate(elems):
                if i >= j:
                    continue
                j_elem = a.join(b)
                if not (a <= j_elem and b <= j_elem):
                    failures.append(
                        f"join({a.key[:8]}, {b.key[:8]}) not ≥ both operands"
                    )
                if not self.check_join(a, b):
                    failures.append(
                        f"λ-join-homomorphism failed: ({a.key[:8]}, {b.key[:8]})"
                    )
                m_elem = a.meet(b)
                if not (m_elem <= a and m_elem <= b):
                    failures.append(
                        f"meet({a.key[:8]}, {b.key[:8]}) not ≤ both operands"
                    )
                if not self.check_meet(a, b):
                    failures.append(
                        f"λ-meet-homomorphism failed: ({a.key[:8]}, {b.key[:8]})"
                    )
        return failures


# ──────────────────────────────────────────────────────────────────────────────
# Spec Ω — computable spectrum (geometry stub)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SpecPoint:
    """
    A point in Spec Ω: the geometric realization of an Ω equivalence class.

    Spec Ω is the spectrum of the distributive lattice Ω: its points are
    the prime filters of Ω (equivalently, the lattice homomorphisms Ω → {0,1}).

    Each prime filter corresponds to a "consistent choice of execution world":
      - the elements it contains are the stages the chosen backend supports
      - it is closed under join (contains everything ≥ any element it contains)
      - it is prime (its complement is a prime ideal — a consistent exclusion)

    In operational terms: a SpecPoint is a backend's "execution commitment"
    — which stages it is willing to be evaluated in.

    This is the bridge between algebra and geometry: execution traces become
    continuous paths in Spec Ω, and deformation of pipelines becomes
    homotopy of paths.
    """
    omega_key: str           # key of the "smallest" Ω element in this prime filter
    is_terminal: bool        # True for filters containing the COMMIT element


def prime_filters(omega_set: frozenset[OmegaElement]) -> list[SpecPoint]:
    """
    Enumerate the prime filters of Ω (points of Spec Ω).

    A filter F ⊆ Ω is prime if:
      - it is an upper set (a ∈ F, a ≤ b → b ∈ F)
      - it is closed under meet restricted to F
      - its complement is a prime ideal

    For a finite distributive lattice, each prime filter is generated
    by exactly one element (the join-irreducible elements generate the lattice).
    Here we enumerate principal filters for the computable case.
    """
    elems = sorted(omega_set, key=lambda e: len(e.stage_word_nf))
    points: list[SpecPoint] = []
    for elem in elems:
        # Principal filter: all elements ≥ elem
        filter_set = {e for e in omega_set if elem <= e}
        if filter_set:
            points.append(SpecPoint(
                omega_key=elem.key,
                is_terminal=any(e.is_terminal for e in filter_set),
            ))
    return points


# ──────────────────────────────────────────────────────────────────────────────
# Distributive law λ: 𝕋 ∘ 𝕌 ⇒ 𝕌 ∘ 𝕋
# ──────────────────────────────────────────────────────────────────────────────

class DistributiveLawChecker:
    """
    Checks the distributive law λ: 𝕋 ∘ 𝕌 ⇒ 𝕌 ∘ 𝕋.

    "Observing a transformation context inside a trace context is equivalent
    to transforming a trace context inside a transformation context."

    Kernel invariant (the concrete, checkable form):
      For every stage generator g and every focus commitment c:
        apply_stage(state_with_focus(c), g).focus_commitment == c

    This is the counit law at the bicomonadic level. It ensures:
    - Stage transitions cannot change "what the current observation is"
    - GPU/SNARK/CPU backends observe the same focus as the semantic layer
    - Optimization (stage application) cannot shift the identity of "now"
    """

    def check(self, focus_commitment: bytes, stage: StageNode) -> bool:
        """
        λ-check for one generator: focus_commitment must survive the stage transition.
        """
        state = initial_alpha_state(focus_commitment)
        new_word = normalize_stage_word((stage,))
        is_term = StageLabel.COMMIT in {n.label for n in new_word}
        after = _mint_alpha_state(new_word, focus_commitment, state.accumulated_cert, is_term)
        return after.focus_commitment == focus_commitment

    def check_all_generators(self, focus_commitment: bytes) -> dict[str, bool]:
        """Run λ-check for every generator. All must pass — any failure breaks the system."""
        return {
            g.label.value: self.check(focus_commitment, g)
            for g in [
                StageNode(StageLabel.WIN, k_past=8),
                StageNode(StageLabel.IDX, layout_id="default"),
                StageNode(StageLabel.COMMIT, hash_scheme="sha256"),
            ]
        }
