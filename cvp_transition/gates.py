"""
The four transition gates.
Each returns (passed: bool, message: str).
"""
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ── Gate 1: Frozen Oracle ──────────────────────────────────────────────────

def gate_frozen_oracle(repo_root: Path) -> tuple[bool, str]:
    """
    Run verify.py (v1.2 portability contract) against the locked baseline.
    Exit 0 = oracle is stable; any other exit = oracle violated.
    """
    result = subprocess.run(
        [sys.executable, "verify.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, "frozen oracle PASS"
    return False, f"frozen oracle FAIL (exit {result.returncode})\n{result.stdout}\n{result.stderr}"


# ── Gate 2: Outcome Preservation ──────────────────────────────────────────

def gate_outcome_preservation(morphism: dict, repo_root: Path) -> tuple[bool, str]:
    """
    For every component declared 'unchanged' in artifact_mapping,
    verify that the live evidence gate still produces the baseline hashes.
    """
    unchanged = [
        k for k, v in morphism.get("artifact_mapping", {}).items()
        if v == "unchanged"
    ]
    if not unchanged:
        return True, "no unchanged components declared — outcome preservation skipped"

    # Running the evidence gate is sufficient: verify.py already checks
    # commit + certificate against the locked baseline for all unchanged components.
    result = subprocess.run(
        [sys.executable, "verify.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, f"outcome preservation PASS (unchanged: {unchanged})"
    return False, (
        f"outcome preservation FAIL for unchanged components {unchanged}\n"
        f"{result.stdout}\n{result.stderr}"
    )


# ── Gate 3: Determinism ────────────────────────────────────────────────────

def gate_determinism(repo_root: Path, runs: int = 3) -> tuple[bool, str]:
    """
    Run the evidence gate N times; all commit + certificate values must be identical.
    """
    import re

    outputs = []
    for _ in range(runs):
        result = subprocess.run(
            [sys.executable, "-u", "-m", "src.evidence_gate"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False, f"evidence gate failed during determinism check\n{result.stderr}"
        outputs.append(result.stdout)

    def extract_field(text: str, field: str) -> str | None:
        m = re.search(rf"^{field}:\s+(\S+)", text, re.MULTILINE)
        return m.group(1) if m else None

    commits = [extract_field(o, "commit") for o in outputs]
    certs   = [extract_field(o, "certificate") for o in outputs]

    if len(set(commits)) != 1 or None in commits:
        return False, f"commit non-determinism across {runs} runs: {commits}"
    if len(set(certs)) != 1 or None in certs:
        return False, f"certificate non-determinism across {runs} runs: {certs}"

    return True, f"determinism PASS ({runs} runs, commit={commits[0][:16]}…)"


# ── Gate 4: Witness Obligation ─────────────────────────────────────────────

def gate_witness(morphism: dict, morphism_path: Path) -> tuple[bool, str]:
    """
    Validate witness records against the Gate 4 schema and admissibility rules.
    Witnesses must be pre-populated from real independent CI runs before submission.
    """
    from .witness import evaluate_gate4, compute_candidate_digest
    witnesses = morphism.get("independent_execution", [])
    digest = compute_candidate_digest(morphism_path)
    return evaluate_gate4(witnesses, digest)
