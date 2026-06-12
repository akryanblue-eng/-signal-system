"""
CVL1 Canonical Line Immunity Test — CVP-v1.2

Runs all drift injectors against a canonical log, attempts CVL1 extraction
on each perturbed variant, and computes a stability score.

stability_score = correct_extractions / total_perturbations

A perturbation is "correct" if:
  - For non-destructive injectors: commit + certificate extracted and match baseline
  - For destructive injectors (truncate*, case_mangle*): extraction correctly returns None
    (fail-closed behavior — no false extraction)
"""
import sys
from dataclasses import dataclass

from .drift import ALL_INJECTORS, corrupt_encoding
from .cvl1 import extract
from .evidence_gate import build_synthetic_trace
from .ri0 import ri0_replay
from .ct0 import ct0_evaluate

DESTRUCTIVE = frozenset({
    "truncate_75pct",
    "truncate_50pct",
    "truncate_25pct",
    "case_mangle_keys",
})

# Injectors where corruption may land in canonical field bytes.
# Correct behavior: either extracts correctly OR returns None (fail-closed).
# A wrong non-None value would be a FAIL.
PARTIAL_DESTRUCTIVE = frozenset({
    "corrupt_encoding",
})


@dataclass
class InjectorResult:
    name: str
    category: str           # "resilient" | "destructive"
    perturbed_log: str
    commit_extracted: str | None
    cert_extracted: str | None
    expected_commit: str
    expected_cert: str
    outcome: str            # "PASS" | "FAIL"
    note: str


def run_immunity_test(verbose: bool = True) -> float:
    # Generate canonical log from live execution
    packet = build_synthetic_trace()
    commit_bytes = ri0_replay(packet)
    _, certificate = ct0_evaluate(commit_bytes, commit_bytes, packet.run_id)

    expected_commit = commit_bytes.hex()
    expected_cert   = certificate.certificate_id

    # Build canonical log string (matches evidence_gate output format)
    import hashlib
    trace_id = hashlib.sha256(
        packet.run_id.encode() + packet.bundle_hash
    ).hexdigest()[:16].upper()

    import pathlib
    h = hashlib.sha256()
    src = pathlib.Path(__file__).parent
    for f in sorted(src.glob("*.py")):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    build_id = h.hexdigest()[:16].upper()

    canonical_log = (
        f"run_id:      {packet.run_id}\n"
        f"build_id:    {build_id}\n"
        f"trace_id:    {trace_id}\n"
        f"commit:      {expected_commit}\n"
        f"certificate: {expected_cert}\n"
        f"verdict:     OK\n"
    )

    results: list[InjectorResult] = []

    # Run string-output injectors
    for name, injector in ALL_INJECTORS:
        perturbed = injector(canonical_log)
        fields = extract(perturbed)
        commit_got = fields.get("commit")
        cert_got   = fields.get("certificate")
        destructive = name in DESTRUCTIVE

        if destructive:
            # Correct behavior: at least one critical field is None (verifier fails-closed).
            # truncate_75pct: commit survives but cert is cut off → cert=None → fail-closed.
            # truncate_50/25pct, case_mangle: both fields None.
            ok = commit_got is None or cert_got is None
            outcome = "PASS" if ok else "FAIL"
            note = "fail-closed (≥1 field None)" if ok else f"unexpected full extraction: commit={commit_got}"
        else:
            ok = commit_got == expected_commit and cert_got == expected_cert
            outcome = "PASS" if ok else "FAIL"
            note = "values match baseline" if ok else f"commit={commit_got} cert={cert_got}"

        results.append(InjectorResult(
            name=name,
            category="destructive" if destructive else "resilient",
            perturbed_log=perturbed,
            commit_extracted=commit_got,
            cert_extracted=cert_got,
            expected_commit=expected_commit,
            expected_cert=expected_cert,
            outcome=outcome,
            note=note,
        ))

    # corrupt_encoding returns bytes — corruption may land in canonical field bytes.
    # Correct: either extracts correct values OR returns None (fail-closed).
    # Wrong: extracts a non-None value that differs from baseline.
    corrupt_bytes = corrupt_encoding(canonical_log)
    fields = extract(corrupt_bytes)
    commit_got = fields.get("commit")
    cert_got   = fields.get("certificate")
    commit_ok = commit_got is None or commit_got == expected_commit
    cert_ok   = cert_got   is None or cert_got   == expected_cert
    ok = commit_ok and cert_ok
    if commit_got is None or cert_got is None:
        note = "fail-closed (corruption hit canonical bytes — correct)"
    else:
        note = "values match baseline despite encoding noise"
    results.append(InjectorResult(
        name="corrupt_encoding",
        category="partial-destructive",
        perturbed_log="<bytes>",
        commit_extracted=commit_got,
        cert_extracted=cert_got,
        expected_commit=expected_commit,
        expected_cert=expected_cert,
        outcome="PASS" if ok else "FAIL",
        note=note if ok else f"WRONG value extracted: commit={commit_got}",
    ))

    passed = sum(1 for r in results if r.outcome == "PASS")
    total  = len(results)
    score  = passed / total

    if verbose:
        print(f"{'Injector':<22} {'Category':<12} {'Outcome':<6}  Note")
        print("-" * 72)
        for r in results:
            print(f"{r.name:<22} {r.category:<12} {r.outcome:<6}  {r.note}")
        print("-" * 72)
        print(f"stability_score = {passed}/{total} = {score:.3f}")

    return score


if __name__ == "__main__":
    score = run_immunity_test(verbose=True)
    sys.exit(0 if score == 1.0 else 1)
