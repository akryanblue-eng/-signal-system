"""
CVP-v1.2 Experiment Runner

Runs the full drift × seed matrix against a canonical stream,
extracts CVL1 fields from each perturbed output, and computes stability_score.
"""
import sys
from typing import Callable

from .config import DriftConfig
from .experiment import ExperimentResult, run_experiment
from .engine import apply_drift


def run_stability_sweep(
    stream: bytes,
    configs: list[tuple[str, DriftConfig]],
    seeds: list[int],
    cvl1_extractor: Callable[[bytes], dict],
    expected: dict[str, str],
    verbose: bool = True,
) -> float:
    """
    For each (config, seed) pair:
      1. Apply drift
      2. Extract CVL1 fields
      3. Determine outcome: PASS if all expected fields match, FAIL otherwise

    stability_score = PASS_count / total_experiments
    """
    results: list[ExperimentResult] = []

    for drift_name, config in configs:
        for seed in seeds:
            corrupted, result = run_experiment(stream, config, drift_name, seed)
            fields = cvl1_extractor(corrupted)
            result.cvl1_recovered = fields

            match = all(fields.get(k) == v for k, v in expected.items())
            result.canonical_hash_match = match
            result.outcome = "PASS" if match else "FAIL"
            if not match:
                mismatches = {k: fields.get(k) for k in expected if fields.get(k) != expected[k]}
                result.note = f"mismatch: {mismatches}"
            else:
                result.note = "all fields match baseline"
            results.append(result)

    passed = sum(1 for r in results if r.outcome == "PASS")
    total = len(results)
    score = passed / total if total else 0.0

    if verbose:
        print(f"{'Drift':<22} {'Seed':<8} {'Sev':>4}  {'Outcome':<6}  Note")
        print("-" * 80)
        for r in results:
            print(f"{r.drift_type:<22} {r.seed:<8} {r.severity:>4.2f}  {r.outcome:<6}  {r.note}")
        print("-" * 80)
        print(f"stability_score = {passed}/{total} = {score:.3f}")

    return score
