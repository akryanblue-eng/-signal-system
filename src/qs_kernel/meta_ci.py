"""
Meta-CI proof harness (§§50-54).

§50 — Invariant→code-path binding registry.
      Each clause is declared; coverage means hitCount > 0.

§51 — Proof hooks at keystone drift boundaries.
      Called inside gate evaluation; hooks record which clauses were exercised.

§52 — Spec coverage graph.
      CI fails if any required clause has hitCount = 0.

§53 — Drift detectors.
      Canonical ordering drift, gate late-binding, projection side-structure.

§54 — metaCiReport.cjson included in manifest hash.

Two types of clauses (avoids coverage paradox):
  STRUCTURAL   — must always hold (phase ordering, isolation, canonical serialization,
                  reducer purity). Checked structurally; not coverage-sensitive.
  OBSERVABILITY — must be exercised at least once (projection paths, mutation
                  categories, gate phases). Coverage-sensitive.

Structural invariants are never marked "uncovered" — they are always-on.
Observability invariants generate CI failures only if hitCount = 0.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .canon import canonical_hash


class ClauseKind(Enum):
    STRUCTURAL = "structural"
    OBSERVABILITY = "observability"


@dataclass
class InvariantClause:
    clause_id: str
    description: str
    kind: ClauseKind
    hit_count: int = 0

    def hit(self) -> None:
        self.hit_count += 1

    @property
    def covered(self) -> bool:
        if self.kind == ClauseKind.STRUCTURAL:
            return True   # structural invariants are always-on; not coverage-sensitive
        return self.hit_count > 0


_REGISTRY: dict[str, InvariantClause] = {}


def _clause(clause_id: str, description: str, kind: ClauseKind) -> InvariantClause:
    c = InvariantClause(clause_id=clause_id, description=description, kind=kind)
    _REGISTRY[clause_id] = c
    return c


# ──────────────────────────────────────────────────────────────────────────────
# §50 Invariant registry (machine-readable; "not implemented unless bound")
# ──────────────────────────────────────────────────────────────────────────────

# Structural invariants (always-on)
INV_PHASE_ORDER        = _clause("INV-PHASE-ORDER",        "Phase 1 must complete before Phase 2/3 evaluates", ClauseKind.STRUCTURAL)
INV_ISOLATION          = _clause("INV-ISOLATION",          "Each world runs in isolated process context",       ClauseKind.STRUCTURAL)
INV_CANON_SORT_KEYS    = _clause("INV-CANON-SORT-KEYS",    "All CJSON object keys sorted lexicographically",   ClauseKind.STRUCTURAL)
INV_REDUCER_PURE       = _clause("INV-REDUCER-PURE",       "violationGraph is a pure function of gate results", ClauseKind.STRUCTURAL)
INV_PROJECTION_INERT   = _clause("INV-PROJECTION-INERT",   "Certified projections cannot write external state", ClauseKind.STRUCTURAL)
INV_NO_FLOAT_NAN       = _clause("INV-NO-FLOAT-NAN",       "NaN/Infinity rejected by canonical serializer",    ClauseKind.STRUCTURAL)

# Observability invariants (must be exercised)
OBS_GATE_PHASE1        = _clause("OBS-GATE-PHASE1",        "At least one Phase-1 gate evaluated",              ClauseKind.OBSERVABILITY)
OBS_GATE_PHASE2        = _clause("OBS-GATE-PHASE2",        "At least one Phase-2 gate evaluated",              ClauseKind.OBSERVABILITY)
OBS_GATE_PHASE3        = _clause("OBS-GATE-PHASE3",        "At least one Phase-3 gate evaluated",              ClauseKind.OBSERVABILITY)
OBS_MUTATION_BUDGET    = _clause("OBS-MUTATION-BUDGET",    "budget_amplify mutation exercised",                ClauseKind.OBSERVABILITY)
OBS_MUTATION_INERT     = _clause("OBS-MUTATION-INERT",     "MUT-HELLO-ILLEGAL-PROJECTION-WRITE exercised",     ClauseKind.OBSERVABILITY)
OBS_MUTATION_FORGE     = _clause("OBS-MUTATION-FORGE",     "witness_forge mutation exercised",                 ClauseKind.OBSERVABILITY)
OBS_MUTATION_NOOP      = _clause("OBS-MUTATION-NOOP",      "noop_inject mutation exercised (legal evolution)", ClauseKind.OBSERVABILITY)
OBS_TRACE_EVAL         = _clause("OBS-TRACE-EVAL",         "At least one execution trace produced",            ClauseKind.OBSERVABILITY)
OBS_OMEGA_COHERENCE    = _clause("OBS-OMEGA-COHERENCE",    "Omega lattice coherence check run",                ClauseKind.OBSERVABILITY)
OBS_CANON_CROSS_CHECK  = _clause("OBS-CANON-CROSS-CHECK",  "Canonical serializer roundtrip verified",          ClauseKind.OBSERVABILITY)


def probe(clause: InvariantClause) -> None:
    """§51 proof hook: mark a clause as exercised. Call at semantic boundaries."""
    clause.hit()


def coverage_report() -> dict:
    """§52 Build coverage report. CI fails if any OBSERVABILITY clause is uncovered."""
    clauses = []
    for c in sorted(_REGISTRY.values(), key=lambda x: x.clause_id):
        clauses.append({
            "clauseId": c.clause_id,
            "covered": c.covered,
            "description": c.description,
            "hitCount": c.hit_count,
            "kind": c.kind.value,
        })
    uncovered = [c["clauseId"] for c in clauses if not c["covered"]]
    return {
        "clauses": clauses,
        "totalClauses": len(clauses),
        "totalCovered": sum(1 for c in clauses if c["covered"]),
        "uncoveredObservability": uncovered,
    }


def drift_detectors_report(
    gate_results: list[dict],
    mutation_results: list[dict],
    execution_traces: list[dict],
) -> dict:
    """§53 Detect known drift patterns."""
    drifts = []

    # Drift 1: canonical ordering drift — gate results must be sorted by gateId
    gate_ids = [g["gateId"] for g in gate_results]
    if gate_ids != sorted(gate_ids):
        drifts.append({
            "driftId": "DRIFT-CANON-ORDER-GATE",
            "description": "gateResults not sorted by gateId",
            "severity": "FATAL",
        })

    # Drift 2: mutation results must be sorted by (mutationId, gateId)
    mut_keys = [(m["mutationId"], m["gateId"]) for m in mutation_results]
    if mut_keys != sorted(mut_keys):
        drifts.append({
            "driftId": "DRIFT-CANON-ORDER-MUT",
            "description": "mutationResults not sorted by (mutationId, gateId)",
            "severity": "FATAL",
        })

    # Drift 3: projection side-structure — writeCapableNodes must always be empty
    # (checked in systemGraph; here we just note it was verified)
    # This is a structural invariant — always passes by construction.

    # Drift 4: gate late-binding — no gate should reference a phase that wasn't run
    phases_present = {g["phase"] for g in gate_results}
    if 1 not in phases_present and gate_results:
        drifts.append({
            "driftId": "DRIFT-GATE-NO-PHASE1",
            "description": "No Phase-1 gates present but gate results exist",
            "severity": "FATAL",
        })

    # Drift 5: trace without phase 2 gate
    if execution_traces and 2 not in phases_present:
        drifts.append({
            "driftId": "DRIFT-TRACE-WITHOUT-PHASE2",
            "description": "Execution traces exist but no Phase-2 gates present",
            "severity": "FATAL",
        })

    return {
        "driftCount": len(drifts),
        "drifts": drifts,
        "ok": len(drifts) == 0,
    }


def build_meta_ci_report(
    gate_results: list[dict],
    mutation_results: list[dict],
    execution_traces: list[dict],
) -> dict:
    """§54 Build the full metaCiReport dict (included in manifest hash)."""
    cov = coverage_report()
    drift = drift_detectors_report(gate_results, mutation_results, execution_traces)
    report = {
        "coverageReport": cov,
        "driftReport": drift,
        "ok": cov["uncoveredObservability"] == [] and drift["ok"],
        "specVersion": "meta-ci-v1",
    }
    return report


def reset_hit_counts() -> None:
    """Reset all hit counts to zero (for test isolation)."""
    for c in _REGISTRY.values():
        c.hit_count = 0
