"""
CI policy gate: hard-fail rules applied to KernelOutputs.

Rule 1 — Non-determinism: manifestA.manifestHash != manifestB.manifestHash → fail
Rule 2 — Illegal PASS mutation: any mutation with expectedOutcome="FAIL" yields
          outcome="PASS" AND isLegalEvolution=False → fail
Rule 3 — Phase leakage: phase1 gate failed AND (phase2 OR phase3 gates exist) → fail
Rule 4 — Canonical corruption: any artifact fails CJSON validation → fail (enforced
          at write time by canonical_serialize; this gate catches post-hoc corruption)
Rule 5 — Meta-CI coverage: any OBSERVABILITY clause with hitCount=0 → fail (§52)
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class PolicyViolation:
    rule: str
    description: str
    fatal: bool = True


@dataclass
class PolicyReport:
    violations: list[PolicyViolation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(v.fatal for v in self.violations)

    def add(self, rule: str, description: str, fatal: bool = True) -> None:
        self.violations.append(PolicyViolation(rule=rule, description=description, fatal=fatal))

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "violations": [
                {"description": v.description, "fatal": v.fatal, "rule": v.rule}
                for v in self.violations
            ],
        }


def check(
    outputs_a_manifest: dict,
    outputs_b_manifest: dict | None,
    gate_results: list[dict],
    mutation_results: list[dict],
    meta_ci_report: dict | None = None,
) -> PolicyReport:
    """
    Run all CI policy rules.

    outputs_a_manifest: manifest from run A.
    outputs_b_manifest: manifest from run B (for replay check). None skips Rule 1.
    gate_results: all gate results from the kernel run.
    mutation_results: all mutation results.
    meta_ci_report: optional meta-CI coverage report (for Rule 5).
    """
    report = PolicyReport()

    # Rule 1: Non-determinism
    if outputs_b_manifest is not None:
        hash_a = outputs_a_manifest.get("manifestHash", "")
        hash_b = outputs_b_manifest.get("manifestHash", "")
        if hash_a != hash_b:
            report.add(
                "RULE-1-NONDETERMINISM",
                f"manifestHash mismatch: A={hash_a[:16]}… B={hash_b[:16]}…",
                fatal=True,
            )

    # Rule 2: Illegal PASS mutation
    for m in mutation_results:
        if (
            m.get("expectedOutcome") == "FAIL"
            and m.get("outcome") == "PASS"
            and not m.get("isLegalEvolution", False)
        ):
            report.add(
                "RULE-2-ILLEGAL-PASS",
                f"Mutation {m['mutationId']} (gate {m['gateId']}) yielded PASS "
                f"but expectedOutcome=FAIL and isLegalEvolution=False. "
                "System may be semantically compromised.",
                fatal=True,
            )

    # Rule 3: Phase leakage
    p1_failed = any(g["phase"] == 1 and g["outcome"] == "FAIL" for g in gate_results)
    p2_present = any(g["phase"] == 2 for g in gate_results)
    p3_present = any(g["phase"] == 3 for g in gate_results)
    if p1_failed and (p2_present or p3_present):
        report.add(
            "RULE-3-PHASE-LEAKAGE",
            "Phase-1 gate failed but Phase-2/3 gates are present — "
            "phase independence contract violated.",
            fatal=True,
        )

    # Rule 4: Canonical corruption (structural check on manifest)
    if "hashes" not in outputs_a_manifest:
        report.add(
            "RULE-4-CANON-CORRUPTION",
            "manifest.cjson missing 'hashes' key — canonical artifact corrupted.",
            fatal=True,
        )

    # Rule 5: Meta-CI observability coverage (§52)
    if meta_ci_report is not None:
        uncovered = meta_ci_report.get("coverageReport", {}).get("uncoveredObservability", [])
        if uncovered:
            report.add(
                "RULE-5-COVERAGE",
                f"Meta-CI: {len(uncovered)} observability clauses never exercised: "
                + ", ".join(sorted(uncovered)[:5]),
                fatal=True,
            )
        drift_ok = meta_ci_report.get("driftReport", {}).get("ok", True)
        if not drift_ok:
            drifts = meta_ci_report.get("driftReport", {}).get("drifts", [])
            report.add(
                "RULE-5-DRIFT",
                f"Meta-CI drift detected: {[d['driftId'] for d in drifts[:3]]}",
                fatal=True,
            )

    return report
