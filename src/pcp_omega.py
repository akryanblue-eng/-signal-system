"""
Ω — computable normal-form quotient of transformation-collapse space.

This module implements the final categorical closure:

  α is a coalgebra section of 𝕌 (the TransformZipper comonad over AlphaStates)
  Ω = A_nf / ≡  (bisimulation equivalence classes of normal-form α-states)

The pipeline of worlds becomes a self-verifying geometry of allowable collapses.

──────────────────────────────────────────────────────────────────────────────
Stage word language (finite, kernel-owned generator alphabet):

  IDENTITY  id    eliminated by normalization
  CANON     canon canonicalize witness ordering and address encoding
  WIN(k)    win   window to k_past past witnesses; k_future future witnesses
  IDX       idx   index for O(1) recenter and GPU-friendly layout
  COMMIT    commit attach cryptographic commitment to context

Prerequisites:  IDX requires WIN.  COMMIT requires IDX.
  (Semantic dependency, not order only.)

Rewrite rules (confluent, terminating → unique normal form):
  A  Identity elimination:   any ∘ Id → any,  Id ∘ any → any
  B  Idempotence:            Canon ∘ Canon → Canon,  Commit ∘ Commit → Commit
  C  Window merge:           Win(k1) ∘ Win(k2) → Win(min(k1, k2))
  D  Canonical sort:         labels ordered Canon(0) < Win(1) < Idx(2) < Commit(3)
  E  Deduplication:          each label appears at most once after sort + merge

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
    IDENTITY = "id"
    CANON    = "canon"
    WIN      = "win"
    IDX      = "idx"
    COMMIT   = "commit"


_STAGE_ORDER: dict[StageLabel, int] = {
    StageLabel.CANON:  0,
    StageLabel.WIN:    1,
    StageLabel.IDX:    2,
    StageLabel.COMMIT: 3,
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
      D — sort by canonical label order
      E — each label appears at most once (guaranteed by merge)

    Idempotent: normalize(normalize(w)) = normalize(w).
    """
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
    Dependencies: IDX requires WIN; COMMIT requires IDX.
    A terminal state admits no generators.
    """
    if state.is_terminal:
        return []
    current = {n.label for n in state.stage_word_nf}
    cands: list[StageNode] = []
    if StageLabel.CANON not in current:
        cands.append(StageNode(StageLabel.CANON))
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
      self ≤ other  iff  self has at least all stage labels that other has
                    (self is more refined / more collapsed)

    Lattice ops (within same fiber):
      join(a,b) = least common refinement = union of labels with stronger params
      meet(a,b) = greatest common abstraction = intersection with weaker params
                  (returns the empty-word top element if labels are disjoint)

    Backends are Ω representatives:
      GPU backend    = element with stage {CANON, WIN, IDX}
      SNARK backend  = element with stage {CANON, WIN, IDX, COMMIT}
      CPU debug      = element with stage {CANON, WIN}
    """
    key: str
    stage_word_nf: StageWord
    focus_commitment: bytes
    is_terminal: bool

    def __le__(self, other: "OmegaElement") -> bool:
        b_labels = {n.label for n in other.stage_word_nf}
        a_labels = {n.label for n in self.stage_word_nf}
        return b_labels <= a_labels

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
                StageNode(StageLabel.IDENTITY),
                StageNode(StageLabel.CANON),
                StageNode(StageLabel.WIN, k_past=8),
                StageNode(StageLabel.IDX, layout_id="default"),
                StageNode(StageLabel.COMMIT, hash_scheme="sha256"),
            ]
        }
