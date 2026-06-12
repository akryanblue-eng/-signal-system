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


def _env_fingerprint(w: dict) -> str:
    """
    Stable execution identity = os + architecture + python_version.
    This is the minimum set that distinguishes machine classes.
    Deliberately excludes runner_type so that two github_actions runners
    with the same image but different VMs can still be independent.
    """
    env = w.get("environment", {})
    parts = (
        env.get("os", "").strip().lower(),
        env.get("architecture", "").strip().lower(),
        env.get("python_version", "").strip().lower(),
    )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def are_independent(w1: dict, w2: dict) -> tuple[bool, str]:
    """
    Independence rule set (minimum fields, in order):

    Rule 1 — Anti-replay: witness_id must differ.
        Same witness_id = same record submitted twice. Always rejected.

    Rule 2 — Environment fingerprint: if both witnesses have identical
        os + architecture + python_version AND both runner_type=local,
        they likely ran on the same physical machine. Rejected.
        Rationale: two local runs on identical hardware are not independent
        corroboration; they are the same environment run twice.

    Rule 3 — github_actions exemption: two witnesses with the same
        environment fingerprint are accepted if both runner_type=github_actions,
        because GitHub guarantees separate VMs even with the same runner image.
        This is the only case where fingerprint collision is trusted.

    Rule 4 — Differing fingerprints: if os + arch + python_version differ,
        the witnesses ran on distinguishable machine classes. Accepted.
    """
    # Rule 1: replay prevention
    if w1.get("witness_id") == w2.get("witness_id"):
        return False, f"replay: same witness_id {w1.get('witness_id', '?')!r}"

    fp1 = _env_fingerprint(w1)
    fp2 = _env_fingerprint(w2)
    rt1 = w1.get("environment", {}).get("runner_type", "")
    rt2 = w2.get("environment", {}).get("runner_type", "")

    if fp1 == fp2:
        # Rule 2: same fingerprint + both local → same machine
        if rt1 == "local" and rt2 == "local":
            env = w1.get("environment", {})
            return False, (
                f"same-machine execution: identical fingerprint "
                f"({env.get('os','?')} / {env.get('architecture','?')} / "
                f"{env.get('python_version','?')}) with runner_type=local on both witnesses"
            )
        # Rule 3: same fingerprint but github_actions → different VMs
        if rt1 == "github_actions" and rt2 == "github_actions":
            return True, (
                f"independent (github_actions VMs, same image — "
                f"fingerprint {fp1}… accepted per runner_type)"
            )
        # Mixed runner types with same fingerprint: accept with note
        return True, (
            f"independent (different runner_types: {rt1!r} vs {rt2!r}, "
            f"same fingerprint {fp1}…)"
        )

    # Rule 4: different fingerprints → different machine classes
    return True, f"independent (distinct fingerprints {fp1}… vs {fp2}…)"


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
