"""
Runs the existing CVP transition gate CLI (`python -m cvp_transition <morphism>`)
on this machine and assembles a schema-valid Gate 4 witness record from the
result. This is the edge-runtime half of the core/edge split: the gate logic
in cvp_transition/ and src/ is untouched and runs identically on x86_64 CI
and on an ARM64 device (e.g. NVIDIA Jetson) — this module only packages the
outcome of that run into the witness envelope cvp_transition/witness.py
expects.

Does not modify transition_morphism.json. Folding an accepted witness into
independent_execution stays a separate, deliberate step (see witness.py's
own admonition: no synthetic/unreviewed record belongs there).
"""
import hashlib
import platform
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

from cvp_transition.witness import compute_candidate_digest

# Unattended edge device — distinct from a developer workstation ("local")
# and from a CI VM ("github_actions"). See witness.py VALID_RUNNER_TYPES.
RUNNER_TYPE = "other"

_GATE_LINE_RE = re.compile(r"^\[(PASS|FAIL)\]\s+gate\s+(1|2|3b|3|4)\b")


def _environment_block() -> dict:
    return {
        "os": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "runner_type": RUNNER_TYPE,
    }


def _validator_version(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root, capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _parse_gate_results(log: str) -> dict[str, str]:
    results: dict[str, str] = {}
    for line in log.splitlines():
        m = _GATE_LINE_RE.match(line.strip())
        if not m:
            continue
        status, gate = m.group(1), m.group(2)
        key = "gate_3b_byte_exact" if gate == "3b" else f"gate_{gate}"
        results[key] = status
    return results


def run_witness(morphism_path: Path, repo_root: Path) -> tuple[dict, int]:
    """
    Runs the transition gate CLI against morphism_path, capturing stdout +
    exit code, and returns (witness_record, exit_code). The witness reflects
    whatever the run actually produced — including a FAIL verdict and a
    partial results dict on early gate failure. Callers must not treat a
    returned witness as automatically admissible; validate it first.
    """
    command = [sys.executable, "-m", "cvp_transition", str(morphism_path)]
    proc = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)
    log = proc.stdout + proc.stderr

    compat_path = repo_root / "CVP_COMPAT.json"
    compat_sha256 = (
        hashlib.sha256(compat_path.read_bytes()).hexdigest()
        if compat_path.exists() else "0" * 64
    )
    log_sha256 = hashlib.sha256(log.encode("utf-8")).hexdigest()

    witness = {
        "schema_version": "1.0",
        "witness_id": str(uuid.uuid4()),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "candidate_digest": compute_candidate_digest(morphism_path),
        "validator_version": _validator_version(repo_root),
        "environment": _environment_block(),
        "execution": {
            "command": " ".join(command),
            "exit_code": proc.returncode,
        },
        "results": _parse_gate_results(log),
        "verdict": "OK" if proc.returncode == 0 else "FAIL",
        "artifacts": {
            "compat_json_sha256": compat_sha256,
            "log_sha256": log_sha256,
        },
    }
    return witness, proc.returncode
