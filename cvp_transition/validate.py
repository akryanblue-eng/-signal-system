"""
cvp.transition.validate — CVP Transition Gate CLI

Usage:
    python -m cvp_transition.validate <transition_morphism.json>

Exit codes:
    0 — valid morphism (all gates pass)
    1 — invariant violation (schema or compatibility check failed)
    2 — determinism failure
    3 — witness failure
    4 — semantic reinterpretation detected (breaking changes in non-BREAKING transition)
"""
import json
import sys
from pathlib import Path

from .schema import validate_schema, load
from .gates import (
    gate_frozen_oracle,
    gate_outcome_preservation,
    gate_determinism,
    gate_witness,
)


def run(morphism_path: Path, repo_root: Path) -> int:
    print(f"CVP Transition Gate — {morphism_path.name}\n")

    # ── Load + schema validation ───────────────────────────────────────────
    try:
        morphism = load(morphism_path)
    except Exception as e:
        print(f"[FAIL] cannot load morphism file: {e}")
        return 1

    schema_errors = validate_schema(morphism)
    if schema_errors:
        print("[FAIL] schema validation errors:")
        for e in schema_errors:
            print(f"  - {e}")
        return 1
    print(f"[PASS] schema valid  (transition_type={morphism['transition_type']!r}  "
          f"{morphism['from_version']} → {morphism['to_version']})")

    # ── Semantic reinterpretation check ───────────────────────────────────
    # EXTENSION/REFINEMENT declaring breaking changes is caught by schema.
    # Additional check: any component mapping of 'removed' is always a breaking change.
    removed = [k for k, v in morphism.get("artifact_mapping", {}).items() if v == "removed"]
    if removed and morphism.get("transition_type") in ("EXTENSION", "REFINEMENT"):
        print(f"[FAIL] semantic reinterpretation: components removed in "
              f"{morphism['transition_type']} transition: {removed}")
        return 4
    if removed:
        print(f"[WARN] components removed: {removed} — valid only for BREAKING/REPLACEMENT")

    # ── Gate 1: Frozen oracle ──────────────────────────────────────────────
    ok, msg = gate_frozen_oracle(repo_root)
    print(f"[{'PASS' if ok else 'FAIL'}] gate 1 — frozen oracle: {msg}")
    if not ok:
        return 1

    # ── Gate 2: Outcome preservation ──────────────────────────────────────
    ok, msg = gate_outcome_preservation(morphism, repo_root)
    print(f"[{'PASS' if ok else 'FAIL'}] gate 2 — outcome preservation: {msg}")
    if not ok:
        return 1

    # ── Gate 3: Determinism ────────────────────────────────────────────────
    ok, msg = gate_determinism(repo_root)
    print(f"[{'PASS' if ok else 'FAIL'}] gate 3 — determinism: {msg}")
    if not ok:
        return 2

    # ── Gate 4: Witness obligation ─────────────────────────────────────────
    ok, msg = gate_witness(morphism)
    print(f"[{'PASS' if ok else 'FAIL'}] gate 4 — witness: {msg}")
    if not ok:
        return 3

    print("\nTRANSITION VALID — all gates passed")
    return 0


def main():
    if len(sys.argv) < 2:
        print(f"usage: python -m cvp_transition.validate <transition_morphism.json>",
              file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        sys.exit(1)

    repo_root = Path(__file__).parent.parent
    sys.exit(run(path, repo_root))


if __name__ == "__main__":
    main()
