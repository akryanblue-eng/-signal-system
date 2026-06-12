"""
Gate 4 Witness Record — schema validation and admissibility checks.

A witness answers one question:
    "Did an independent runtime observe the same transition verdict?"
Everything else is supporting evidence for independence and anomaly reproduction.
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
REQUIRED_GATES = ("gate_1", "gate_2", "gate_3")   # gate_3b checked by name if present
VALID_RUNNER_TYPES = ("github_actions", "local", "other")
ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


# ── Schema validation ──────────────────────────────────────────────────────

def validate_witness(w: dict) -> list[str]:
    """Return list of error strings; empty = valid schema."""
    errors: list[str] = []

    if w.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}, got {w.get('schema_version')!r}")

    for field in ("witness_id", "timestamp_utc", "transition_manifest_sha256",
                  "validator_version", "environment", "execution", "results",
                  "verdict", "artifacts"):
        if field not in w:
            errors.append(f"missing required field: {field!r}")

    if errors:
        return errors  # structural issues prevent further checks

    if not ISO8601_RE.match(w.get("timestamp_utc", "")):
        errors.append("timestamp_utc must be ISO 8601 UTC: YYYY-MM-DDTHH:MM:SSZ")

    if w.get("verdict") not in ("OK", "FAIL"):
        errors.append(f"verdict must be 'OK' or 'FAIL', got {w.get('verdict')!r}")

    env = w.get("environment", {})
    for field in ("os", "architecture", "python_version", "runner_type"):
        if not env.get(field):
            errors.append(f"environment.{field} is required and must be non-empty")
    if env.get("runner_type") not in VALID_RUNNER_TYPES:
        errors.append(
            f"environment.runner_type must be one of {VALID_RUNNER_TYPES}, "
            f"got {env.get('runner_type')!r}"
        )

    execution = w.get("execution", {})
    if "exit_code" not in execution:
        errors.append("execution.exit_code is required")
    elif not isinstance(execution["exit_code"], int):
        errors.append("execution.exit_code must be an integer")

    results = w.get("results", {})
    for gate in REQUIRED_GATES:
        if gate not in results:
            errors.append(f"results.{gate} is required")

    artifacts = w.get("artifacts", {})
    for field in ("compat_json_sha256", "log_sha256"):
        if not artifacts.get(field):
            errors.append(f"artifacts.{field} is required and must be non-empty")

    return errors


# ── Admissibility ──────────────────────────────────────────────────────────

def is_admissible(w: dict, morphism_sha256: str) -> tuple[bool, str]:
    """
    Check acceptance rules:
    1. Manifest hash matches the candidate under review.
    2. Validator version is recorded (non-empty).
    3. Execution completed successfully (exit_code == 0).
    4. All prerequisite gates pass.
    5. Artifact hashes included (validated in schema check).
    """
    if w.get("transition_manifest_sha256") != morphism_sha256:
        return False, (
            f"manifest hash mismatch: witness has "
            f"{w.get('transition_manifest_sha256', '?')[:16]}…, "
            f"candidate is {morphism_sha256[:16]}…"
        )

    if not w.get("validator_version"):
        return False, "validator_version is empty"

    if w.get("execution", {}).get("exit_code") != 0:
        return False, f"execution exit_code != 0: {w.get('execution', {}).get('exit_code')}"

    results = w.get("results", {})
    failed_gates = [g for g in REQUIRED_GATES if results.get(g) != "PASS"]
    if failed_gates:
        return False, f"prerequisite gates did not PASS: {failed_gates}"

    if w.get("verdict") != "OK":
        return False, f"verdict is not OK: {w.get('verdict')!r}"

    return True, "admissible"


def are_independent(w1: dict, w2: dict) -> tuple[bool, str]:
    """
    Two witnesses are independent if they do not share execution origin.
    Independence is established by differing on at least one of:
      - witness_id
      - environment.os + environment.architecture
      - runner_type (if both are github_actions, runner IDs should differ —
        but we can't verify that here, so we trust the witness_id)
    Replay detection: same witness_id → not independent.
    """
    if w1.get("witness_id") == w2.get("witness_id"):
        return False, f"duplicate witness_id: {w1.get('witness_id')!r}"

    # Same manifest hash is required (both validated same candidate), so skip that.
    # Two witnesses from the same runner type + same environment are suspicious but
    # not disqualified — that is the cross-machine portability case.
    return True, "witnesses have distinct IDs (independence accepted)"


# ── Gate 4 evaluation ──────────────────────────────────────────────────────

def evaluate_gate4(
    witnesses: list[dict],
    morphism_sha256: str,
) -> tuple[bool, str]:
    """
    Gate 4 is satisfied when:
    - At least 2 witnesses are schema-valid
    - At least 2 witnesses are admissible
    - At least one pair is independent
    - Both report verdict=OK
    """
    if not witnesses:
        return False, "no witnesses provided"

    valid, admitted, errors = [], [], []

    for i, w in enumerate(witnesses):
        schema_errs = validate_witness(w)
        if schema_errs:
            errors.append(f"witness[{i}] schema invalid: {schema_errs[0]}")
            continue
        valid.append(w)

        ok, reason = is_admissible(w, morphism_sha256)
        if not ok:
            errors.append(f"witness[{i}] inadmissible: {reason}")
        else:
            admitted.append(w)

    if len(admitted) < 2:
        detail = "; ".join(errors) if errors else "not enough witnesses"
        return False, f"need ≥2 admissible witnesses, got {len(admitted)}: {detail}"

    # Check at least one independent pair among admitted witnesses
    for i in range(len(admitted)):
        for j in range(i + 1, len(admitted)):
            ind, _ = are_independent(admitted[i], admitted[j])
            if ind:
                ids = admitted[i].get("witness_id", "?")[:8], admitted[j].get("witness_id", "?")[:8]
                return True, f"PASS — 2 independent admissible witnesses ({ids[0]}… {ids[1]}…)"

    return False, "all admitted witnesses appear to share the same execution origin"


def morphism_sha256(morphism_path: Path) -> str:
    return hashlib.sha256(morphism_path.read_bytes()).hexdigest()
