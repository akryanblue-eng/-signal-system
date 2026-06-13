"""
Gate 4 Witness Record — schema validation and admissibility checks.

A witness answers one question:
    "Did an independent runtime observe the same transition verdict?"
Everything else is supporting evidence for independence and anomaly reproduction.

Gate 4 formal predicate:
    Gate 4 is satisfied iff there exist witness records A and B such that:
        A.candidate_digest = B.candidate_digest    (same candidate)
        A.verdict = OK                             (A accepted the transition)
        B.verdict = OK                             (B accepted the transition)
        independent(A, B)                          (distinct execution origins)

    All four conditions are computational:
        candidate_digest  — sha256 of transition_morphism.json
        verdict           — string equality
        independent(A, B) — rule set in are_independent()

    The gate does not admit partial satisfaction. All four conditions must hold
    for a single admitted pair.
"""
import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = "1.0"
REQUIRED_GATES = ("gate_1", "gate_2", "gate_3")
VALID_RUNNER_TYPES = ("github_actions", "local", "other")
ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


# ── Schema validation ──────────────────────────────────────────────────────

def validate_witness(w: dict) -> list[str]:
    """Return list of error strings; empty = valid schema."""
    errors: list[str] = []

    if w.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}, got {w.get('schema_version')!r}")

    for field in ("witness_id", "timestamp_utc", "candidate_digest",
                  "validator_version", "environment", "execution", "results",
                  "verdict", "artifacts"):
        if field not in w:
            errors.append(f"missing required field: {field!r}")

    if errors:
        return errors

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

def is_admissible(w: dict, expected_digest: str) -> tuple[bool, str]:
    """
    Acceptance rules (all must pass):
    1. candidate_digest matches the transition manifest under review.
    2. validator_version is recorded (non-empty).
    3. exit_code == 0.
    4. All prerequisite gates report PASS.
    5. Artifact hashes present (enforced by schema validation).
    """
    if w.get("candidate_digest") != expected_digest:
        return False, (
            f"candidate_digest mismatch: witness has "
            f"{w.get('candidate_digest', '?')[:16]}…, "
            f"candidate is {expected_digest[:16]}…"
        )

    if not w.get("validator_version"):
        return False, "validator_version is empty"

    if w.get("execution", {}).get("exit_code") != 0:
        return False, f"exit_code != 0: {w.get('execution', {}).get('exit_code')}"

    failed = [g for g in REQUIRED_GATES if w.get("results", {}).get(g) != "PASS"]
    if failed:
        return False, f"prerequisite gates did not PASS: {failed}"

    if w.get("verdict") != "OK":
        return False, f"verdict is not OK: {w.get('verdict')!r}"

    return True, "admissible"


# ── Independence ───────────────────────────────────────────────────────────

def _env_fingerprint(w: dict) -> str:
    """
    Stable execution identity = os + architecture + python_version.
    Minimum set that distinguishes machine classes.
    Excludes runner_type so fingerprint is machine-class-based.
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
    Independence rule set (minimum fields, evaluated in order):

    Rule 1 — Anti-replay: witness_id must differ.
        Same witness_id = same record submitted twice. Always rejected.

    Rule 2 — Same fingerprint + both local → same machine.
        os + arch + python identical and runner_type=local on both = likely
        the same physical machine. Not independent corroboration.

    Rule 3 — Same fingerprint + both github_actions → accepted.
        GitHub guarantees distinct VMs even with the same runner image.

    Rule 4 — Different fingerprints → accepted.
        os/arch/python differ = distinguishable machine classes.
    """
    if w1.get("witness_id") == w2.get("witness_id"):
        return False, f"replay: same witness_id {w1.get('witness_id', '?')!r}"

    fp1, fp2 = _env_fingerprint(w1), _env_fingerprint(w2)
    rt1 = w1.get("environment", {}).get("runner_type", "")
    rt2 = w2.get("environment", {}).get("runner_type", "")

    if fp1 == fp2:
        if rt1 == "local" and rt2 == "local":
            env = w1.get("environment", {})
            return False, (
                f"same-machine: fingerprint ({env.get('os','?')} / "
                f"{env.get('architecture','?')} / {env.get('python_version','?')}) "
                f"with runner_type=local on both"
            )
        if rt1 == "github_actions" and rt2 == "github_actions":
            return True, f"independent (github_actions VMs, fingerprint {fp1}…)"
        return True, f"independent (runner_types {rt1!r} vs {rt2!r}, fingerprint {fp1}…)"

    return True, f"independent (fingerprints {fp1}… vs {fp2}…)"


# ── Gate 4 evaluation ──────────────────────────────────────────────────────

def evaluate_gate4(witnesses: list[dict], candidate_digest: str) -> tuple[bool, str]:
    """
    Formal predicate:
        ∃ A, B ∈ witnesses :
            A.candidate_digest = B.candidate_digest = candidate_digest
            ∧ A.verdict = OK
            ∧ B.verdict = OK
            ∧ independent(A, B)

    Implementation:
    1. Validate schema of each witness.
    2. Check admissibility of each valid witness (enforces candidate_digest match,
       exit_code=0, prerequisite gates, and verdict=OK).
    3. Among admitted witnesses, find one independent pair.
    4. The explicit candidate_digest equality check (A.cd = B.cd) is satisfied
       transitively: both must equal the single candidate_digest argument.
    """
    if not witnesses:
        return False, "no witnesses provided"

    admitted: list[dict] = []
    errors: list[str] = []

    for i, w in enumerate(witnesses):
        schema_errs = validate_witness(w)
        if schema_errs:
            errors.append(f"witness[{i}] schema invalid: {schema_errs[0]}")
            continue

        ok, reason = is_admissible(w, candidate_digest)
        if not ok:
            errors.append(f"witness[{i}] inadmissible: {reason}")
        else:
            admitted.append(w)

    if len(admitted) < 2:
        detail = "; ".join(errors) if errors else "insufficient witnesses"
        return False, f"need ≥2 admissible witnesses, got {len(admitted)}: {detail}"

    for i in range(len(admitted)):
        for j in range(i + 1, len(admitted)):
            ind, ind_msg = are_independent(admitted[i], admitted[j])
            if ind:
                ids = admitted[i]["witness_id"][:8], admitted[j]["witness_id"][:8]
                return True, f"PASS — {ids[0]}… × {ids[1]}… — {ind_msg}"

    return False, "no independent pair found among admitted witnesses"


def compute_candidate_digest(morphism_path: Path) -> str:
    return hashlib.sha256(morphism_path.read_bytes()).hexdigest()
