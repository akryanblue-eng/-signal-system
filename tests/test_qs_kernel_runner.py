"""
Tests for the qs-kernel runner, policy gate, and artifact determinism.

Covers:
  - run_kernel() produces all required outputs
  - All phase-1 gates pass (normal run)
  - MUT-HELLO-ILLEGAL-PROJECTION-WRITE always yields FAIL (golden sentinel)
  - All expected-FAIL mutations yield FAIL
  - Phase isolation: if phase 1 fails, phase 2/3 are absent
  - manifest hash is stable across two in-process runs
  - policy.check() correctly classifies violations
  - Meta-CI: all observability clauses covered
"""
import pytest

from src.qs_kernel.runner import run_kernel, KernelOutputs
from src.qs_kernel.policy import check as policy_check, PolicyViolation
from src.qs_kernel.canon import canonical_hash
from src.qs_kernel import meta_ci as _meta_ci


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _run() -> KernelOutputs:
    return run_kernel()


def _gate(outputs: KernelOutputs, gate_id: str) -> dict | None:
    for g in outputs.gate_results:
        if g["gateId"] == gate_id:
            return g
    return None


def _mutation(outputs: KernelOutputs, mutation_id: str) -> dict | None:
    for m in outputs.mutation_results:
        if m["mutationId"] == mutation_id:
            return m
    return None


# ──────────────────────────────────────────────────────────────────────────────
# 1. Output structure
# ──────────────────────────────────────────────────────────────────────────────

class TestRunnerOutputStructure:
    def setup_method(self):
        self.out = _run()

    def test_has_system_graph(self):
        assert isinstance(self.out.system_graph, dict)
        assert "nodes" in self.out.system_graph
        assert "edges" in self.out.system_graph
        assert "rootHash" in self.out.system_graph

    def test_write_capable_nodes_always_empty(self):
        """Projection inertness invariant: no certified projection has write capability."""
        assert self.out.system_graph.get("writeCapableNodes") == []

    def test_has_execution_traces(self):
        assert isinstance(self.out.execution_traces, list)
        assert len(self.out.execution_traces) > 0

    def test_has_gate_results(self):
        assert isinstance(self.out.gate_results, list)
        assert len(self.out.gate_results) > 0

    def test_has_mutation_results(self):
        assert isinstance(self.out.mutation_results, list)
        assert len(self.out.mutation_results) > 0

    def test_has_violation_graph(self):
        assert isinstance(self.out.violation_graph, dict)
        assert "nodes" in self.out.violation_graph
        assert "edges" in self.out.violation_graph
        assert "rootHash" in self.out.violation_graph

    def test_has_failure_witnesses(self):
        assert isinstance(self.out.failure_witnesses, list)

    def test_has_meta_ci_report(self):
        assert isinstance(self.out.meta_ci_report, dict)
        assert "coverageReport" in self.out.meta_ci_report
        assert "driftReport" in self.out.meta_ci_report


# ──────────────────────────────────────────────────────────────────────────────
# 2. Gate results: all phase-1 gates pass on clean kernel
# ──────────────────────────────────────────────────────────────────────────────

class TestGateResults:
    def setup_method(self):
        self.out = _run()

    def _gate(self, gate_id: str) -> dict:
        g = _gate(self.out, gate_id)
        assert g is not None, f"Gate {gate_id} not found in results"
        return g

    def test_closed_algebra_gate_passes(self):
        assert self._gate("GATE-P1-CLOSED-ALGEBRA")["outcome"] == "PASS"

    def test_budget_monotone_gate_passes(self):
        assert self._gate("GATE-P1-BUDGET-MONOTONE")["outcome"] == "PASS"

    def test_map_fn_closed_gate_passes(self):
        assert self._gate("GATE-P1-MAP-FN-CLOSED")["outcome"] == "PASS"

    def test_cert_idempotent_gate_passes(self):
        assert self._gate("GATE-P1-CERT-IDEMPOTENT")["outcome"] == "PASS"

    def test_nf_id_elim_gate_passes(self):
        assert self._gate("GATE-P1-NF-ID-ELIM")["outcome"] == "PASS"

    def test_fusion_rule_c_gate_passes(self):
        assert self._gate("GATE-P1-FUSION-RULE-C")["outcome"] == "PASS"

    def test_verify_cert_gate_passes(self):
        assert self._gate("GATE-P1-VERIFY-CERT")["outcome"] == "PASS"

    def test_alpha_counit_law_gate_passes(self):
        assert self._gate("GATE-P2-ALPHA-COUNIT-LAW")["outcome"] == "PASS"

    def test_omega_nonempty_gate_passes(self):
        assert self._gate("GATE-P3-OMEGA-NONEMPTY")["outcome"] == "PASS"

    def test_lambda_coherence_gate_passes(self):
        assert self._gate("GATE-P3-LAMBDA-COHERENCE")["outcome"] == "PASS"

    def test_focus_preserved_gate_passes(self):
        assert self._gate("GATE-P3-FOCUS-PRESERVED")["outcome"] == "PASS"

    def test_all_gates_have_required_keys(self):
        for g in self.out.gate_results:
            assert "gateId" in g
            assert "phase" in g
            assert "outcome" in g
            assert "evidenceHash" in g
            assert "reason" in g

    def test_gate_results_sorted_by_gate_id(self):
        ids = [g["gateId"] for g in self.out.gate_results]
        assert ids == sorted(ids)

    def test_all_phases_represented(self):
        phases = {g["phase"] for g in self.out.gate_results}
        assert 1 in phases
        assert 2 in phases
        assert 3 in phases


# ──────────────────────────────────────────────────────────────────────────────
# 3. Golden sentinel: MUT-HELLO-ILLEGAL-PROJECTION-WRITE
# ──────────────────────────────────────────────────────────────────────────────

class TestGoldenSentinelMutation:
    """
    MUT-HELLO-ILLEGAL-PROJECTION-WRITE must ALWAYS yield outcome=FAIL.
    If it ever yields PASS, the closed algebra is compromised — CI fatal.
    This is a security property, not a test case.
    """
    def test_sentinel_mutation_present(self):
        out = _run()
        m = _mutation(out, "MUT-HELLO-ILLEGAL-PROJECTION-WRITE")
        assert m is not None, "Sentinel mutation MUT-HELLO-ILLEGAL-PROJECTION-WRITE must always be present"

    def test_sentinel_outcome_is_always_fail(self):
        out = _run()
        m = _mutation(out, "MUT-HELLO-ILLEGAL-PROJECTION-WRITE")
        assert m["outcome"] == "FAIL", (
            "CRITICAL: MUT-HELLO-ILLEGAL-PROJECTION-WRITE yielded PASS. "
            "The closed projection algebra may be compromised. Gate: GATE-PROJECTION-INERT-23."
        )

    def test_sentinel_gate_is_projection_inert_23(self):
        out = _run()
        m = _mutation(out, "MUT-HELLO-ILLEGAL-PROJECTION-WRITE")
        assert m["gateId"] == "GATE-PROJECTION-INERT-23"

    def test_sentinel_is_not_legal_evolution(self):
        out = _run()
        m = _mutation(out, "MUT-HELLO-ILLEGAL-PROJECTION-WRITE")
        assert m["isLegalEvolution"] is False

    def test_policy_would_fail_if_sentinel_passed(self):
        """policy.check() correctly identifies sentinel PASS as CI-fatal."""
        fake_mutation_pass = {
            "mutationId": "MUT-HELLO-ILLEGAL-PROJECTION-WRITE",
            "operator": "illegal_write_projection",
            "targetId": "universe.B.term",
            "gateId": "GATE-PROJECTION-INERT-23",
            "outcome": "PASS",   # ← simulated compromise
            "expectedOutcome": "FAIL",
            "isLegalEvolution": False,
            "evidenceHash": "0" * 64,
        }
        manifest = {"hashes": {}, "kernelVersion": "1.0.0", "manifestHash": "x"}
        report = policy_check(
            outputs_a_manifest=manifest,
            outputs_b_manifest=None,
            gate_results=[],
            mutation_results=[fake_mutation_pass],
        )
        assert not report.ok
        assert any("ILLEGAL-PASS" in v.rule for v in report.violations)


# ──────────────────────────────────────────────────────────────────────────────
# 4. All expected-FAIL mutations yield FAIL
# ──────────────────────────────────────────────────────────────────────────────

class TestMutationResults:
    def setup_method(self):
        self.out = _run()

    def test_all_expected_fail_mutations_yield_fail(self):
        """No unexpected PASS for any non-legal-evolution mutation."""
        for m in self.out.mutation_results:
            if m["expectedOutcome"] == "FAIL" and not m["isLegalEvolution"]:
                assert m["outcome"] == "FAIL", (
                    f"Mutation {m['mutationId']} (gate {m['gateId']}) yielded PASS "
                    f"but expected FAIL with isLegalEvolution=False"
                )

    def test_noop_inject_is_legal_evolution(self):
        m = _mutation(self.out, "MUT-NOOP-INJECT-001")
        assert m is not None
        assert m["isLegalEvolution"] is True
        assert m["outcome"] == "PASS"

    def test_mutation_results_sorted_by_mutation_id_gate_id(self):
        keys = [(m["mutationId"], m["gateId"]) for m in self.out.mutation_results]
        assert keys == sorted(keys)

    def test_mutation_results_have_required_keys(self):
        required = {"mutationId", "operator", "targetId", "gateId",
                    "outcome", "expectedOutcome", "isLegalEvolution", "evidenceHash"}
        for m in self.out.mutation_results:
            assert required <= set(m.keys()), f"Missing keys in mutation {m.get('mutationId')}"

    def test_budget_amplify_fails(self):
        m = _mutation(self.out, "MUT-BUDGET-AMPLIFY-001")
        assert m is not None
        assert m["outcome"] == "FAIL"

    def test_witness_forge_fails(self):
        m = _mutation(self.out, "MUT-WITNESS-FORGE-001")
        assert m is not None
        assert m["outcome"] == "FAIL"

    def test_unknown_constructor_fails(self):
        m = _mutation(self.out, "MUT-UNKNOWN-CONSTRUCTOR-001")
        assert m is not None
        assert m["outcome"] == "FAIL"

    def test_map_fn_open_fails(self):
        m = _mutation(self.out, "MUT-MAP-FN-OPEN-001")
        assert m is not None
        assert m["outcome"] == "FAIL"


# ──────────────────────────────────────────────────────────────────────────────
# 5. Execution traces
# ──────────────────────────────────────────────────────────────────────────────

class TestExecutionTraces:
    def setup_method(self):
        self.out = _run()

    def test_traces_have_required_keys(self):
        required = {"worldId", "intentId", "traceHash", "focusHash",
                    "budgetGrade", "certHash", "commitment"}
        for t in self.out.execution_traces:
            assert required <= set(t.keys())

    def test_traces_sorted_by_world_intent_trace(self):
        keys = [(t["worldId"], t["intentId"], t["traceHash"]) for t in self.out.execution_traces]
        assert keys == sorted(keys)

    def test_world_id_is_pcp_kernel(self):
        for t in self.out.execution_traces:
            assert t["worldId"] == "pcp-kernel"

    def test_trace_hash_is_hex_string(self):
        for t in self.out.execution_traces:
            assert len(t["traceHash"]) == 64
            int(t["traceHash"], 16)  # must be valid hex

    def test_commitment_is_hex_string(self):
        for t in self.out.execution_traces:
            assert isinstance(t["commitment"], str)
            int(t["commitment"], 16)  # must be valid hex


# ──────────────────────────────────────────────────────────────────────────────
# 6. Phase isolation
# ──────────────────────────────────────────────────────────────────────────────

class TestPhaseIsolation:
    def test_clean_run_has_all_three_phases(self):
        out = _run()
        phases = {g["phase"] for g in out.gate_results}
        assert phases >= {1, 2, 3}

    def test_policy_rule3_catches_phase_leakage(self):
        """If phase-1 gate fails but phase-2 results are present, Rule 3 fires."""
        p1_fail = {"gateId": "GATE-P1-X", "phase": 1, "outcome": "FAIL",
                   "evidenceHash": "x", "reason": "test"}
        p2_gate = {"gateId": "GATE-P2-Y", "phase": 2, "outcome": "PASS",
                   "evidenceHash": "y", "reason": "test"}
        manifest = {"hashes": {}, "kernelVersion": "1.0.0", "manifestHash": "z"}
        report = policy_check(
            outputs_a_manifest=manifest,
            outputs_b_manifest=None,
            gate_results=[p1_fail, p2_gate],
            mutation_results=[],
        )
        assert not report.ok
        assert any("PHASE-LEAKAGE" in v.rule for v in report.violations)

    def test_policy_rule3_does_not_fire_for_clean_run(self):
        out = _run()
        manifest = {"hashes": {"x": "y"}, "kernelVersion": "1.0.0", "manifestHash": "z"}
        report = policy_check(
            outputs_a_manifest=manifest,
            outputs_b_manifest=None,
            gate_results=out.gate_results,
            mutation_results=out.mutation_results,
            meta_ci_report=out.meta_ci_report,
        )
        assert report.ok, f"Unexpected violations: {[v.description for v in report.violations]}"


# ──────────────────────────────────────────────────────────────────────────────
# 7. Determinism (in-process replay)
# ──────────────────────────────────────────────────────────────────────────────

class TestDeterminism:
    def test_manifest_hash_stable_across_two_runs(self):
        """Same run() twice must produce the same artifact hashes."""
        from src.qs_kernel.artifacts import write_artifacts
        import tempfile, pathlib

        out_a = _run()
        out_b = _run()

        with tempfile.TemporaryDirectory() as tmp_a, \
             tempfile.TemporaryDirectory() as tmp_b:
            m_a = write_artifacts(out_a, pathlib.Path(tmp_a))
            m_b = write_artifacts(out_b, pathlib.Path(tmp_b))

        assert m_a["manifestHash"] == m_b["manifestHash"], (
            f"Manifest hashes differ:\n  A: {m_a['manifestHash']}\n  B: {m_b['manifestHash']}"
        )

    def test_gate_results_hash_stable(self):
        from src.qs_kernel.canon import canonical_hash
        out_a = _run()
        out_b = _run()
        assert canonical_hash(out_a.gate_results) == canonical_hash(out_b.gate_results)

    def test_mutation_results_hash_stable(self):
        from src.qs_kernel.canon import canonical_hash
        out_a = _run()
        out_b = _run()
        assert canonical_hash(out_a.mutation_results) == canonical_hash(out_b.mutation_results)

    def test_system_graph_root_hash_stable(self):
        out_a = _run()
        out_b = _run()
        assert out_a.system_graph["rootHash"] == out_b.system_graph["rootHash"]

    def test_violation_graph_root_hash_stable(self):
        out_a = _run()
        out_b = _run()
        assert out_a.violation_graph["rootHash"] == out_b.violation_graph["rootHash"]


# ──────────────────────────────────────────────────────────────────────────────
# 8. System graph
# ──────────────────────────────────────────────────────────────────────────────

class TestSystemGraph:
    def setup_method(self):
        self.out = _run()
        self.sg = self.out.system_graph

    def test_nodes_sorted_by_id(self):
        ids = [n["id"] for n in self.sg["nodes"]]
        assert ids == sorted(ids)

    def test_edges_sorted_by_from_to_label(self):
        edges = self.sg["edges"]
        keys = [(e["from"], e["to"], e["label"]) for e in edges]
        assert keys == sorted(keys)

    def test_root_hash_matches_content(self):
        payload = {
            "edges": self.sg["edges"],
            "nodes": self.sg["nodes"],
            "writeCapableNodes": self.sg["writeCapableNodes"],
        }
        assert self.sg["rootHash"] == canonical_hash(payload)

    def test_nodes_have_required_fields(self):
        for n in self.sg["nodes"]:
            assert "id" in n
            assert "kind" in n
            assert "hash" in n
            assert "meta" in n

    def test_at_least_one_node(self):
        assert len(self.sg["nodes"]) > 0


# ──────────────────────────────────────────────────────────────────────────────
# 9. Meta-CI coverage (§52)
# ──────────────────────────────────────────────────────────────────────────────

class TestMetaCICoverage:
    def test_no_uncovered_observability_clauses(self):
        out = _run()
        uncovered = out.meta_ci_report["coverageReport"]["uncoveredObservability"]
        assert uncovered == [], (
            f"Meta-CI: observability clauses never exercised: {uncovered}"
        )

    def test_drift_report_ok(self):
        out = _run()
        assert out.meta_ci_report["driftReport"]["ok"], (
            f"Meta-CI drift detected: {out.meta_ci_report['driftReport']['drifts']}"
        )

    def test_meta_ci_report_overall_ok(self):
        out = _run()
        assert out.meta_ci_report["ok"]

    def test_policy_rule5_fires_on_uncovered_clause(self):
        """policy.check() catches uncovered observability clauses."""
        fake_meta_report = {
            "coverageReport": {
                "uncoveredObservability": ["OBS-TRACE-EVAL"],
                "clauses": [],
                "totalClauses": 1,
                "totalCovered": 0,
            },
            "driftReport": {"ok": True, "drifts": [], "driftCount": 0},
            "ok": False,
            "specVersion": "meta-ci-v1",
        }
        manifest = {"hashes": {"x": "y"}, "kernelVersion": "1.0.0", "manifestHash": "z"}
        report = policy_check(
            outputs_a_manifest=manifest,
            outputs_b_manifest=None,
            gate_results=[],
            mutation_results=[],
            meta_ci_report=fake_meta_report,
        )
        assert not report.ok
        assert any("COVERAGE" in v.rule for v in report.violations)


# ──────────────────────────────────────────────────────────────────────────────
# 10. Policy: replay check (Rule 1)
# ──────────────────────────────────────────────────────────────────────────────

class TestPolicyRule1:
    def test_matching_manifests_ok(self):
        manifest = {"hashes": {"x": "abc"}, "kernelVersion": "1.0.0", "manifestHash": "abc123"}
        report = policy_check(
            outputs_a_manifest=manifest,
            outputs_b_manifest=manifest,
            gate_results=[],
            mutation_results=[],
        )
        assert report.ok

    def test_mismatched_manifests_fail(self):
        m_a = {"hashes": {}, "kernelVersion": "1.0.0", "manifestHash": "aaa"}
        m_b = {"hashes": {}, "kernelVersion": "1.0.0", "manifestHash": "bbb"}
        report = policy_check(
            outputs_a_manifest=m_a,
            outputs_b_manifest=m_b,
            gate_results=[],
            mutation_results=[],
        )
        assert not report.ok
        assert any("NONDETERMINISM" in v.rule for v in report.violations)
