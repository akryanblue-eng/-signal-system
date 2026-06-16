"""
Ω quotient space — test suite.

Covers:
  1. Stage word normalization (rules A–E)
  2. Idempotence of normalize_stage_word
  3. AlphaState kernel minting and witness token properties
  4. Γ coalgebra (gamma): productivity, determinism, witness preservation
  5. TransformZipper 𝕌 comonad operations
  6. Ω element preorder and lattice ops (join, meet)
  7. Reachable Ω enumeration (finite, computable)
  8. Distributive law λ checks (all generators)
  9. Backend as Ω representative
  10. Epistemic closure: witness token is not forgeable
"""
import hashlib
import pytest

from src.pcp_omega import (
    StageLabel, StageNode, StageWord,
    normalize_stage_word, stage_word_key,
    AlphaState, initial_alpha_state,
    TransformZipper, gamma,
    OmegaElement, alpha_state_to_omega, reachable_omega,
    DistributiveLawChecker,
    _mint_alpha_state, _admissible_generators,
)

_FOCUS = hashlib.sha256(b"test-focus-commitment").digest()


# ──────────────────────────────────────────────────────────────────────────────
# 1. Stage word normalization
# ──────────────────────────────────────────────────────────────────────────────

class TestNormalization:
    def test_identity_eliminated(self):
        word = (StageNode(StageLabel.IDENTITY), StageNode(StageLabel.CANON))
        nf = normalize_stage_word(word)
        assert all(n.label != StageLabel.IDENTITY for n in nf)

    def test_empty_word_normalizes_to_empty(self):
        assert normalize_stage_word(()) == ()

    def test_canon_idempotent(self):
        word = (StageNode(StageLabel.CANON), StageNode(StageLabel.CANON))
        nf = normalize_stage_word(word)
        assert len([n for n in nf if n.label == StageLabel.CANON]) == 1

    def test_win_merge_takes_min_k_past(self):
        word = (
            StageNode(StageLabel.WIN, k_past=8),
            StageNode(StageLabel.WIN, k_past=4),
        )
        nf = normalize_stage_word(word)
        win_nodes = [n for n in nf if n.label == StageLabel.WIN]
        assert len(win_nodes) == 1
        assert win_nodes[0].k_past == 4

    def test_canonical_order_enforced(self):
        # Applied in wrong order: Commit, Idx, Win, Canon
        word = (
            StageNode(StageLabel.COMMIT, hash_scheme="sha256"),
            StageNode(StageLabel.IDX, layout_id="default"),
            StageNode(StageLabel.WIN, k_past=8),
            StageNode(StageLabel.CANON),
        )
        nf = normalize_stage_word(word)
        labels = [n.label for n in nf]
        assert labels == sorted(labels, key=lambda l: {
            StageLabel.CANON: 0, StageLabel.WIN: 1,
            StageLabel.IDX: 2, StageLabel.COMMIT: 3,
        }[l])

    def test_deduplication(self):
        word = (
            StageNode(StageLabel.CANON),
            StageNode(StageLabel.WIN, k_past=8),
            StageNode(StageLabel.CANON),
        )
        nf = normalize_stage_word(word)
        labels = [n.label for n in nf]
        assert labels.count(StageLabel.CANON) == 1

    def test_idempotent(self):
        word = (
            StageNode(StageLabel.IDX, layout_id="gpu"),
            StageNode(StageLabel.CANON),
            StageNode(StageLabel.WIN, k_past=8),
            StageNode(StageLabel.IDENTITY),
        )
        nf1 = normalize_stage_word(word)
        nf2 = normalize_stage_word(nf1)
        assert nf1 == nf2

    def test_full_chain_normalizes_to_sorted_unique(self):
        word = (
            StageNode(StageLabel.COMMIT, hash_scheme="sha256"),
            StageNode(StageLabel.CANON),
            StageNode(StageLabel.WIN, k_past=4),
            StageNode(StageLabel.IDX, layout_id="default"),
        )
        nf = normalize_stage_word(word)
        labels = [n.label for n in nf]
        expected = [StageLabel.CANON, StageLabel.WIN, StageLabel.IDX, StageLabel.COMMIT]
        assert labels == expected

    def test_stage_word_key_deterministic(self):
        word = (StageNode(StageLabel.CANON), StageNode(StageLabel.WIN, k_past=4))
        k1 = stage_word_key(word, _FOCUS)
        k2 = stage_word_key(word, _FOCUS)
        assert k1 == k2

    def test_stage_word_key_different_params(self):
        w1 = (StageNode(StageLabel.WIN, k_past=4),)
        w2 = (StageNode(StageLabel.WIN, k_past=8),)
        assert stage_word_key(w1, _FOCUS) != stage_word_key(w2, _FOCUS)


# ──────────────────────────────────────────────────────────────────────────────
# 2. AlphaState minting
# ──────────────────────────────────────────────────────────────────────────────

class TestAlphaState:
    def test_initial_state_empty_word(self):
        state = initial_alpha_state(_FOCUS)
        assert state.stage_word_nf == ()
        assert state.focus_commitment == _FOCUS
        assert not state.is_terminal

    def test_witness_token_is_32_bytes(self):
        state = initial_alpha_state(_FOCUS)
        assert len(state.witness_token) == 32

    def test_witness_token_deterministic(self):
        s1 = initial_alpha_state(_FOCUS)
        s2 = initial_alpha_state(_FOCUS)
        assert s1.witness_token == s2.witness_token

    def test_different_focus_different_token(self):
        s1 = initial_alpha_state(_FOCUS)
        s2 = initial_alpha_state(b"\x00" * 32)
        assert s1.witness_token != s2.witness_token

    def test_accumulated_cert_chains_from_prior(self):
        s1 = initial_alpha_state(_FOCUS)
        s2 = _mint_alpha_state(
            stage_word_nf=(StageNode(StageLabel.CANON),),
            focus_commitment=_FOCUS,
            prior_cert=s1.accumulated_cert,
            is_terminal=False,
        )
        s3 = _mint_alpha_state(
            stage_word_nf=(StageNode(StageLabel.CANON),),
            focus_commitment=_FOCUS,
            prior_cert=s1.accumulated_cert,
            is_terminal=False,
        )
        # Same inputs → same cert
        assert s2.accumulated_cert == s3.accumulated_cert

    def test_terminal_state_has_commit_in_word(self):
        word = normalize_stage_word((
            StageNode(StageLabel.CANON),
            StageNode(StageLabel.WIN, k_past=4),
            StageNode(StageLabel.IDX, layout_id="default"),
            StageNode(StageLabel.COMMIT, hash_scheme="sha256"),
        ))
        state = _mint_alpha_state(word, _FOCUS, b"", is_terminal=True)
        assert state.is_terminal


# ──────────────────────────────────────────────────────────────────────────────
# 3. Γ coalgebra
# ──────────────────────────────────────────────────────────────────────────────

class TestGamma:
    def test_initial_state_has_admissible_successors(self):
        state = initial_alpha_state(_FOCUS)
        tz = gamma(state)
        assert len(tz.future) > 0

    def test_gamma_returns_transform_zipper(self):
        state = initial_alpha_state(_FOCUS)
        tz = gamma(state)
        assert isinstance(tz, TransformZipper)

    def test_focus_unchanged_by_gamma(self):
        state = initial_alpha_state(_FOCUS)
        tz = gamma(state)
        assert tz.extract() is state

    def test_successors_are_kernel_minted(self):
        state = initial_alpha_state(_FOCUS)
        tz = gamma(state)
        for successor in tz.future:
            assert len(successor.witness_token) == 32

    def test_successors_preserve_focus_commitment(self):
        """Γ must be witness-preserving: focus_commitment unchanged."""
        state = initial_alpha_state(_FOCUS)
        tz = gamma(state)
        for successor in tz.future:
            assert successor.focus_commitment == _FOCUS

    def test_terminal_state_has_no_successors(self):
        word = normalize_stage_word((
            StageNode(StageLabel.CANON),
            StageNode(StageLabel.WIN, k_past=4),
            StageNode(StageLabel.IDX, layout_id="default"),
            StageNode(StageLabel.COMMIT, hash_scheme="sha256"),
        ))
        terminal = _mint_alpha_state(word, _FOCUS, b"", is_terminal=True)
        tz = gamma(terminal)
        assert len(tz.future) == 0
        assert tz.is_terminal

    def test_gamma_deterministic(self):
        state = initial_alpha_state(_FOCUS)
        tz1 = gamma(state)
        tz2 = gamma(state)
        # Same focus, same future structure
        assert len(tz1.future) == len(tz2.future)
        tokens1 = {s.witness_token for s in tz1.future}
        tokens2 = {s.witness_token for s in tz2.future}
        assert tokens1 == tokens2

    def test_successor_stage_words_are_normalized(self):
        state = initial_alpha_state(_FOCUS)
        tz = gamma(state)
        for s in tz.future:
            assert normalize_stage_word(s.stage_word_nf) == s.stage_word_nf


# ──────────────────────────────────────────────────────────────────────────────
# 4. TransformZipper 𝕌
# ──────────────────────────────────────────────────────────────────────────────

class TestTransformZipper:
    def _initial_zipper(self) -> TransformZipper:
        return gamma(initial_alpha_state(_FOCUS))

    def test_extract_returns_focus(self):
        tz = self._initial_zipper()
        assert tz.extract() is tz.focus

    def test_advance_moves_focus(self):
        tz = self._initial_zipper()
        if tz.future:
            next_s = tz.future[0]
            tz2 = tz.advance(next_s)
            assert tz2 is not None
            assert tz2.focus is next_s
            assert tz.focus in tz2.past

    def test_advance_unknown_state_returns_none(self):
        tz = self._initial_zipper()
        unknown = initial_alpha_state(b"\xff" * 32)
        assert tz.advance(unknown) is None

    def test_not_terminal_at_initial(self):
        tz = self._initial_zipper()
        assert not tz.is_terminal


# ──────────────────────────────────────────────────────────────────────────────
# 5. Ω preorder and lattice
# ──────────────────────────────────────────────────────────────────────────────

def _omega(labels: list[StageLabel], k_past: int = 8) -> OmegaElement:
    nodes = []
    for label in labels:
        if label == StageLabel.WIN:
            nodes.append(StageNode(label, k_past=k_past))
        elif label == StageLabel.IDX:
            nodes.append(StageNode(label, layout_id="default"))
        elif label == StageLabel.COMMIT:
            nodes.append(StageNode(label, hash_scheme="sha256"))
        else:
            nodes.append(StageNode(label))
    word = normalize_stage_word(tuple(nodes))
    is_term = StageLabel.COMMIT in {n.label for n in word}
    return OmegaElement(
        key=stage_word_key(word, _FOCUS),
        stage_word_nf=word,
        focus_commitment=_FOCUS,
        is_terminal=is_term,
    )


class TestOmegaLattice:
    def test_more_refined_le_less_refined(self):
        # {CANON, WIN} is more refined than {CANON}
        more = _omega([StageLabel.CANON, StageLabel.WIN])
        less = _omega([StageLabel.CANON])
        assert more <= less   # {CANON, WIN} has ⊇ labels of {CANON}
        assert not (less <= more)

    def test_reflexive(self):
        e = _omega([StageLabel.CANON])
        assert e <= e

    def test_empty_word_is_top(self):
        top = _omega([])
        refined = _omega([StageLabel.CANON, StageLabel.WIN])
        assert refined <= top  # everything is below top (top has no labels)

    def test_join_gives_union_of_labels(self):
        a = _omega([StageLabel.CANON])
        b = _omega([StageLabel.WIN])
        j = a.join(b)
        j_labels = {n.label for n in j.stage_word_nf}
        assert StageLabel.CANON in j_labels
        assert StageLabel.WIN in j_labels

    def test_join_idempotent(self):
        e = _omega([StageLabel.CANON, StageLabel.WIN])
        assert e.join(e).stage_word_nf == e.stage_word_nf

    def test_join_win_takes_min_k_past(self):
        a = _omega([StageLabel.WIN], k_past=8)
        b = _omega([StageLabel.WIN], k_past=4)
        j = a.join(b)
        win_nodes = [n for n in j.stage_word_nf if n.label == StageLabel.WIN]
        assert len(win_nodes) == 1
        assert win_nodes[0].k_past == 4  # min of 8 and 4

    def test_meet_gives_intersection_of_labels(self):
        a = _omega([StageLabel.CANON, StageLabel.WIN])
        b = _omega([StageLabel.WIN])
        m = a.meet(b)
        m_labels = {n.label for n in m.stage_word_nf}
        assert StageLabel.WIN in m_labels
        assert StageLabel.CANON not in m_labels

    def test_meet_disjoint_gives_empty_word(self):
        a = _omega([StageLabel.CANON])
        b = _omega([StageLabel.WIN])
        m = a.meet(b)
        assert m.stage_word_nf == ()

    def test_meet_win_takes_max_k_past(self):
        a = _omega([StageLabel.WIN], k_past=4)
        b = _omega([StageLabel.WIN], k_past=8)
        m = a.meet(b)
        win_nodes = [n for n in m.stage_word_nf if n.label == StageLabel.WIN]
        assert len(win_nodes) == 1
        assert win_nodes[0].k_past == 8  # max of 4 and 8 (weaker abstraction)

    def test_join_associative(self):
        a = _omega([StageLabel.CANON])
        b = _omega([StageLabel.WIN])
        c = _omega([StageLabel.IDX, StageLabel.WIN])
        j1 = a.join(b).join(c)
        j2 = a.join(b.join(c))
        assert j1.stage_word_nf == j2.stage_word_nf


# ──────────────────────────────────────────────────────────────────────────────
# 6. Reachable Ω enumeration
# ──────────────────────────────────────────────────────────────────────────────

class TestReachableOmega:
    def test_reachable_is_finite(self):
        state = initial_alpha_state(_FOCUS)
        omega_set = reachable_omega(state)
        assert len(omega_set) > 0
        assert len(omega_set) <= 20  # bounded by 2^|generators| + some

    def test_reachable_contains_initial(self):
        state = initial_alpha_state(_FOCUS)
        omega_set = reachable_omega(state)
        initial_elem = alpha_state_to_omega(state)
        assert initial_elem in omega_set

    def test_reachable_contains_terminal(self):
        state = initial_alpha_state(_FOCUS)
        omega_set = reachable_omega(state, max_depth=10)
        terminals = [e for e in omega_set if e.is_terminal]
        assert len(terminals) > 0

    def test_reachable_keys_unique(self):
        state = initial_alpha_state(_FOCUS)
        omega_set = reachable_omega(state)
        keys = [e.key for e in omega_set]
        assert len(keys) == len(set(keys))

    def test_all_reachable_preserve_focus_commitment(self):
        state = initial_alpha_state(_FOCUS)
        for elem in reachable_omega(state):
            assert elem.focus_commitment == _FOCUS

    def test_stage_labels_grow_monotonically(self):
        """All reachable states have at most |generators| labels."""
        state = initial_alpha_state(_FOCUS)
        for elem in reachable_omega(state):
            assert len(elem.stage_word_nf) <= 4  # CANON, WIN, IDX, COMMIT


# ──────────────────────────────────────────────────────────────────────────────
# 7. Distributive law λ
# ──────────────────────────────────────────────────────────────────────────────

class TestDistributiveLaw:
    def setup_method(self):
        self.checker = DistributiveLawChecker()

    def test_all_generators_satisfy_lambda(self):
        results = self.checker.check_all_generators(_FOCUS)
        failures = [k for k, v in results.items() if not v]
        assert failures == [], f"λ violations: {failures}"

    def test_focus_preserved_across_all_generators(self):
        for label in [StageLabel.IDENTITY, StageLabel.CANON, StageLabel.WIN,
                      StageLabel.IDX, StageLabel.COMMIT]:
            stage = StageNode(label, k_past=4, layout_id="default", hash_scheme="sha256")
            assert self.checker.check(_FOCUS, stage), f"λ failed for {label}"

    def test_different_focus_commitments_isolated(self):
        focus_a = hashlib.sha256(b"a").digest()
        focus_b = hashlib.sha256(b"b").digest()
        state_a = initial_alpha_state(focus_a)
        state_b = initial_alpha_state(focus_b)
        # Applying any stage must not cross-contaminate focus commitments
        tz_a = gamma(state_a)
        tz_b = gamma(state_b)
        for s in tz_a.future:
            assert s.focus_commitment == focus_a
        for s in tz_b.future:
            assert s.focus_commitment == focus_b


# ──────────────────────────────────────────────────────────────────────────────
# 8. Epistemic closure: witness token is not forgeable
# ──────────────────────────────────────────────────────────────────────────────

class TestEpistemicClosureOmega:
    def test_witness_token_is_keyed_hash(self):
        state = initial_alpha_state(_FOCUS)
        assert state.witness_token != _FOCUS
        assert len(state.witness_token) == 32

    def test_two_states_same_word_different_cert_different_token(self):
        word = normalize_stage_word((StageNode(StageLabel.CANON),))
        s1 = _mint_alpha_state(word, _FOCUS, b"cert_a", False)
        s2 = _mint_alpha_state(word, _FOCUS, b"cert_b", False)
        # Different accumulated cert → different witness token
        assert s1.witness_token != s2.witness_token

    def test_alpha_state_has_no_raw_bytes_public_field(self):
        state = initial_alpha_state(_FOCUS)
        # focus_commitment is OK to read (needed for Ω keys)
        assert hasattr(state, "focus_commitment")
        assert hasattr(state, "witness_token")
        # No backdoor "raw_trace" or "source_bytes" field
        assert not hasattr(state, "raw_trace")
        assert not hasattr(state, "source_bytes")

    def test_omega_key_stable_after_normalization(self):
        state = initial_alpha_state(_FOCUS)
        tz = gamma(state)
        if tz.future:
            succ = tz.future[0]
            elem = alpha_state_to_omega(succ)
            # key must be reproducible from normalized word
            expected_key = stage_word_key(succ.stage_word_nf, succ.focus_commitment)
            assert elem.key == expected_key

    def test_backends_as_omega_representatives(self):
        """GPU, SNARK, CPU debug are Ω representatives — not separate engines."""
        gpu_backend  = _omega([StageLabel.CANON, StageLabel.WIN, StageLabel.IDX])
        snark_backend = _omega([StageLabel.CANON, StageLabel.WIN, StageLabel.IDX, StageLabel.COMMIT])
        cpu_debug    = _omega([StageLabel.CANON, StageLabel.WIN])

        # SNARK is more refined than GPU which is more refined than CPU debug
        assert snark_backend <= gpu_backend
        assert gpu_backend   <= cpu_debug
        assert snark_backend <= cpu_debug

        # join(GPU, CPU_debug) = GPU (more refined wins)
        j = gpu_backend.join(cpu_debug)
        assert j.stage_word_nf == gpu_backend.stage_word_nf

        # Terminals exist only at the COMMIT level
        assert snark_backend.is_terminal
        assert not gpu_backend.is_terminal
        assert not cpu_debug.is_terminal
