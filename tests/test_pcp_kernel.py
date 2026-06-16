"""
Proof-carrying projection kernel — test suite.

Covers:
  1. BudgetGrade grading functor (max composition law)
  2. Certifier: admits valid terms, rejects invalid ones
  3. Rewrite system: normal forms, confluence, critical pairs
  4. Interpreter: determinism, provenance, coKleisli composition
  5. Comonadic artifact operations (extract, duplicate, map_payload)
  6. WitnessRef opacity and kernel-only minting
  7. TraceZipper comonad operations
  8. α-chain: comonad homomorphism laws
  9. Epistemic closure invariants
  10. CI re-verification (verify_certificate)
"""
import hashlib
import pytest

from src.pcp_budget import BudgetGrade, compose_grade
from src.pcp_term import (
    Id, Compose, MapWitnesses, LiftDirector, LiftField,
    LiftOverlay, LiftCounterfactual, RestrictBudget, ProjectSegment,
    FoldTrace, FusedDirectorField,
)
from src.pcp_rewrite import NormalForm, Rewriter, ConfluenceChecker
from src.pcp_kernel import (
    SovereignTrace, TraceZipper, WitnessCoalgebra, RawBytesCoalgebra,
    CertifiedProjection, ProjectionCertificate,
    CertificationError, certify, interpret, verify_certificate,
    _mint_witness,
)
from src.pcp_artifact import Artifact, ArtifactRecord, WitnessView
from src.pcp_witness_ref import WitnessRef
from src.pcp_alpha import (
    WindowZipper, AlphaChain, CanonicalizationStage,
    WindowingStage, IndexedExecutionStage,
)

_TRACE = b"test-trace-data-0123456789abcdef"


# ──────────────────────────────────────────────────────────────────────────────
# 1. Budget grading functor
# ──────────────────────────────────────────────────────────────────────────────

class TestBudgetGrade:
    def test_compose_grade_is_max(self):
        assert compose_grade(
            BudgetGrade.STREAMING_NO_LOOKAHEAD,
            BudgetGrade.BATCH_LOOKAHEAD_K,
        ) == BudgetGrade.BATCH_LOOKAHEAD_K

    def test_compose_grade_highest_wins(self):
        assert compose_grade(
            BudgetGrade.INDEXED_ALLOWED,
            BudgetGrade.NO_ALLOCATION,
        ) == BudgetGrade.INDEXED_ALLOWED

    def test_compose_grade_idempotent(self):
        for g in BudgetGrade:
            assert compose_grade(g, g) == g

    def test_grade_total_order(self):
        grades = list(BudgetGrade)
        for i, g in enumerate(grades):
            for j, h in enumerate(grades):
                if i < j:
                    assert g < h


# ──────────────────────────────────────────────────────────────────────────────
# 2. Certifier — valid terms
# ──────────────────────────────────────────────────────────────────────────────

class TestCertifierValidTerms:
    def test_id_certifies(self):
        cp = certify(Id())
        assert isinstance(cp, CertifiedProjection)
        assert cp.budget_grade == BudgetGrade.STREAMING_NO_LOOKAHEAD
        assert cp.certificate.closed_under_kernel_laws

    def test_lift_director_certifies(self):
        cp = certify(LiftDirector())
        assert cp.budget_grade == BudgetGrade.STREAMING_NO_LOOKAHEAD

    def test_lift_field_is_batch(self):
        cp = certify(LiftField())
        assert cp.budget_grade == BudgetGrade.BATCH_LOOKAHEAD_K

    def test_counterfactual_is_indexed(self):
        cp = certify(LiftCounterfactual())
        assert cp.budget_grade == BudgetGrade.INDEXED_ALLOWED

    def test_compose_grade_propagates(self):
        cp = certify(Compose(LiftField(), LiftDirector()))
        assert cp.budget_grade == BudgetGrade.BATCH_LOOKAHEAD_K

    def test_restrict_budget_lowers_grade(self):
        # FoldTrace = BATCH; restrict to STREAMING is valid downcast
        cp = certify(RestrictBudget(BudgetGrade.STREAMING_NO_LOOKAHEAD, FoldTrace()))
        assert cp.budget_grade == BudgetGrade.STREAMING_NO_LOOKAHEAD

    def test_map_witnesses_valid_symbol(self):
        cp = certify(MapWitnesses("witness_identity"))
        assert cp.budget_grade == BudgetGrade.STREAMING_NO_LOOKAHEAD

    def test_project_segment_certifies(self):
        cp = certify(ProjectSegment("scene_01"))
        assert cp.budget_grade == BudgetGrade.STREAMING_NO_LOOKAHEAD

    def test_all_constructor_types_certify(self):
        terms = [
            Id(),
            LiftDirector(),
            LiftField(),
            LiftOverlay(),
            LiftCounterfactual(),
            FoldTrace(),
            FusedDirectorField(),
            MapWitnesses("witness_dedup"),
            ProjectSegment("seg_a"),
            Compose(Id(), LiftDirector()),
            RestrictBudget(BudgetGrade.STREAMING_NO_LOOKAHEAD, FoldTrace()),
        ]
        for term in terms:
            cp = certify(term)
            assert isinstance(cp, CertifiedProjection), f"failed for {type(term).__name__}"

    def test_stable_hash_reproducible(self):
        cp1 = certify(Compose(LiftDirector(), Id()), "policy_a")
        cp2 = certify(Compose(LiftDirector(), Id()), "policy_a")
        assert cp1.stable_hash == cp2.stable_hash

    def test_policy_tag_changes_stable_hash(self):
        cp1 = certify(Id(), "policy_a")
        cp2 = certify(Id(), "policy_b")
        assert cp1.stable_hash != cp2.stable_hash

    def test_term_and_normal_form_hashes_exist(self):
        cp = certify(Compose(Id(), LiftDirector()))
        assert cp.term_hash
        assert cp.normal_form_hash
        # After normalization, compose(id, t) → t, so the normal form is LiftDirector
        assert cp.normal_form_term == LiftDirector()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Certifier — invalid terms
# ──────────────────────────────────────────────────────────────────────────────

class TestCertifierRejectsInvalidTerms:
    def test_unknown_fn_symbol_rejected(self):
        with pytest.raises(CertificationError, match="Unknown kernel fn symbol"):
            certify(MapWitnesses("user_custom_fn"))

    def test_budget_amplification_rejected(self):
        # LiftDirector = STREAMING(0); RestrictBudget(BATCH=1) > STREAMING → amplification
        with pytest.raises(CertificationError, match="amplif|Budget"):
            certify(RestrictBudget(BudgetGrade.BATCH_LOOKAHEAD_K, LiftDirector()))

    def test_budget_amplification_indexed_on_streaming(self):
        with pytest.raises(CertificationError, match="amplif|Budget"):
            certify(RestrictBudget(BudgetGrade.INDEXED_ALLOWED, LiftDirector()))

    def test_bad_segment_id_rejected(self):
        with pytest.raises(CertificationError, match="segment_id"):
            certify(ProjectSegment("bad segment!"))

    def test_empty_segment_id_rejected(self):
        with pytest.raises(CertificationError, match="segment_id"):
            certify(ProjectSegment(""))

    def test_segment_id_with_uppercase_rejected(self):
        with pytest.raises(CertificationError, match="segment_id"):
            certify(ProjectSegment("Scene_01"))

    def test_non_kernel_constructor_rejected(self):
        class Impostor:
            pass
        with pytest.raises(CertificationError, match="Non-kernel constructor"):
            certify(Impostor())  # type: ignore


# ──────────────────────────────────────────────────────────────────────────────
# 4. Rewrite system
# ──────────────────────────────────────────────────────────────────────────────

class TestRewriteSystem:
    def setup_method(self):
        self.rw = Rewriter()

    def test_identity_elimination_left(self):
        nf = self.rw.normalize(Compose(Id(), LiftDirector()))
        assert nf.term == LiftDirector()

    def test_identity_elimination_right(self):
        nf = self.rw.normalize(Compose(LiftDirector(), Id()))
        assert nf.term == LiftDirector()

    def test_identity_both_sides(self):
        nf = self.rw.normalize(Compose(Id(), Compose(Id(), LiftField())))
        assert nf.term == LiftField()

    def test_associativity_right_assoc(self):
        # compose(compose(a, b), c) → compose(a, compose(b, c))
        a, b, c = LiftOverlay(), LiftDirector(), LiftOverlay()
        nf = self.rw.normalize(Compose(Compose(a, b), c))
        assert nf.term == Compose(a, Compose(b, c))

    def test_projection_fusion(self):
        # Compose(LiftField, LiftDirector) → FusedDirectorField
        nf = self.rw.normalize(Compose(LiftField(), LiftDirector()))
        assert nf.term == FusedDirectorField()

    def test_projection_fusion_in_chain(self):
        # Id ∘ (LiftField ∘ LiftDirector) → FusedDirectorField (after id-elim)
        nf = self.rw.normalize(Compose(Id(), Compose(LiftField(), LiftDirector())))
        assert nf.term == FusedDirectorField()

    def test_double_restriction_collapses(self):
        # RestrictBudget(b1, RestrictBudget(b2, t)) → RestrictBudget(min(b1, b2), t)
        inner = FoldTrace()
        term = RestrictBudget(
            BudgetGrade.STREAMING_NO_LOOKAHEAD,
            RestrictBudget(BudgetGrade.STREAMING_NO_LOOKAHEAD, inner),
        )
        nf = self.rw.normalize(term)
        assert nf.term == RestrictBudget(BudgetGrade.STREAMING_NO_LOOKAHEAD, inner)

    def test_map_witnesses_identity_eliminates(self):
        nf = self.rw.normalize(Compose(MapWitnesses("witness_identity"), LiftDirector()))
        assert nf.term == LiftDirector()

    def test_normal_form_is_stable(self):
        # Normalizing an already-normalized term returns the same hash
        term = LiftField()
        nf1 = self.rw.normalize(term)
        nf2 = self.rw.normalize(nf1.term)
        assert nf1.hash == nf2.hash

    def test_normal_form_hash_is_deterministic(self):
        term = Compose(Compose(LiftDirector(), Id()), LiftOverlay())
        nf1 = self.rw.normalize(term)
        nf2 = self.rw.normalize(term)
        assert nf1.hash == nf2.hash


class TestConfluenceChecker:
    def setup_method(self):
        self.checker = ConfluenceChecker()

    def test_simple_terms_are_confluent(self):
        for term in [Id(), LiftDirector(), FoldTrace(), FusedDirectorField()]:
            assert self.checker.is_confluent(term), f"Not confluent: {term}"

    def test_compose_chains_are_confluent(self):
        term = Compose(Compose(LiftOverlay(), LiftDirector()), LiftField())
        assert self.checker.is_confluent(term)

    def test_no_critical_pair_failures(self):
        failures = self.checker.check_critical_pairs()
        assert failures == [], f"Critical pair failures: {failures}"


# ──────────────────────────────────────────────────────────────────────────────
# 5. Interpreter: determinism and provenance
# ──────────────────────────────────────────────────────────────────────────────

class TestInterpreter:
    def _t(self) -> SovereignTrace:
        return SovereignTrace(_TRACE)

    def test_id_returns_full_trace_payload(self):
        cp = certify(Id())
        art = interpret(cp, self._t())
        assert isinstance(art, Artifact)
        assert art.records[0].payload == _TRACE

    def test_determinism_same_trace(self):
        cp = certify(LiftDirector())
        t = self._t()
        assert interpret(cp, t).provenance_hash == interpret(cp, t).provenance_hash

    def test_determinism_fold_trace(self):
        cp = certify(FoldTrace())
        t = self._t()
        art1 = interpret(cp, t)
        art2 = interpret(cp, t)
        assert art1.records == art2.records

    def test_different_traces_different_artifacts(self):
        cp = certify(LiftField())
        art1 = interpret(cp, SovereignTrace(b"trace-a"))
        art2 = interpret(cp, SovereignTrace(b"trace-b"))
        assert art1.provenance_hash != art2.provenance_hash

    def test_compose_is_sequential(self):
        cp = certify(Compose(LiftOverlay(), LiftDirector()))
        art = interpret(cp, self._t())
        assert isinstance(art, Artifact)
        assert art.source_term_hash == cp.term_hash

    def test_fused_director_field_same_as_chain(self):
        # Certifying the chain fuses it; the fused form should compute the same thing
        # as the FusedDirectorField primitive (they share the evaluator op "fused_director_field")
        cp_fused_prim = certify(FusedDirectorField())
        cp_chain = certify(Compose(LiftField(), LiftDirector()))
        t = self._t()
        art_prim = interpret(cp_fused_prim, t)
        art_chain = interpret(cp_chain, t)
        # Both use the same fused_director_field evaluator plan after normalization
        assert art_prim.provenance_hash == art_chain.provenance_hash

    def test_restrict_budget_transparent_to_output(self):
        # RestrictBudget is a policy declaration; output is identical to unrestricted
        cp_plain = certify(FoldTrace())
        cp_restricted = certify(RestrictBudget(BudgetGrade.STREAMING_NO_LOOKAHEAD, FoldTrace()))
        t = self._t()
        assert interpret(cp_plain, t).records == interpret(cp_restricted, t).records

    def test_provenance_hash_covers_all_witness_tokens(self):
        cp = certify(LiftDirector())
        art = interpret(cp, self._t())
        h = hashlib.sha256()
        for r in art.records:
            h.update(r.address._token)
        assert art.provenance_hash == h.digest()

    def test_raw_term_rejected_at_runtime(self):
        with pytest.raises(TypeError, match="CertifiedProjection"):
            interpret(Id(), self._t())  # type: ignore

    def test_raw_bytes_rejected_at_runtime(self):
        cp = certify(Id())
        with pytest.raises(TypeError, match="SovereignTrace"):
            interpret(cp, _TRACE)  # type: ignore

    def test_fold_trace_produces_multiple_records(self):
        cp = certify(FoldTrace())
        art = interpret(cp, SovereignTrace(b"x" * 64))
        assert len(art.records) > 1

    def test_project_segment_deterministic(self):
        cp = certify(ProjectSegment("scene_a"))
        t = self._t()
        assert interpret(cp, t).provenance_hash == interpret(cp, t).provenance_hash

    def test_different_segments_produce_different_artifacts(self):
        cpa = certify(ProjectSegment("scene_a"))
        cpb = certify(ProjectSegment("scene_b"))
        t = self._t()
        assert interpret(cpa, t).provenance_hash != interpret(cpb, t).provenance_hash


# ──────────────────────────────────────────────────────────────────────────────
# 6. Comonadic artifact operations
# ──────────────────────────────────────────────────────────────────────────────

class TestArtifactComonad:
    def _artifact(self) -> Artifact:
        cp = certify(LiftDirector())
        return interpret(cp, SovereignTrace(b"comonad-test-data" * 4))

    def test_extract_returns_witness_view(self):
        art = self._artifact()
        view = art.extract()
        assert isinstance(view, WitnessView)
        assert len(view.witness_refs) == len(art.records)
        assert view.provenance_hash == art.provenance_hash

    def test_extract_counit_law(self):
        # extract ∘ id = id on the witness set
        art = self._artifact()
        view = art.extract()
        assert view.witness_refs == tuple(r.address for r in art.records)

    def test_duplicate_preserves_provenance(self):
        art = self._artifact()
        left, right = art.duplicate()
        assert left.provenance_hash == art.provenance_hash
        assert right.provenance_hash == art.provenance_hash

    def test_duplicate_covers_all_records(self):
        art = self._artifact()
        left, right = art.duplicate()
        assert len(left.records) + len(right.records) == len(art.records)

    def test_map_payload_preserves_witness_refs(self):
        art = self._artifact()
        orig_refs = [r.address for r in art.records]
        mapped = art.map_payload(lambda p: hashlib.sha256(p).digest())
        assert [r.address for r in mapped.records] == orig_refs

    def test_map_payload_preserves_provenance_hash(self):
        # provenance_hash is over witness tokens only — survives payload transformation
        art = self._artifact()
        mapped = art.map_payload(lambda p: b"\xff" + p)
        assert mapped.provenance_hash == art.provenance_hash

    def test_map_payload_changes_payload_content(self):
        art = self._artifact()
        mapped = art.map_payload(lambda p: b"\x00" * len(p))
        for orig, new in zip(art.records, mapped.records):
            if orig.payload:  # non-empty
                assert new.payload != orig.payload


# ──────────────────────────────────────────────────────────────────────────────
# 7. WitnessRef opacity
# ──────────────────────────────────────────────────────────────────────────────

class TestWitnessRefOpacity:
    def test_external_construction_raises(self):
        with pytest.raises(TypeError, match="opaque|kernel|protocol"):
            WitnessRef(_token=bytes(32))  # no sentinel

    def test_kernel_can_mint(self):
        ref = _mint_witness(b"test", 0)
        assert isinstance(ref, WitnessRef)
        assert len(ref._token) == 32

    def test_minted_tokens_are_deterministic(self):
        r1 = _mint_witness(b"abc", 0)
        r2 = _mint_witness(b"abc", 0)
        assert r1 == r2

    def test_different_inputs_different_tokens(self):
        r1 = _mint_witness(b"abc", 0)
        r2 = _mint_witness(b"def", 0)
        assert r1 != r2

    def test_witness_ref_in_artifact_is_opaque(self):
        cp = certify(Id())
        art = interpret(cp, SovereignTrace(b"opacity-test"))
        ref = art.records[0].address
        assert isinstance(ref, WitnessRef)
        assert ref._token != b"opacity-test"  # token is keyed hash, not raw bytes


# ──────────────────────────────────────────────────────────────────────────────
# 8. TraceZipper comonad
# ──────────────────────────────────────────────────────────────────────────────

class TestTraceZipper:
    def _make_zipper(self) -> TraceZipper:
        refs = tuple(_mint_witness(b"z", i) for i in range(5))
        return TraceZipper(past=(), focus=refs[0], future=refs[1:])

    def test_extract_returns_focus(self):
        z = self._make_zipper()
        assert z.extract() is z.focus

    def test_advance_moves_focus(self):
        z = self._make_zipper()
        z2 = z.advance()
        assert z2 is not None
        assert z2.focus == z.future[0]
        assert z.focus in z2.past

    def test_advance_at_end_returns_none(self):
        ref = _mint_witness(b"end", 0)
        z = TraceZipper(past=(), focus=ref, future=())
        assert z.advance() is None

    def test_is_live_when_no_future(self):
        ref = _mint_witness(b"live", 0)
        z = TraceZipper(past=(), focus=ref, future=())
        assert z.is_live

    def test_is_not_live_with_future(self):
        z = self._make_zipper()
        assert not z.is_live

    def test_limit_window_truncates_future(self):
        z = self._make_zipper()
        z2 = z.limit_window(2)
        assert len(z2.future) == 2

    def test_coalgebra_unfolds_trace(self):
        coalgebra = RawBytesCoalgebra()
        trace = SovereignTrace(b"x" * 64)
        zipper = coalgebra.unfold(trace)
        assert isinstance(zipper, TraceZipper)
        assert zipper.focus is not None


# ──────────────────────────────────────────────────────────────────────────────
# 9. α-chain: comonad homomorphism laws
# ──────────────────────────────────────────────────────────────────────────────

class TestAlphaChain:
    def _refs(self, n: int) -> tuple:
        return tuple(_mint_witness(b"alpha", i) for i in range(n))

    def test_window_zipper_extract_invariant(self):
        """Law A: ε' ∘ α = ε — focus token unchanged by α."""
        refs = self._refs(5)
        alpha = AlphaChain(k_past=4, k_future=0)
        wz = alpha.apply(focus=refs[0], context=refs[1:])
        assert isinstance(wz, WindowZipper)
        assert wz.extract()._token == refs[0]._token

    def test_all_stages_pass_law_a(self):
        refs = self._refs(6)
        alpha = AlphaChain(k_past=4)
        results = alpha.verify_all_stages(focus=refs[0], context=refs[1:])
        assert all(results.values()), f"Stage failures: {results}"

    def test_focus_invariant_across_all_stages(self):
        refs = self._refs(4)
        for Stage in [CanonicalizationStage, WindowingStage, IndexedExecutionStage]:
            stage = Stage()
            result = stage.apply(refs[0], refs[1:])
            assert result.focus._token == refs[0]._token, f"Focus changed in {Stage.__name__}"

    def test_window_zipper_is_live_with_k_future_zero(self):
        refs = self._refs(4)
        alpha = AlphaChain(k_past=4, k_future=0)
        wz = alpha.apply(refs[0], refs[1:])
        assert wz.is_live

    def test_truncation_marked_when_context_exceeds_window(self):
        refs = self._refs(20)
        alpha = AlphaChain(k_past=4, k_future=0)
        wz = alpha.apply(refs[0], refs[1:])
        assert wz.past_truncated

    def test_no_truncation_within_window(self):
        refs = self._refs(5)
        alpha = AlphaChain(k_past=8, k_future=0)
        wz = alpha.apply(refs[0], refs[1:])
        assert not wz.past_truncated

    def test_commitment_is_deterministic(self):
        refs = self._refs(4)
        alpha = AlphaChain(k_past=4)
        wz1 = alpha.apply(refs[0], refs[1:])
        wz2 = alpha.apply(refs[0], refs[1:])
        assert wz1.commitment == wz2.commitment

    def test_commitment_changes_with_different_context(self):
        refs_a = self._refs(4)
        refs_b = tuple(_mint_witness(b"beta", i) for i in range(4))
        alpha = AlphaChain(k_past=4)
        wz_a = alpha.apply(refs_a[0], refs_a[1:])
        wz_b = alpha.apply(refs_b[0], refs_b[1:])
        assert wz_a.commitment != wz_b.commitment


# ──────────────────────────────────────────────────────────────────────────────
# 10. CI re-verification
# ──────────────────────────────────────────────────────────────────────────────

class TestVerifyCertificate:
    def test_valid_cert_verifies(self):
        cp = certify(Compose(LiftDirector(), Id()))
        assert verify_certificate(cp)

    def test_all_term_types_verify(self):
        terms = [
            Id(), Compose(Id(), Id()), MapWitnesses("witness_identity"),
            LiftDirector(), LiftField(), LiftOverlay(), LiftCounterfactual(),
            RestrictBudget(BudgetGrade.STREAMING_NO_LOOKAHEAD, FoldTrace()),
            ProjectSegment("test_seg"), FoldTrace(), FusedDirectorField(),
        ]
        for term in terms:
            cp = certify(term)
            assert verify_certificate(cp), f"Verification failed for {type(term).__name__}"

    def test_tampered_term_hash_fails(self):
        cp = certify(Id())
        bad = CertifiedProjection(
            term_hash="dead" * 16,
            normal_form_hash=cp.normal_form_hash,
            term=cp.term,
            normal_form_term=cp.normal_form_term,
            policy_tag=cp.policy_tag,
            budget_grade=cp.budget_grade,
            certificate=cp.certificate,
            evaluator_plan=cp.evaluator_plan,
            stable_hash=cp.stable_hash,
        )
        assert not verify_certificate(bad)

    def test_tampered_stable_hash_fails(self):
        cp = certify(Id())
        bad = CertifiedProjection(
            term_hash=cp.term_hash,
            normal_form_hash=cp.normal_form_hash,
            term=cp.term,
            normal_form_term=cp.normal_form_term,
            policy_tag=cp.policy_tag,
            budget_grade=cp.budget_grade,
            certificate=cp.certificate,
            evaluator_plan=cp.evaluator_plan,
            stable_hash="00" * 32,
        )
        assert not verify_certificate(bad)

    def test_non_certified_projection_fails(self):
        assert not verify_certificate("not a projection")  # type: ignore

    def test_wrong_type_fails(self):
        assert not verify_certificate(42)  # type: ignore


# ──────────────────────────────────────────────────────────────────────────────
# 11. Epistemic closure
# ──────────────────────────────────────────────────────────────────────────────

class TestEpistemicClosure:
    def test_artifact_has_no_term_reference(self):
        """No reverse path from Artifact to Term — ontology cannot leak back."""
        cp = certify(LiftDirector())
        art = interpret(cp, SovereignTrace(b"closure-test"))
        assert not hasattr(art, "term")
        assert not hasattr(art, "certified_projection")
        assert not hasattr(art, "evaluator_plan")
        assert hasattr(art, "source_term_hash")  # hash only, not the term itself

    def test_sovereign_trace_raw_not_public(self):
        """SovereignTrace hides raw bytes from external code."""
        trace = SovereignTrace(b"opaque-bytes")
        assert not hasattr(trace, "raw")
        assert not hasattr(trace, "data")

    def test_witness_ref_token_is_hash_not_plaintext(self):
        """WitnessRef token is a keyed hash — raw trace not recoverable."""
        cp = certify(Id())
        art = interpret(cp, SovereignTrace(b"plain-text-trace"))
        ref = art.records[0].address
        assert ref._token != b"plain-text-trace"
        assert len(ref._token) == 32

    def test_certified_projection_term_is_read_only_for_audit(self):
        """Term field exists for auditability only — cannot be used to execute."""
        cp = certify(LiftOverlay())
        assert cp.term == LiftOverlay()
        # Calling interpret on the raw term would fail — only CertifiedProjection runs
        with pytest.raises(TypeError):
            interpret(cp.term, SovereignTrace(b"x"))  # type: ignore

    def test_normal_form_equivalence_class(self):
        """Semantically equivalent terms share a normal_form_hash."""
        # compose(id, LiftDirector) normalizes to LiftDirector
        cp1 = certify(LiftDirector())
        cp2 = certify(Compose(Id(), LiftDirector()))
        assert cp1.normal_form_hash == cp2.normal_form_hash

    def test_fused_and_chain_share_normal_form(self):
        """LiftField ∘ LiftDirector fuses to FusedDirectorField — same normal form."""
        cp_chain = certify(Compose(LiftField(), LiftDirector()))
        cp_fused = certify(FusedDirectorField())
        assert cp_chain.normal_form_hash == cp_fused.normal_form_hash
