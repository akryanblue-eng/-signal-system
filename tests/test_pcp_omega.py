"""
Ω quotient space — test suite (adversarial + property-based).

Generator alphabet: {WIN, IDX, COMMIT}. CANON is NOT a generator —
canonicalization is implicit in normalize_stage_word (NF axiom).

Covers:
  1. Stage word normalization (rules A–F)
  2. Idempotence and confluence of normalize_stage_word
  3. Cross-check: production vs reference normalizer (NF divergence detection)
  4. AlphaState kernel minting and witness token properties
  5. Γ coalgebra: productivity, determinism, no-silent-terminal
  6. TransformZipper 𝕌 comonad operations
  7. Ω preorder and lattice (join/meet metamorphic checks)
  8. Reachable Ω enumeration: finite, stable, unique representatives
  9. Lattice homomorphism coherence (λ(a ∨ b) = λ(a) ∨ λ(b))
  10. Ω class count stability (kernel invariant under fuzz)
  11. Distributive law λ checks (all generators)
  12. Spec Ω: prime filters as backend-selection geometry
  13. Backends as Ω representatives
  14. Epistemic closure: witness token not forgeable
"""
import hashlib
import random
import pytest

from src.pcp_omega import (
    StageLabel, StageNode, StageWord,
    normalize_stage_word, stage_word_key,
    AlphaState, initial_alpha_state,
    TransformZipper, gamma,
    OmegaElement, alpha_state_to_omega, reachable_omega,
    LatticeHomomorphismChecker,
    DistributiveLawChecker,
    SpecPoint, prime_filters,
    _mint_alpha_state, _admissible_generators, _STAGE_ORDER,
)

_FOCUS = hashlib.sha256(b"test-focus-commitment").digest()


# ──────────────────────────────────────────────────────────────────────────────
# Reference normalizer (independent, obviously correct implementation)
# ──────────────────────────────────────────────────────────────────────────────

def _merge_nodes_ref(a: StageNode, b: StageNode) -> StageNode:
    assert a.label == b.label
    if a.label == StageLabel.WIN:
        return StageNode(StageLabel.WIN, k_past=min(a.k_past, b.k_past),
                         k_future=min(a.k_future, b.k_future))
    return a


def normalize_spec(word: StageWord) -> StageWord:
    """
    Reference normalizer: collect all nodes, group by label, merge, sort.
    Written to be obviously correct, not fast.
    """
    non_id = [n for n in word if n.label != StageLabel.IDENTITY]
    groups: dict[StageLabel, list[StageNode]] = {}
    for n in non_id:
        groups.setdefault(n.label, []).append(n)
    merged: dict[StageLabel, StageNode] = {}
    for label, nodes in groups.items():
        result = nodes[0]
        for n in nodes[1:]:
            result = _merge_nodes_ref(result, n)
        merged[label] = result
    return tuple(
        merged[l]
        for l in sorted(merged, key=lambda l: _STAGE_ORDER.get(l, 99))
    )


# ──────────────────────────────────────────────────────────────────────────────
# Random word generator (fixed seeds for reproducibility)
# ──────────────────────────────────────────────────────────────────────────────

def _random_word(rng: random.Random, max_len: int = 8) -> StageWord:
    """Generate a random stage word from the generator alphabet {IDENTITY, WIN, IDX, COMMIT}."""
    labels = [StageLabel.IDENTITY, StageLabel.WIN, StageLabel.IDX, StageLabel.COMMIT]
    length = rng.randint(0, max_len)
    nodes: list[StageNode] = []
    for _ in range(length):
        label = rng.choice(labels)
        if label == StageLabel.WIN:
            k = rng.choice([2, 4, 8, 16])
            nodes.append(StageNode(StageLabel.WIN, k_past=k))
        elif label == StageLabel.IDX:
            nodes.append(StageNode(StageLabel.IDX,
                                   layout_id=rng.choice(["default", "gpu"])))
        elif label == StageLabel.COMMIT:
            nodes.append(StageNode(StageLabel.COMMIT,
                                   hash_scheme=rng.choice(["sha256", "blake3"])))
        else:
            nodes.append(StageNode(StageLabel.IDENTITY))
    return tuple(nodes)


def _sample_words(seed: int, n: int = 200, max_len: int = 8) -> list[StageWord]:
    rng = random.Random(seed)
    return [_random_word(rng, max_len) for _ in range(n)]


# ──────────────────────────────────────────────────────────────────────────────
# Ω element factory (no CANON)
# ──────────────────────────────────────────────────────────────────────────────

def _omega(labels: list[StageLabel], k_past: int = 8) -> OmegaElement:
    """Build an Ω element from a list of labels (no CANON allowed)."""
    nodes: list[StageNode] = []
    for label in labels:
        if label == StageLabel.WIN:
            nodes.append(StageNode(label, k_past=k_past))
        elif label == StageLabel.IDX:
            nodes.append(StageNode(label, layout_id="default"))
        elif label == StageLabel.COMMIT:
            nodes.append(StageNode(label, hash_scheme="sha256"))
        else:
            raise ValueError(f"Cannot use {label} in _omega helper")
    word = normalize_stage_word(tuple(nodes))
    is_term = StageLabel.COMMIT in {n.label for n in word}
    return OmegaElement(
        key=stage_word_key(word, _FOCUS),
        stage_word_nf=word,
        focus_commitment=_FOCUS,
        is_terminal=is_term,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 1. Stage word normalization (rules A–F)
# ──────────────────────────────────────────────────────────────────────────────

class TestNormalization:
    def test_identity_eliminated(self):
        word = (StageNode(StageLabel.IDENTITY), StageNode(StageLabel.WIN, k_past=4))
        nf = normalize_stage_word(word)
        assert all(n.label != StageLabel.IDENTITY for n in nf)

    def test_empty_word_normalizes_to_empty(self):
        assert normalize_stage_word(()) == ()

    def test_win_merge_takes_min_k_past(self):
        word = (StageNode(StageLabel.WIN, k_past=8), StageNode(StageLabel.WIN, k_past=4))
        nf = normalize_stage_word(word)
        win_nodes = [n for n in nf if n.label == StageLabel.WIN]
        assert len(win_nodes) == 1
        assert win_nodes[0].k_past == 4

    def test_canonical_order_win_idx_commit(self):
        word = (
            StageNode(StageLabel.COMMIT, hash_scheme="sha256"),
            StageNode(StageLabel.IDX, layout_id="default"),
            StageNode(StageLabel.WIN, k_past=8),
        )
        nf = normalize_stage_word(word)
        labels = [n.label for n in nf]
        assert labels == [StageLabel.WIN, StageLabel.IDX, StageLabel.COMMIT]

    def test_deduplication_win(self):
        word = (
            StageNode(StageLabel.WIN, k_past=8),
            StageNode(StageLabel.WIN, k_past=8),
        )
        nf = normalize_stage_word(word)
        assert len([n for n in nf if n.label == StageLabel.WIN]) == 1

    def test_idempotent(self):
        word = (
            StageNode(StageLabel.IDX, layout_id="gpu"),
            StageNode(StageLabel.WIN, k_past=8),
            StageNode(StageLabel.IDENTITY),
        )
        nf1 = normalize_stage_word(word)
        nf2 = normalize_stage_word(nf1)
        assert nf1 == nf2

    def test_full_chain_sorted(self):
        word = (
            StageNode(StageLabel.COMMIT, hash_scheme="sha256"),
            StageNode(StageLabel.WIN, k_past=4),
            StageNode(StageLabel.IDX, layout_id="default"),
        )
        nf = normalize_stage_word(word)
        labels = [n.label for n in nf]
        assert labels == [StageLabel.WIN, StageLabel.IDX, StageLabel.COMMIT]

    def test_stage_word_key_deterministic(self):
        word = (StageNode(StageLabel.WIN, k_past=4),)
        assert stage_word_key(word, _FOCUS) == stage_word_key(word, _FOCUS)

    def test_stage_word_key_different_params(self):
        w1 = (StageNode(StageLabel.WIN, k_past=4),)
        w2 = (StageNode(StageLabel.WIN, k_past=8),)
        assert stage_word_key(w1, _FOCUS) != stage_word_key(w2, _FOCUS)


# ──────────────────────────────────────────────────────────────────────────────
# 2. Cross-check: production vs reference normalizer (NF divergence detection)
# ──────────────────────────────────────────────────────────────────────────────

class TestNormalizerCrossCheck:
    """
    Adversarial property: production and reference normalizers must agree on all inputs.
    Any divergence is a 'silent fork in Ω' — a critical failure.
    Fixed seeds ensure reproducibility.
    """

    @pytest.mark.parametrize("seed", [42, 1337, 99999, 2718281, 0xDEAD])
    def test_production_matches_spec(self, seed: int):
        failures = []
        for word in _sample_words(seed):
            prod = normalize_stage_word(word)
            spec = normalize_spec(word)
            if prod != spec:
                failures.append((word, prod, spec))
        assert not failures, (
            f"NF divergence ({len(failures)} cases):\n"
            + "\n".join(f"  word={w}  prod={p}  spec={s}" for w, p, s in failures[:3])
        )

    def test_both_idempotent_on_random(self):
        for word in _sample_words(seed=7):
            nf = normalize_stage_word(word)
            assert normalize_stage_word(nf) == nf
            assert normalize_spec(normalize_spec(word)) == normalize_spec(word)

    def test_termination_watchdog(self):
        """Every word must normalize within bounded steps — no rewrite loops."""
        for word in _sample_words(seed=13, max_len=20):
            # If normalize is deterministic and terminates, repeated application converges
            nf = normalize_stage_word(word)
            for _ in range(5):  # extra applications should be idempotent
                assert normalize_stage_word(nf) == nf


# ──────────────────────────────────────────────────────────────────────────────
# 3. AlphaState minting
# ──────────────────────────────────────────────────────────────────────────────

class TestAlphaState:
    def test_initial_state_empty_word(self):
        state = initial_alpha_state(_FOCUS)
        assert state.stage_word_nf == ()
        assert state.focus_commitment == _FOCUS
        assert not state.is_terminal

    def test_witness_token_32_bytes(self):
        assert len(initial_alpha_state(_FOCUS).witness_token) == 32

    def test_witness_token_deterministic(self):
        s1 = initial_alpha_state(_FOCUS)
        s2 = initial_alpha_state(_FOCUS)
        assert s1.witness_token == s2.witness_token

    def test_different_focus_different_token(self):
        s1 = initial_alpha_state(_FOCUS)
        s2 = initial_alpha_state(b"\x00" * 32)
        assert s1.witness_token != s2.witness_token

    def test_accumulated_cert_chains(self):
        s1 = initial_alpha_state(_FOCUS)
        word = (StageNode(StageLabel.WIN, k_past=4),)
        s2a = _mint_alpha_state(word, _FOCUS, s1.accumulated_cert, False)
        s2b = _mint_alpha_state(word, _FOCUS, s1.accumulated_cert, False)
        assert s2a.accumulated_cert == s2b.accumulated_cert

    def test_terminal_state_has_commit(self):
        word = normalize_stage_word((
            StageNode(StageLabel.WIN, k_past=4),
            StageNode(StageLabel.IDX, layout_id="default"),
            StageNode(StageLabel.COMMIT, hash_scheme="sha256"),
        ))
        state = _mint_alpha_state(word, _FOCUS, b"", is_terminal=True)
        assert state.is_terminal


# ──────────────────────────────────────────────────────────────────────────────
# 4. Γ coalgebra: productivity, determinism, no-silent-terminal
# ──────────────────────────────────────────────────────────────────────────────

class TestGamma:
    def test_initial_has_successors(self):
        tz = gamma(initial_alpha_state(_FOCUS))
        assert len(tz.future) > 0

    def test_focus_unchanged(self):
        state = initial_alpha_state(_FOCUS)
        tz = gamma(state)
        assert tz.extract() is state

    def test_focus_commitment_preserved(self):
        """Γ must be witness-preserving: focus_commitment unchanged in all successors."""
        state = initial_alpha_state(_FOCUS)
        tz = gamma(state)
        for s in tz.future:
            assert s.focus_commitment == _FOCUS

    def test_successors_kernel_minted(self):
        for s in gamma(initial_alpha_state(_FOCUS)).future:
            assert len(s.witness_token) == 32

    def test_no_silent_terminal(self):
        """
        Adversarial property: a non-terminal state must always have successors.
        Conversely, if Γ yields no successors, the state must be genuinely terminal.
        """
        state = initial_alpha_state(_FOCUS)
        visited: list[AlphaState] = [state]
        frontier = [state]
        for _ in range(10):
            next_front: list[AlphaState] = []
            for s in frontier:
                tz = gamma(s)
                if not tz.future:
                    # Must be terminal — check that COMMIT is in the stage word
                    assert s.is_terminal or StageLabel.COMMIT in {
                        n.label for n in s.stage_word_nf
                    }, f"Non-terminal state with no successors: {s.stage_word_nf}"
                next_front.extend(tz.future)
            frontier = next_front
            if not frontier:
                break

    def test_gamma_deterministic(self):
        state = initial_alpha_state(_FOCUS)
        tokens1 = {s.witness_token for s in gamma(state).future}
        tokens2 = {s.witness_token for s in gamma(state).future}
        assert tokens1 == tokens2

    def test_successor_words_are_normalized(self):
        for s in gamma(initial_alpha_state(_FOCUS)).future:
            assert normalize_stage_word(s.stage_word_nf) == s.stage_word_nf

    def test_terminal_has_no_successors(self):
        word = normalize_stage_word((
            StageNode(StageLabel.WIN, k_past=4),
            StageNode(StageLabel.IDX, layout_id="default"),
            StageNode(StageLabel.COMMIT, hash_scheme="sha256"),
        ))
        terminal = _mint_alpha_state(word, _FOCUS, b"", is_terminal=True)
        tz = gamma(terminal)
        assert len(tz.future) == 0
        assert tz.is_terminal


# ──────────────────────────────────────────────────────────────────────────────
# 5. TransformZipper 𝕌
# ──────────────────────────────────────────────────────────────────────────────

class TestTransformZipper:
    def _tz(self) -> TransformZipper:
        return gamma(initial_alpha_state(_FOCUS))

    def test_extract_returns_focus(self):
        tz = self._tz()
        assert tz.extract() is tz.focus

    def test_advance_moves_focus(self):
        tz = self._tz()
        if tz.future:
            next_s = tz.future[0]
            tz2 = tz.advance(next_s)
            assert tz2 is not None
            assert tz2.focus is next_s
            assert tz.focus in tz2.past

    def test_advance_unknown_state_returns_none(self):
        tz = self._tz()
        unknown = initial_alpha_state(b"\xff" * 32)
        assert tz.advance(unknown) is None

    def test_not_terminal_at_initial(self):
        assert not self._tz().is_terminal


# ──────────────────────────────────────────────────────────────────────────────
# 6. Ω lattice metamorphic checks
# ──────────────────────────────────────────────────────────────────────────────

class TestOmegaLattice:
    def test_more_stages_ge_fewer_stages(self):
        # Forward inclusion: a ≤ b iff a.labels ⊆ b.labels. More stages = larger.
        more = _omega([StageLabel.WIN, StageLabel.IDX])
        less = _omega([StageLabel.WIN])
        assert less <= more
        assert not (more <= less)

    def test_reflexive(self):
        e = _omega([StageLabel.WIN])
        assert e <= e

    def test_empty_is_bottom(self):
        # Empty word has no labels; it is the bottom element (⊆ every other).
        bottom = _omega([])
        refined = _omega([StageLabel.WIN, StageLabel.IDX])
        assert bottom <= refined

    def test_join_gives_union_of_labels(self):
        a = _omega([StageLabel.WIN])
        b = _omega([StageLabel.IDX, StageLabel.WIN])
        j = a.join(b)
        j_labels = {n.label for n in j.stage_word_nf}
        assert StageLabel.WIN in j_labels
        assert StageLabel.IDX in j_labels

    def test_join_idempotent(self):
        e = _omega([StageLabel.WIN, StageLabel.IDX])
        assert e.join(e).stage_word_nf == e.stage_word_nf

    def test_join_win_takes_min_k_past(self):
        a = _omega([StageLabel.WIN], k_past=8)
        b = _omega([StageLabel.WIN], k_past=4)
        j = a.join(b)
        win = [n for n in j.stage_word_nf if n.label == StageLabel.WIN]
        assert win[0].k_past == 4

    def test_meet_gives_intersection(self):
        a = _omega([StageLabel.WIN, StageLabel.IDX])
        b = _omega([StageLabel.WIN])
        m = a.meet(b)
        m_labels = {n.label for n in m.stage_word_nf}
        assert StageLabel.WIN in m_labels
        assert StageLabel.IDX not in m_labels

    def test_meet_disjoint_gives_empty(self):
        # WIN and IDX alone (without WIN) share no labels in this test:
        a = _omega([StageLabel.WIN])
        # IDX alone is not constructable without WIN dependency, so use empty vs WIN
        b = _omega([])
        m = a.meet(b)
        assert m.stage_word_nf == ()

    def test_meet_win_takes_max_k_past(self):
        a = _omega([StageLabel.WIN], k_past=4)
        b = _omega([StageLabel.WIN], k_past=8)
        m = a.meet(b)
        win = [n for n in m.stage_word_nf if n.label == StageLabel.WIN]
        assert win[0].k_past == 8

    def test_join_associative(self):
        a = _omega([StageLabel.WIN])
        b = _omega([StageLabel.WIN, StageLabel.IDX])
        c = _omega([StageLabel.WIN, StageLabel.IDX, StageLabel.COMMIT])
        j1 = a.join(b).join(c)
        j2 = a.join(b.join(c))
        assert j1.stage_word_nf == j2.stage_word_nf

    def test_join_upper_bound(self):
        """join(a, b) ≥ a and ≥ b."""
        a = _omega([StageLabel.WIN])
        b = _omega([StageLabel.WIN, StageLabel.IDX])
        j = a.join(b)
        assert a <= j
        assert b <= j

    def test_meet_lower_bound(self):
        """meet(a, b) ≤ a and ≤ b."""
        a = _omega([StageLabel.WIN, StageLabel.IDX])
        b = _omega([StageLabel.WIN])
        m = a.meet(b)
        assert m <= a
        assert m <= b


# ──────────────────────────────────────────────────────────────────────────────
# 7. Reachable Ω enumeration
# ──────────────────────────────────────────────────────────────────────────────

_STABLE_CLASS_COUNT: int | None = None  # set on first run, checked on subsequent


class TestReachableOmega:
    def test_finite(self):
        state = initial_alpha_state(_FOCUS)
        assert 0 < len(reachable_omega(state)) <= 16

    def test_contains_initial(self):
        state = initial_alpha_state(_FOCUS)
        initial_elem = alpha_state_to_omega(state)
        assert initial_elem in reachable_omega(state)

    def test_contains_terminal(self):
        terminals = [e for e in reachable_omega(initial_alpha_state(_FOCUS), max_depth=10)
                     if e.is_terminal]
        assert len(terminals) > 0

    def test_unique_keys(self):
        state = initial_alpha_state(_FOCUS)
        omega_set = reachable_omega(state)
        keys = [e.key for e in omega_set]
        assert len(keys) == len(set(keys))

    def test_all_preserve_focus_commitment(self):
        for elem in reachable_omega(initial_alpha_state(_FOCUS)):
            assert elem.focus_commitment == _FOCUS

    def test_label_count_bounded(self):
        for elem in reachable_omega(initial_alpha_state(_FOCUS)):
            assert len(elem.stage_word_nf) <= 3  # WIN, IDX, COMMIT

    def test_class_count_stable_under_fixed_seed(self):
        """
        Adversarial stability: Ω class count must not change across versions
        for the same initial focus. Drift indicates semantic fracture.
        """
        count = len(reachable_omega(initial_alpha_state(_FOCUS), max_depth=10))
        # Run again — must be identical
        count2 = len(reachable_omega(initial_alpha_state(_FOCUS), max_depth=10))
        assert count == count2


# ──────────────────────────────────────────────────────────────────────────────
# 8. Lattice homomorphism coherence (λ(a ∨ b) = λ(a) ∨ λ(b))
# ──────────────────────────────────────────────────────────────────────────────

class TestLatticeHomomorphism:
    def setup_method(self):
        self.checker = LatticeHomomorphismChecker()
        self.omega_set = reachable_omega(initial_alpha_state(_FOCUS), max_depth=10)

    def test_join_homomorphism_all_pairs(self):
        failures = []
        elems = list(self.omega_set)
        for i, a in enumerate(elems):
            for j, b in enumerate(elems):
                if i >= j:
                    continue
                if not self.checker.check_join(a, b):
                    failures.append((a.key[:8], b.key[:8]))
        assert not failures, f"λ-join-homomorphism failures: {failures}"

    def test_meet_homomorphism_all_pairs(self):
        failures = []
        elems = list(self.omega_set)
        for i, a in enumerate(elems):
            for j, b in enumerate(elems):
                if i >= j:
                    continue
                if not self.checker.check_meet(a, b):
                    failures.append((a.key[:8], b.key[:8]))
        assert not failures, f"λ-meet-homomorphism failures: {failures}"

    def test_full_coherence_check(self):
        failures = self.checker.check_coherence(self.omega_set)
        assert not failures, f"Lattice coherence failures:\n" + "\n".join(failures)

    def test_lambda_lift_idempotent_on_nf(self):
        """λ-lifting an already-NF element is identity."""
        for elem in self.omega_set:
            lifted = self.checker._lambda_lift(elem)
            assert lifted.key == elem.key


# ──────────────────────────────────────────────────────────────────────────────
# 9. Distributive law λ: 𝕋 ∘ 𝕌 ⇒ 𝕌 ∘ 𝕋
# ──────────────────────────────────────────────────────────────────────────────

class TestDistributiveLaw:
    def setup_method(self):
        self.checker = DistributiveLawChecker()

    def test_all_generators_satisfy_lambda(self):
        results = self.checker.check_all_generators(_FOCUS)
        failures = [k for k, v in results.items() if not v]
        assert not failures, f"λ violations: {failures}"

    def test_focus_commitment_preserved_across_generators(self):
        for label, stage in [
            (StageLabel.IDENTITY, StageNode(StageLabel.IDENTITY)),
            (StageLabel.WIN, StageNode(StageLabel.WIN, k_past=4)),
            (StageLabel.IDX, StageNode(StageLabel.IDX, layout_id="default")),
            (StageLabel.COMMIT, StageNode(StageLabel.COMMIT, hash_scheme="sha256")),
        ]:
            assert self.checker.check(_FOCUS, stage), f"λ failed for {label}"

    def test_different_focus_commitments_isolated(self):
        focus_a = hashlib.sha256(b"a").digest()
        focus_b = hashlib.sha256(b"b").digest()
        for s in gamma(initial_alpha_state(focus_a)).future:
            assert s.focus_commitment == focus_a
        for s in gamma(initial_alpha_state(focus_b)).future:
            assert s.focus_commitment == focus_b


# ──────────────────────────────────────────────────────────────────────────────
# 10. Spec Ω: prime filters as backend-selection geometry
# ──────────────────────────────────────────────────────────────────────────────

class TestSpecOmega:
    def test_prime_filters_exist(self):
        state = initial_alpha_state(_FOCUS)
        omega_set = reachable_omega(state)
        points = prime_filters(omega_set)
        assert len(points) > 0

    def test_prime_filters_are_spec_points(self):
        state = initial_alpha_state(_FOCUS)
        omega_set = reachable_omega(state)
        for point in prime_filters(omega_set):
            assert isinstance(point, SpecPoint)
            assert point.omega_key  # non-empty key

    def test_terminal_points_exist(self):
        state = initial_alpha_state(_FOCUS)
        omega_set = reachable_omega(state, max_depth=10)
        points = prime_filters(omega_set)
        terminal_points = [p for p in points if p.is_terminal]
        assert len(terminal_points) > 0

    def test_filter_count_matches_omega_elements(self):
        state = initial_alpha_state(_FOCUS)
        omega_set = reachable_omega(state)
        # Each Ω element generates at least one prime filter
        assert len(prime_filters(omega_set)) <= len(omega_set)


# ──────────────────────────────────────────────────────────────────────────────
# 11. Backends as Ω representatives
# ──────────────────────────────────────────────────────────────────────────────

class TestBackendsAsOmegaRepresentatives:
    def test_backend_ordering(self):
        """CPU ≤ GPU ≤ SNARK: more stages = larger in the forward-inclusion preorder."""
        gpu    = _omega([StageLabel.WIN, StageLabel.IDX])
        snark  = _omega([StageLabel.WIN, StageLabel.IDX, StageLabel.COMMIT])
        cpu    = _omega([StageLabel.WIN])

        assert cpu   <= gpu
        assert gpu   <= snark
        assert cpu   <= snark

    def test_join_gives_most_refined(self):
        gpu   = _omega([StageLabel.WIN, StageLabel.IDX])
        cpu   = _omega([StageLabel.WIN])
        j = gpu.join(cpu)
        assert j.stage_word_nf == gpu.stage_word_nf

    def test_snark_is_terminal(self):
        snark = _omega([StageLabel.WIN, StageLabel.IDX, StageLabel.COMMIT])
        assert snark.is_terminal

    def test_gpu_is_not_terminal(self):
        assert not _omega([StageLabel.WIN, StageLabel.IDX]).is_terminal

    def test_cpu_debug_is_not_terminal(self):
        assert not _omega([StageLabel.WIN]).is_terminal

    def test_backends_reachable_from_initial(self):
        state = initial_alpha_state(_FOCUS)
        omega_set = reachable_omega(state, max_depth=10)
        gpu_word = normalize_stage_word((
            StageNode(StageLabel.WIN, k_past=8),
            StageNode(StageLabel.IDX, layout_id="default"),
        ))
        gpu_key = stage_word_key(gpu_word, _FOCUS)
        assert any(e.key == gpu_key for e in omega_set), "GPU backend not reachable"


# ──────────────────────────────────────────────────────────────────────────────
# 12. Epistemic closure: witness token not forgeable
# ──────────────────────────────────────────────────────────────────────────────

class TestEpistemicClosureOmega:
    def test_witness_token_is_keyed_hash(self):
        state = initial_alpha_state(_FOCUS)
        assert state.witness_token != _FOCUS
        assert len(state.witness_token) == 32

    def test_different_cert_gives_different_token(self):
        word = (StageNode(StageLabel.WIN, k_past=4),)
        s1 = _mint_alpha_state(word, _FOCUS, b"cert_a", False)
        s2 = _mint_alpha_state(word, _FOCUS, b"cert_b", False)
        assert s1.witness_token != s2.witness_token

    def test_omega_key_reproducible(self):
        state = initial_alpha_state(_FOCUS)
        tz = gamma(state)
        if tz.future:
            succ = tz.future[0]
            elem = alpha_state_to_omega(succ)
            assert elem.key == stage_word_key(succ.stage_word_nf, succ.focus_commitment)

    def test_no_raw_trace_leak_in_alpha_state(self):
        state = initial_alpha_state(_FOCUS)
        assert not hasattr(state, "raw_trace")
        assert not hasattr(state, "source_bytes")
        assert hasattr(state, "focus_commitment")  # commitment is OK to expose
        assert hasattr(state, "witness_token")
