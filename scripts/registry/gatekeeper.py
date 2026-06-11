"""
registry/gatekeeper.py — Gatekeeper v0.1

Thin RCC (RBB Consistency Contract) enforcement middleware.
Called before any CSSR aggregation or cross-artifact analysis.

Typed error codes:
  MIXED_REGISTRY_WINDOW   — multiple registry_hash values in the same window (BLOCK)
  MOVESET_DRIFT           — same registry_hash but different move_set_hash (BLOCK)
  SCHEMA_DRIFT            — mixed schema_major versions in window (BLOCK)
  CSSR_AEC_MIXED_INPUT    — CSSR input spans multiple AECs (BLOCK)
  NO_RBB                  — artifacts lack RBB fields; enforcement skipped (WARN)

Severity semantics:
  BLOCK — aggregation must not proceed; caller should surface as CRITICAL or abort.
  WARN  — aggregation may proceed but caller should log the violation.

Design constraint: Gatekeeper has no state and no side effects. It is a pure
predicate over a list of artifacts. All enforcement decisions are typed so
callers can surface them to the human-readable CSSR summary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set


@dataclass
class GatekeeperViolation:
    code: str
    message: str
    severity: str   # "BLOCK" | "WARN"


class GatekeeperResult:
    def __init__(self, passed: bool, violations: List[GatekeeperViolation]) -> None:
        self.passed = passed
        self.violations = violations

    @property
    def blocked(self) -> bool:
        return not self.passed

    def as_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [
                {"code": v.code, "message": v.message, "severity": v.severity}
                for v in self.violations
            ],
        }


class Gatekeeper:
    """
    Enforces RCC rules before CSSR aggregation.

    Stateless — construct fresh per validation call or reuse across calls.

    RCC rules:
      1. Identity homogeneity:  all artifacts share registry_hash.
      2. Move-set coupling:     identical registry_hash requires identical move_set_hash.
      3. Schema immutability:   schema_major must not change within a window.
      4. AEC integrity:         CSSR aggregation must not span multiple AECs.
    """

    # ── Public interface ───────────────────────────────────────────────────────

    def validate_rbb(self, artifacts: List[Dict[str, Any]]) -> GatekeeperResult:
        """
        Check RCC Rules 1–3 over a list of artifacts.

        Artifacts without an 'rbb' field are silently skipped (backward
        compatible with pre-RBB CVCs). If NO artifact has an RBB, returns a
        WARN rather than a false PASS, so callers know enforcement was skipped.
        """
        violations: List[GatekeeperViolation] = []
        rbbs = [a["rbb"] for a in artifacts if isinstance(a.get("rbb"), dict)]

        if not rbbs:
            violations.append(GatekeeperViolation(
                code="NO_RBB",
                message="No artifacts carry RBB fields; RCC enforcement skipped.",
                severity="WARN",
            ))
            return GatekeeperResult(passed=True, violations=violations)

        registry_hashes: Set[str] = {r.get("registry_hash", "") for r in rbbs}
        schema_majors:   Set[int]  = {r.get("schema_major", -1) for r in rbbs}

        # Rule 1
        if len(registry_hashes) > 1:
            violations.append(GatekeeperViolation(
                code="MIXED_REGISTRY_WINDOW",
                message=(
                    f"Multiple registry_hash values in window — "
                    f"artifacts are from different world registries: "
                    f"{sorted(registry_hashes)}"
                ),
                severity="BLOCK",
            ))

        # Rule 2 (only meaningful if registry is homogeneous)
        if len(registry_hashes) == 1:
            move_set_hashes: Set[str] = {r.get("move_set_hash", "") for r in rbbs}
            if len(move_set_hashes) > 1:
                violations.append(GatekeeperViolation(
                    code="MOVESET_DRIFT",
                    message=(
                        f"Same registry_hash but different move_set_hash — "
                        f"move set changed mid-window: {sorted(move_set_hashes)}"
                    ),
                    severity="BLOCK",
                ))

        # Rule 3
        if len(schema_majors) > 1:
            violations.append(GatekeeperViolation(
                code="SCHEMA_DRIFT",
                message=(
                    f"Mixed schema_major versions in window: "
                    f"{sorted(schema_majors)} — "
                    "hard rejection; re-run under a single schema version."
                ),
                severity="BLOCK",
            ))

        passed = not any(v.severity == "BLOCK" for v in violations)
        return GatekeeperResult(passed=passed, violations=violations)

    def enforce_cssr_input(self, certs: List[Dict[str, Any]]) -> GatekeeperResult:
        """
        Check RCC Rule 4: CSSR aggregation must not span multiple AECs.

        Certs without RBBs do not contribute to AEC computation (backward
        compatible). If the AEC set is ambiguous (some certs have RBBs,
        some don't), the mixed presence itself is reported as a WARN.
        """
        violations: List[GatekeeperViolation] = []

        rbb_certs    = [c for c in certs if isinstance(c.get("rbb"), dict)]
        no_rbb_certs = [c for c in certs if not isinstance(c.get("rbb"), dict)]

        if rbb_certs and no_rbb_certs:
            violations.append(GatekeeperViolation(
                code="PARTIAL_RBB_COVERAGE",
                message=(
                    f"{len(rbb_certs)} cert(s) have RBB, "
                    f"{len(no_rbb_certs)} do not — AEC boundary may be incomplete."
                ),
                severity="WARN",
            ))

        aec_ids: Set[str] = set()
        for cert in rbb_certs:
            rbb = cert["rbb"]
            aec_id = (
                f"{rbb.get('registry_hash', '')}:"
                f"{rbb.get('move_set_hash', '')}:"
                f"{rbb.get('schema_major', 0)}"
            )
            aec_ids.add(aec_id)

        if len(aec_ids) > 1:
            violations.append(GatekeeperViolation(
                code="CSSR_AEC_MIXED_INPUT",
                message=(
                    f"CSSR input spans {len(aec_ids)} distinct AECs — "
                    "cross-AEC aggregation produces undefined stability semantics. "
                    "Partition by AEC before aggregating."
                ),
                severity="BLOCK",
            ))

        passed = not any(v.severity == "BLOCK" for v in violations)
        return GatekeeperResult(passed=passed, violations=violations)
