#!/usr/bin/env python3
"""
Phase 1 Portability Run Contract.

Usage:
    python verify.py

Exit codes:
    0 — PASS (commit and certificate match baseline)
    1 — FAIL (divergence detected; first differing field printed)
    2 — ERROR (implementation or environment issue)

The baseline is the Machine 1 record produced under:
    Linux 6.18.5 x86_64 / Python 3.11.15 (GCC 13.3.0)
"""
import hashlib
import platform
import subprocess
import sys

BASELINE = {
    "commit":      "edb1735ccfa34f0f89206649ce4d1451da280f9563fdc712247bfc7acb81d8a6",
    "certificate": "f56a64c3d9b1b4d8383c7d74693cd55cff8eb4ff077c3646fd2bacb13fbab178",
}

def environment_block() -> str:
    return (
        f"OS: {platform.system()} {platform.release()} {platform.machine()}\n"
        f"Python: {sys.version}\n"
        f"hashlib SHA256 backend: {hashlib.sha256.__module__}"
    )

def run_gate() -> dict:
    from src.types import WitnessPacket304
    from src.ri0 import ri0_replay
    from src.ct0 import ct0_evaluate
    from src.evidence_gate import build_synthetic_trace

    packet = build_synthetic_trace()
    commit_a = ri0_replay(packet)
    commit_b = ri0_replay(packet)

    if commit_a != commit_b:
        print("ERROR: RI-0 non-determinism on this machine", file=sys.stderr)
        sys.exit(2)

    verdict, certificate = ct0_evaluate(commit_a, commit_b, packet.run_id)
    return {
        "commit":      commit_a.hex(),
        "certificate": certificate.certificate_id,
        "verdict":     verdict.status,
    }

def main():
    print("=== Machine 2 Run Contract ===\n")
    print(environment_block())
    print()

    result = run_gate()

    print(f"commit:      {result['commit']}")
    print(f"certificate: {result['certificate']}")
    print(f"verdict:     {result['verdict']}")
    print()

    failures = []
    for field in ("commit", "certificate"):
        if result[field] != BASELINE[field]:
            failures.append(
                f"  FAIL [{field}]\n"
                f"    baseline: {BASELINE[field]}\n"
                f"    observed: {result[field]}"
            )

    if failures:
        print("FAIL — first diverging field:")
        print(failures[0])
        sys.exit(1)
    else:
        print("PASS")
        sys.exit(0)

if __name__ == "__main__":
    main()
