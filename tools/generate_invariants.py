#!/usr/bin/env python3
"""
Regenerate invariants/*.json from Python implementation constants.

Run after changing witness.py, validate.py, or gate semantics.
CI asserts `git diff --exit-code invariants/` after this runs — any registry
drift from the Python source becomes a structural commit violation, not a test
failure buried in a log.

Usage:
    python tools/generate_invariants.py
"""
import json
import sys
from pathlib import Path

# Ensure repo root is on path so imports work from any working directory
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from cvp_transition.witness import (
    REQUIRED_WITNESS_FIELDS,
    REQUIRED_GATES,
    VALID_RUNNER_TYPES,
    SCHEMA_VERSION,
    DIGEST_EXCLUDED_FIELDS,
)

OUT = REPO_ROOT / "invariants"


def _write(filename: str, data: dict) -> None:
    path = OUT / filename
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(REPO_ROOT)}")


def main() -> None:
    OUT.mkdir(exist_ok=True)

    _write("01_digest_canonicalization.json", {
        "authority": "derived",
        "excluded_fields": sorted(DIGEST_EXCLUDED_FIELDS),
        "hash_algorithm": "sha256",
        "invariant": "digest_value_must_not_change_when_independent_execution_is_mutated",
        "law": "digest = sha256(json.dumps(candidate_spec, sort_keys=True).encode('utf-8'))",
        "name": "candidate_digest_contract",
        "rationale": (
            "Witness material is excluded by type, not convention. "
            "Any presence of witness keys in the digest domain is a hard law violation. "
            "Identity must be computable without any attestation existing."
        ),
        "serialization": {
            "encoding": "utf-8",
            "format": "json",
            "key_ordering": "sorted",
            "null_field_inference": False,
        },
        "source": "cvp_transition/witness.py:compute_candidate_digest",
        "version": "1.0",
    })

    _write("02_witness_contract.json", {
        "admissibility_rules": [
            "candidate_digest matches computed spec digest",
            "validator_version is non-empty",
            "execution.exit_code == 0",
            "results.gate_1 == PASS AND results.gate_2 == PASS AND results.gate_3 == PASS",
            "verdict == OK",
        ],
        "authority": "derived",
        "authority_class": "non_authoritative",
        "binding_rule": "witness.candidate_digest MUST equal compute_candidate_digest(morphism_path)",
        "fingerprint_components": [
            "environment.os",
            "environment.architecture",
            "environment.python_version",
        ],
        "independence_rules": [
            "Rule 1 (anti-replay): witness_id must differ between any pair",
            "Rule 2 (same-machine rejection): identical fingerprint + both runner_type=local -> rejected",
            "Rule 3 (github_actions acceptance): identical fingerprint + both runner_type=github_actions -> accepted (GitHub guarantees distinct VMs)",
            "Rule 4 (fingerprint divergence): different fingerprint -> accepted unconditionally",
        ],
        "mutation_policy": "append_only",
        "name": "witness_contract",
        "required_fields": sorted(REQUIRED_WITNESS_FIELDS),
        "required_gate_results": sorted(REQUIRED_GATES),
        "schema_version_value": SCHEMA_VERSION,
        "source": "cvp_transition/witness.py:REQUIRED_WITNESS_FIELDS",
        "valid_runner_types": sorted(VALID_RUNNER_TYPES),
        "valid_verdicts": ["FAIL", "OK"],
        "version": "1.0",
    })

    _write("03_bootstrap_policy.json", {
        "authority": "derived",
        "bootstrap_witness_constraints": {
            "candidate_digest": "sha256 of morphism spec excluding independent_execution",
            "exit_code": 0,
            "gate_4_result_in_witness": "PENDING",
            "verdict": "OK",
        },
        "cold_start_admissible": False,
        "execution_ordering": [
            "1. load and schema-validate morphism",
            "2. semantic reinterpretation check (removed components in EXTENSION/REFINEMENT)",
            "3. gate_1: frozen oracle (verify.py exit 0)",
            "4. gate_2: outcome preservation (unchanged components still match baseline)",
            "5. gate_3: determinism (evidence gate identical across 3 runs)",
            "6. gate_3b: fixture pack (E1.2 corpus byte-exact)",
            "7. gate_4: witness obligation (>=2 independent admissible witnesses)",
            "8. emit CVP_COMPAT.json",
        ],
        "minimum_admissible_witnesses": 2,
        "name": "bootstrap_policy",
        "rationale": (
            "Gate 4 requires >=2 independent admissible witnesses. In cold-start "
            "(no prior CI runs), bootstrap witnesses must be pre-populated by independent "
            "local executions covering gates 1-3 before the first CI merge. "
            "Gate 4 is PENDING in bootstrap witnesses; they attest to gates 1-3 only."
        ),
        "source": "cvp_transition/witness.py:evaluate_gate4",
        "version": "1.0",
    })

    _write("04_gate_failure_map.json", {
        "authority": "derived",
        "exit_codes": {
            "0": {
                "class": "success",
                "description": "All gates passed; CVP_COMPAT.json emitted",
                "label": "TRANSITION_VALID",
                "triggers": [],
            },
            "1": {
                "class": "contract_violation",
                "description": (
                    "Schema invalid, oracle unstable, outcome preservation failed, "
                    "fixture pack mismatch, or removed component in EXTENSION/REFINEMENT transition"
                ),
                "label": "INVARIANT_VIOLATION",
                "triggers": [
                    "morphism schema validation errors",
                    "gate_1 (frozen oracle) failure",
                    "gate_2 (outcome preservation) failure",
                    "gate_3b (fixture pack) failure",
                    "semantic reinterpretation: removed component in non-BREAKING transition",
                ],
            },
            "2": {
                "class": "cryptographic_invariant_violation",
                "description": (
                    "Evidence gate produced non-identical commit or certificate "
                    "across repeated runs"
                ),
                "label": "DETERMINISM_FAILURE",
                "triggers": [
                    "gate_3 (determinism) failure: commit or certificate varies across 3 runs",
                ],
            },
            "3": {
                "class": "attestation_obligation_violation",
                "description": (
                    "Gate 4 precondition not met: zero witnesses, fewer than 2 admissible "
                    "witnesses, or no independent pair"
                ),
                "label": "WITNESS_FAILURE",
                "triggers": [
                    "independent_execution is empty",
                    "fewer than 2 admissible witness records after schema + admissibility filtering",
                    "all admitted pairs fail independence rules",
                ],
            },
            "4": {
                "class": "breaking_change_in_non_breaking_transition",
                "description": (
                    "Components declared 'removed' in a transition typed EXTENSION or REFINEMENT"
                ),
                "label": "SEMANTIC_REINTERPRETATION",
                "triggers": [
                    "artifact_mapping contains 'removed' value and transition_type is EXTENSION or REFINEMENT",
                ],
            },
        },
        "name": "gate_failure_map",
        "source": "cvp_transition/validate.py:run",
        "version": "1.0",
    })

    print("invariants/ regenerated successfully")


if __name__ == "__main__":
    main()
