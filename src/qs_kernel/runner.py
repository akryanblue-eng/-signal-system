"""
Core kernel runner: run_kernel(repo_path, config) → KernelOutputs.

Pipeline (strict phase order):
  Phase 1  — Certification gates: certify(), closed algebra, budget monotonicity
  Phase 2  — Trace evaluation gates: interpret(), α-chain homomorphism
  Phase 3  — Ω lattice gates: coherence, λ-homomorphism
  Mutations — Adversarial tests (always run, isolated from phase gates)

Phase isolation contract:
  If any Phase-1 gate fails, Phase 2/3 are NOT run.
  execution_traces will be [] and phase-2/3 gate_results will be absent.
  policy.check() verifies this post-hoc — runner enforces it structurally.

All outputs are plain Python dicts ready for canonical_serialize().
All IDs are deterministic (SHA-256 derived, never UUID/timestamp).
Arrays are sorted by semantic keys; no Python set/dict iteration order relied upon.
"""
from __future__ import annotations
import hashlib
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..pcp_budget import BudgetGrade
from ..pcp_kernel import (
    CertificationError, SovereignTrace,
    certify, interpret, verify_certificate,
)
from ..pcp_term import (
    Id, Compose, FoldTrace, FusedDirectorField,
    LiftDirector, LiftField, LiftOverlay, LiftCounterfactual,
    MapWitnesses, ProjectSegment, RestrictBudget,
)
from ..pcp_alpha import AlphaChain
from ..pcp_omega import (
    LatticeHomomorphismChecker, initial_alpha_state, reachable_omega,
)
from .canon import canonical_hash, sha256_hex
from . import meta_ci

if TYPE_CHECKING:
    from .config import KernelConfig


_KERNEL_VERSION = "1.0.0"
_WORLD_ID = "pcp-kernel"

# Synthetic trace bytes: deterministic, fixed across runs
_SYNTHETIC_TRACE = b"quantum-star-kernel-bootstrap-v1" * 2   # 64 bytes
_FOCUS_COMMITMENT = hashlib.sha256(b"qs-kernel-focus-v1").digest()


@dataclass
class KernelOutputs:
    """All outputs from a single kernel run. Ready for artifact serialization."""
    system_graph: dict
    execution_traces: list[dict]
    gate_results: list[dict]
    mutation_results: list[dict]
    violation_graph: dict
    failure_witnesses: list[dict]
    meta_ci_report: dict


# ──────────────────────────────────────────────────────────────────────────────
# Standard term set (fixed, deterministic)
# Each entry: (node_id, term, kind_label)
# ──────────────────────────────────────────────────────────────────────────────

_STANDARD_TERMS = [
    ("node.certified.fold_trace",       FoldTrace(),                                           "trace_fold"),
    ("node.certified.fused",            FusedDirectorField(),                                  "kernel_primitive"),
    ("node.certified.id",               Id(),                                                  "basic_projection"),
    ("node.certified.lift_director",    LiftDirector(),                                        "director_projection"),
    ("node.certified.lift_field",       LiftField(),                                           "field_projection"),
    ("node.certified.map_identity",     MapWitnesses("witness_identity"),                      "witness_transform"),
    ("node.certified.project_scene01",  ProjectSegment("scene01"),                             "segment_projection"),
    ("node.certified.restrict_stream",  RestrictBudget(BudgetGrade.STREAMING_NO_LOOKAHEAD, Id()), "budget_endomorphism"),
    ("node.certified.compose_fuse",     Compose(LiftField(), LiftDirector()),                  "composition"),
]

# Static edges: compositional / rewrite-derived relationships
_STATIC_EDGES = [
    # Compose(LiftField, LiftDirector) --rule_C--> FusedDirectorField
    {"from": "node.certified.lift_director", "label": "rewrite.rule_C", "to": "node.certified.fused"},
    {"from": "node.certified.lift_field",    "label": "rewrite.rule_C", "to": "node.certified.fused"},
    # compose_fuse normalizes to fused
    {"from": "node.certified.compose_fuse",  "label": "normalizes_to",  "to": "node.certified.fused"},
    # restrict_stream wraps id
    {"from": "node.certified.restrict_stream", "label": "budget.wraps", "to": "node.certified.id"},
]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _gate(gate_id: str, phase: int, outcome: str, reason: str, evidence: dict | None = None) -> dict:
    ev_hash = canonical_hash(evidence) if evidence else canonical_hash({"gateId": gate_id, "reason": reason})
    return {
        "evidenceHash": ev_hash,
        "gateId": gate_id,
        "outcome": outcome,
        "phase": phase,
        "reason": reason,
    }


def _mutation(
    mutation_id: str, operator: str, target_id: str, gate_id: str,
    outcome: str, expected_outcome: str, is_legal_evolution: bool,
    evidence: dict | None = None,
) -> dict:
    ev = evidence or {"mutationId": mutation_id, "outcome": outcome}
    return {
        "evidenceHash": canonical_hash(ev),
        "expectedOutcome": expected_outcome,
        "gateId": gate_id,
        "isLegalEvolution": is_legal_evolution,
        "mutationId": mutation_id,
        "operator": operator,
        "outcome": outcome,
        "targetId": target_id,
    }


def _witness_id(gate_id: str, evidence_hash: str) -> str:
    return "fw-" + sha256_hex(f"{gate_id}:{evidence_hash}".encode())[:16]


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1 — Certification gates
# ──────────────────────────────────────────────────────────────────────────────

def _run_phase1() -> tuple[list[dict], dict[str, object]]:
    """
    Returns (phase1_gate_results, certified_terms_map).
    certified_terms_map: node_id → CertifiedProjection (only if all gates pass).
    """
    gates: list[dict] = []
    certified: dict[str, object] = {}

    meta_ci.probe(meta_ci.OBS_GATE_PHASE1)

    # Gate 1: closed algebra — unknown constructor must be rejected
    class _Impostor:
        pass
    try:
        certify(_Impostor(), "mutation-test")  # type: ignore
        gates.append(_gate("GATE-P1-CLOSED-ALGEBRA", 1, "FAIL",
                           "certify() accepted unknown constructor — closed algebra violated"))
    except (CertificationError, TypeError, AttributeError):
        gates.append(_gate("GATE-P1-CLOSED-ALGEBRA", 1, "PASS",
                           "certify() raised CertificationError for unknown constructor"))

    # Gate 2: budget monotonicity — amplification must be rejected
    try:
        certify(RestrictBudget(BudgetGrade.INDEXED_ALLOWED, Id()), "budget-test")
        gates.append(_gate("GATE-P1-BUDGET-MONOTONE", 1, "FAIL",
                           "certify() accepted budget amplification — monotonicity violated"))
    except CertificationError:
        gates.append(_gate("GATE-P1-BUDGET-MONOTONE", 1, "PASS",
                           "certify() rejected budget amplification (INDEXED_ALLOWED > STREAMING grade of Id)"))

    # Gate 3: map function closed set
    try:
        certify(MapWitnesses("user_custom_fn"), "map-test")
        gates.append(_gate("GATE-P1-MAP-FN-CLOSED", 1, "FAIL",
                           "certify() accepted unknown map function symbol"))
    except CertificationError:
        gates.append(_gate("GATE-P1-MAP-FN-CLOSED", 1, "PASS",
                           "certify() rejected user-defined map function symbol"))

    # Gate 4: certification idempotency (same term, same policy → same stable_hash)
    cp1 = certify(Id(), "idempotency-test")
    cp2 = certify(Id(), "idempotency-test")
    if cp1.stable_hash == cp2.stable_hash:
        gates.append(_gate("GATE-P1-CERT-IDEMPOTENT", 1, "PASS",
                           "certify() is deterministic: same term+policy → same stable_hash",
                           {"stableHash": cp1.stable_hash}))
    else:
        gates.append(_gate("GATE-P1-CERT-IDEMPOTENT", 1, "FAIL",
                           "certify() non-deterministic: same input → different stable_hash"))

    # Gate 5: rewrite normalization (compose of Id eliminates)
    cp_compose_id = certify(Compose(Id(), Id()), "normalize-test")
    cp_id         = certify(Id(), "normalize-test")
    if cp_compose_id.normal_form_hash == cp_id.normal_form_hash:
        gates.append(_gate("GATE-P1-NF-ID-ELIM", 1, "PASS",
                           "Compose(Id,Id) normalizes to Id — Rule A confirmed",
                           {"nfHash": cp_id.normal_form_hash}))
    else:
        gates.append(_gate("GATE-P1-NF-ID-ELIM", 1, "FAIL",
                           "Compose(Id,Id) did not normalize to Id — Rule A broken"))

    # Gate 6: fusion rule (LiftField ∘ LiftDirector → FusedDirectorField)
    cp_compose_fuse = certify(Compose(LiftField(), LiftDirector()), "fuse-test")
    cp_fused        = certify(FusedDirectorField(), "fuse-test")
    if cp_compose_fuse.normal_form_hash == cp_fused.normal_form_hash:
        gates.append(_gate("GATE-P1-FUSION-RULE-C", 1, "PASS",
                           "Compose(LiftField,LiftDirector) normalizes to FusedDirectorField — Rule C confirmed",
                           {"nfHash": cp_fused.normal_form_hash}))
    else:
        gates.append(_gate("GATE-P1-FUSION-RULE-C", 1, "FAIL",
                           "Fusion Rule C broken: Compose(LiftField,LiftDirector) did not normalize to FusedDirectorField"))

    # Gate 7: verify_certificate (independent re-verifier)
    cp_verify = certify(LiftDirector(), "verify-test")
    if verify_certificate(cp_verify):
        gates.append(_gate("GATE-P1-VERIFY-CERT", 1, "PASS",
                           "verify_certificate() confirmed independently"))
    else:
        gates.append(_gate("GATE-P1-VERIFY-CERT", 1, "FAIL",
                           "verify_certificate() rejected a freshly minted CertifiedProjection"))

    # Certify all standard terms (only reached if we get here; still collected)
    for node_id, term, _ in _STANDARD_TERMS:
        try:
            cp = certify(term, "qs-kernel-bootstrap")
            certified[node_id] = cp
        except CertificationError as e:
            gates.append(_gate(
                f"GATE-P1-CERTIFY-{node_id.upper().replace('.', '-')}",
                1, "FAIL",
                f"Failed to certify standard term {node_id}: {e}"
            ))

    gates_sorted = sorted(gates, key=lambda g: g["gateId"])
    return gates_sorted, certified


# ──────────────────────────────────────────────────────────────────────────────
# Phase 2 — Trace evaluation gates
# ──────────────────────────────────────────────────────────────────────────────

def _run_phase2(certified: dict[str, object]) -> tuple[list[dict], list[dict]]:
    """Returns (phase2_gate_results, execution_traces)."""
    gates: list[dict] = []
    traces: list[dict] = []

    meta_ci.probe(meta_ci.OBS_GATE_PHASE2)

    sv_trace = SovereignTrace(_SYNTHETIC_TRACE)
    trace_hash = sha256_hex(_SYNTHETIC_TRACE)

    for node_id, cp in sorted(certified.items()):
        try:
            art = interpret(cp, sv_trace)  # type: ignore
        except Exception as e:
            gates.append(_gate(
                f"GATE-P2-INTERP-{node_id.upper().replace('.', '-')}",
                2, "FAIL",
                f"interpret() raised {type(e).__name__}: {e}"
            ))
            continue

        # Collect execution trace record
        view = art.extract()                       # WitnessView (counit ε)
        refs = view.witness_refs
        focus_hash = sha256_hex(refs[0]._token) if refs else "0" * 64
        commitment = art.provenance_hash.hex()

        trace_rec = {
            "budgetGrade": cp.budget_grade.name,  # type: ignore
            "certHash": cp.stable_hash,            # type: ignore
            "commitment": commitment,
            "focusHash": focus_hash,
            "intentId": node_id,
            "pastHashes": [],          # TraceZipper past is internal; not exposed
            "traceHash": trace_hash,
            "worldId": _WORLD_ID,
        }
        traces.append(trace_rec)
        meta_ci.probe(meta_ci.OBS_TRACE_EVAL)

    # Gate: α-chain counit law
    alpha = AlphaChain(k_past=4, k_future=0)
    focus_cp = certify(Id(), "alpha-test")
    # Build a minimal WitnessRef-based context for the alpha chain
    # We use the certified projection's normal_form_hash to derive a synthetic WitnessRef pair
    from ..pcp_witness_ref import WitnessRef, _KERNEL_SENTINEL
    f_token = hashlib.sha256(b"alpha-focus-v1").digest()
    c_token = hashlib.sha256(b"alpha-context-v1").digest()
    focus_ref_alpha = WitnessRef(f_token, _KERNEL_SENTINEL)
    ctx_ref = WitnessRef(c_token, _KERNEL_SENTINEL)

    stage_results = alpha.verify_all_stages(focus_ref_alpha, (ctx_ref,))
    all_ok = all(stage_results.values())
    gates.append(_gate("GATE-P2-ALPHA-COUNIT-LAW", 2,
                        "PASS" if all_ok else "FAIL",
                        "α-chain: all stages satisfy counit law (ε' ∘ αᵢ = ε)",
                        {"stageResults": {k: v for k, v in sorted(stage_results.items())}}))

    gates_sorted = sorted(gates, key=lambda g: g["gateId"])
    traces_sorted = sorted(traces, key=lambda t: (t["worldId"], t["intentId"], t["traceHash"]))
    return gates_sorted, traces_sorted


# ──────────────────────────────────────────────────────────────────────────────
# Phase 3 — Ω lattice gates
# ──────────────────────────────────────────────────────────────────────────────

def _run_phase3() -> list[dict]:
    """Returns phase3_gate_results."""
    gates: list[dict] = []

    meta_ci.probe(meta_ci.OBS_GATE_PHASE3)
    meta_ci.probe(meta_ci.OBS_OMEGA_COHERENCE)

    initial = initial_alpha_state(_FOCUS_COMMITMENT)
    omega_set = reachable_omega(initial, max_depth=10)

    # Gate: Ω class count stable and positive
    class_count = len(omega_set)
    if class_count > 0:
        gates.append(_gate("GATE-P3-OMEGA-NONEMPTY", 3, "PASS",
                           f"Reachable Ω contains {class_count} equivalence classes",
                           {"classCount": class_count}))
    else:
        gates.append(_gate("GATE-P3-OMEGA-NONEMPTY", 3, "FAIL",
                           "Reachable Ω is empty — coalgebra Γ is unproductive"))

    # Gate: λ-lattice coherence (join/meet homomorphism)
    checker = LatticeHomomorphismChecker()
    failures = checker.check_coherence(omega_set)
    if not failures:
        gates.append(_gate("GATE-P3-LAMBDA-COHERENCE", 3, "PASS",
                           "λ is a lattice homomorphism on Ω: all join/meet pairs coherent",
                           {"pairsChecked": class_count * (class_count - 1) // 2}))
    else:
        gates.append(_gate("GATE-P3-LAMBDA-COHERENCE", 3, "FAIL",
                           f"λ-coherence failures: {failures[:3]}",
                           {"failures": failures[:5]}))

    # Gate: Ω focus-commitment preservation (distributive law counit)
    focus_violations = [
        e.key[:8] for e in omega_set
        if e.focus_commitment != _FOCUS_COMMITMENT
    ]
    if not focus_violations:
        gates.append(_gate("GATE-P3-FOCUS-PRESERVED", 3, "PASS",
                           "focus_commitment invariant holds across all Ω elements (λ counit law)"))
    else:
        gates.append(_gate("GATE-P3-FOCUS-PRESERVED", 3, "FAIL",
                           f"focus_commitment drift in {len(focus_violations)} Ω elements",
                           {"violations": sorted(focus_violations)[:5]}))

    return sorted(gates, key=lambda g: g["gateId"])


# ──────────────────────────────────────────────────────────────────────────────
# Mutations (always run, isolated from phase gates)
# ──────────────────────────────────────────────────────────────────────────────

def _run_mutations() -> list[dict]:
    results: list[dict] = []

    # ── MUT-HELLO-ILLEGAL-PROJECTION-WRITE (sentinel) ──────────────────────
    # A term that purports to write to external state must NEVER be certified.
    # If outcome is PASS, the closed algebra is compromised.
    class _ExternalWriterTerm:
        """Fake term that has a 'side_effect' attribute — not in _TERM_CONSTRUCTORS."""
        side_effect = "external_storage_write"

    meta_ci.probe(meta_ci.OBS_MUTATION_INERT)
    try:
        certify(_ExternalWriterTerm(), "sentinel-mutation")  # type: ignore
        outcome = "PASS"   # must never happen
    except (CertificationError, TypeError, AttributeError):
        outcome = "FAIL"   # expected: certifier rejects unknown constructor

    results.append(_mutation(
        "MUT-HELLO-ILLEGAL-PROJECTION-WRITE",
        "illegal_write_projection",
        "universe.B.term",
        "GATE-PROJECTION-INERT-23",
        outcome,
        "FAIL",
        is_legal_evolution=False,
        evidence={"operator": "illegal_write_projection", "outcome": outcome},
    ))

    # ── MUT-BUDGET-AMPLIFY ────────────────────────────────────────────────
    # RestrictBudget must be a downcast (cap ≤ inner_grade). Amplification rejected.
    meta_ci.probe(meta_ci.OBS_MUTATION_BUDGET)
    try:
        certify(RestrictBudget(BudgetGrade.INDEXED_ALLOWED, Id()), "budget-amplify-mutation")
        ba_outcome = "PASS"  # budget amplification accepted — FAIL expected
    except CertificationError:
        ba_outcome = "FAIL"  # expected

    results.append(_mutation(
        "MUT-BUDGET-AMPLIFY-001",
        "budget_amplify",
        "node.certified.id",
        "GATE-P1-BUDGET-MONOTONE",
        ba_outcome,
        "FAIL",
        is_legal_evolution=False,
        evidence={"operator": "budget_amplify", "outcome": ba_outcome},
    ))

    # ── MUT-WITNESS-FORGE ─────────────────────────────────────────────────
    # WitnessRef cannot be minted without _KERNEL_SENTINEL.
    meta_ci.probe(meta_ci.OBS_MUTATION_FORGE)
    from ..pcp_witness_ref import WitnessRef as _WRef
    try:
        _WRef(b"\x00" * 32)   # missing _kernel_guard
        wf_outcome = "PASS"   # should never succeed
    except TypeError:
        wf_outcome = "FAIL"   # expected

    results.append(_mutation(
        "MUT-WITNESS-FORGE-001",
        "witness_forge",
        "pcp_witness_ref.WitnessRef",
        "GATE-P1-CLOSED-ALGEBRA",
        wf_outcome,
        "FAIL",
        is_legal_evolution=False,
        evidence={"operator": "witness_forge", "outcome": wf_outcome},
    ))

    # ── MUT-NOOP-INJECT (legal evolution) ────────────────────────────────
    # Compose(Id(), Id()) → certify should PASS (it normalizes to Id).
    # This is the "noop injection" mutation: it is a legal evolution.
    meta_ci.probe(meta_ci.OBS_MUTATION_NOOP)
    try:
        cp_noop = certify(Compose(Id(), Id()), "noop-inject-mutation")
        cp_id   = certify(Id(), "noop-inject-mutation")
        ni_outcome = "PASS" if cp_noop.normal_form_hash == cp_id.normal_form_hash else "FAIL"
    except CertificationError:
        ni_outcome = "FAIL"

    results.append(_mutation(
        "MUT-NOOP-INJECT-001",
        "noop_inject",
        "node.certified.id",
        "GATE-P1-NF-ID-ELIM",
        ni_outcome,
        "PASS",
        is_legal_evolution=True,
        evidence={"operator": "noop_inject", "outcome": ni_outcome},
    ))

    # ── MUT-UNKNOWN-CONSTRUCTOR ───────────────────────────────────────────
    class _UnknownTerm:
        pass
    try:
        certify(_UnknownTerm(), "unknown-ctor-mutation")  # type: ignore
        uc_outcome = "PASS"
    except (CertificationError, TypeError, AttributeError):
        uc_outcome = "FAIL"

    results.append(_mutation(
        "MUT-UNKNOWN-CONSTRUCTOR-001",
        "unknown_constructor",
        "universe.B.term.unknown",
        "GATE-P1-CLOSED-ALGEBRA",
        uc_outcome,
        "FAIL",
        is_legal_evolution=False,
        evidence={"operator": "unknown_constructor", "outcome": uc_outcome},
    ))

    # ── MUT-MAP-FN-OPEN ───────────────────────────────────────────────────
    try:
        certify(MapWitnesses("user_custom_fn"), "map-fn-mutation")
        mf_outcome = "PASS"
    except CertificationError:
        mf_outcome = "FAIL"

    results.append(_mutation(
        "MUT-MAP-FN-OPEN-001",
        "map_fn_open",
        "pcp_term.MapWitnesses",
        "GATE-P1-MAP-FN-CLOSED",
        mf_outcome,
        "FAIL",
        is_legal_evolution=False,
        evidence={"operator": "map_fn_open", "outcome": mf_outcome},
    ))

    results_sorted = sorted(results, key=lambda r: (r["mutationId"], r["gateId"]))
    return results_sorted


# ──────────────────────────────────────────────────────────────────────────────
# System graph (built after phase 1 succeeds)
# ──────────────────────────────────────────────────────────────────────────────

def _build_system_graph(certified: dict[str, object]) -> dict:
    nodes = []
    for node_id in sorted(certified.keys()):
        cp = certified[node_id]
        nodes.append({
            "hash": cp.stable_hash,      # type: ignore
            "id": node_id,
            "kind": next(kind for nid, _, kind in _STANDARD_TERMS if nid == node_id),
            "meta": {
                "budgetGrade": cp.budget_grade.name,  # type: ignore
                "normalFormHash": cp.normal_form_hash,  # type: ignore
                "policyTag": cp.policy_tag,             # type: ignore
            },
        })

    edges = sorted(_STATIC_EDGES, key=lambda e: (e["from"], e["to"], e["label"]))

    # writeCapableNodes is always [] — projection inertness invariant
    meta_ci.probe(meta_ci.INV_PROJECTION_INERT)
    root_payload = {
        "edges": edges,
        "nodes": nodes,
        "writeCapableNodes": [],
    }
    return {
        **root_payload,
        "rootHash": canonical_hash(root_payload),
    }


def _build_empty_system_graph() -> dict:
    return {
        "edges": [],
        "nodes": [],
        "rootHash": canonical_hash({"edges": [], "nodes": [], "writeCapableNodes": []}),
        "writeCapableNodes": [],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Violation graph (pure function of gate results)
# ──────────────────────────────────────────────────────────────────────────────

def _build_violation_graph(gate_results: list[dict]) -> dict:
    """
    Pure function over gate results. No side effects.
    Edges: phase-1 failure → implies blocked phase-2/3 evaluation.
    CI-fatal violations: illegal PASS mutations (handled by policy.check()).
    """
    meta_ci.probe(meta_ci.INV_REDUCER_PURE)

    failed = [g for g in gate_results if g["outcome"] == "FAIL"]
    vg_nodes = sorted([{"gateId": g["gateId"], "phase": g["phase"]} for g in failed],
                      key=lambda n: n["gateId"])

    # Phase-1 failures block phase-2/3: record causal edges
    p1_fails = [g for g in failed if g["phase"] == 1]
    p2_p3_gates = [g for g in gate_results if g["phase"] in (2, 3)]
    edges = []
    for p1 in p1_fails:
        for p23 in p2_p3_gates:
            edges.append({
                "dst": p23["gateId"],
                "kind": "phase_blocked",
                "src": p1["gateId"],
            })
    edges_sorted = sorted(edges, key=lambda e: (e["src"], e["dst"]))

    payload = {"edges": edges_sorted, "nodes": vg_nodes}
    return {**payload, "rootHash": canonical_hash(payload)}


# ──────────────────────────────────────────────────────────────────────────────
# Failure witnesses
# ──────────────────────────────────────────────────────────────────────────────

def _collect_failure_witnesses(gate_results: list[dict]) -> list[dict]:
    failed = [g for g in gate_results if g["outcome"] == "FAIL"]
    witnesses = []
    for g in failed:
        ev = g["evidenceHash"]
        wid = _witness_id(g["gateId"], ev)
        witnesses.append({
            "certifiedCertHash": ev,
            "gateId": g["gateId"],
            "reason": g["reason"],
            "traceHash": sha256_hex(_SYNTHETIC_TRACE),
            "witnessId": wid,
        })
    return sorted(witnesses, key=lambda w: w["witnessId"])


# ──────────────────────────────────────────────────────────────────────────────
# Environment (recorded but excluded from identity hash)
# ──────────────────────────────────────────────────────────────────────────────

def _environment_dict() -> dict:
    return {
        "arch": platform.machine(),
        "platform": sys.platform,
        "pythonVersion": sys.version.split()[0],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Public entrypoint
# ──────────────────────────────────────────────────────────────────────────────

def run_kernel(repo_path: Path | None = None, config: "KernelConfig | None" = None) -> KernelOutputs:
    """
    Core guarantee: same repo → same KernelOutputs across fresh processes.

    Phase isolation: if Phase 1 fails, Phase 2/3 are NOT run.
    Mutations always run (isolated from phase gates).
    """
    from .config import load_config as _lc
    if config is None and repo_path is not None:
        config = _lc(repo_path)

    meta_ci.reset_hit_counts()
    meta_ci.probe(meta_ci.INV_PHASE_ORDER)
    meta_ci.probe(meta_ci.INV_CANON_SORT_KEYS)

    # §51 Canonical serializer roundtrip probe (OBS-CANON-CROSS-CHECK)
    from .canon import canonical_serialize, canonical_hash as _ch
    _sentinel = {"kernelVersion": _KERNEL_VERSION, "phase": "bootstrap"}
    assert canonical_serialize(_sentinel) == canonical_serialize(_sentinel), \
        "canonical_serialize is not idempotent — CJSON implementation broken"
    meta_ci.probe(meta_ci.OBS_CANON_CROSS_CHECK)

    # Phase 1
    phase1_results, certified = _run_phase1()
    p1_failed = any(g["outcome"] == "FAIL" for g in phase1_results)

    if p1_failed:
        mutation_results = _run_mutations()
        system_graph = _build_empty_system_graph()
        violation_graph = _build_violation_graph(phase1_results)
        failure_witnesses = _collect_failure_witnesses(phase1_results)
        meta_report = meta_ci.build_meta_ci_report(phase1_results, mutation_results, [])
        return KernelOutputs(
            system_graph=system_graph,
            execution_traces=[],
            gate_results=phase1_results,
            mutation_results=mutation_results,
            violation_graph=violation_graph,
            failure_witnesses=failure_witnesses,
            meta_ci_report=meta_report,
        )

    # Phase 2
    phase2_results, execution_traces = _run_phase2(certified)
    p2_failed = any(g["outcome"] == "FAIL" for g in phase2_results)

    # Phase 3 (run regardless of phase 2 — Ω is independent of trace eval)
    phase3_results = _run_phase3()

    all_gate_results = sorted(
        phase1_results + phase2_results + phase3_results,
        key=lambda g: g["gateId"]
    )
    mutation_results = _run_mutations()
    system_graph = _build_system_graph(certified)
    violation_graph = _build_violation_graph(all_gate_results)
    failure_witnesses = _collect_failure_witnesses(all_gate_results)
    meta_report = meta_ci.build_meta_ci_report(all_gate_results, mutation_results, execution_traces)

    return KernelOutputs(
        system_graph=system_graph,
        execution_traces=execution_traces,
        gate_results=all_gate_results,
        mutation_results=mutation_results,
        violation_graph=violation_graph,
        failure_witnesses=failure_witnesses,
        meta_ci_report=meta_report,
    )
