"""
qs-kernel CLI entrypoint.

Commands:
  run           Run the kernel once and write artifacts.
  replay-check  Run twice in fresh subprocesses and assert manifests match.
  print-hashes  Print artifact hashes from a previously written run.

Usage:
  python -m src.qs_kernel run --repo . --out /tmp/qs-out [--ci]
  python -m src.qs_kernel replay-check --repo . [--runs 2]
  python -m src.qs_kernel print-hashes --out /tmp/qs-out
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path


def _cmd_run(args: argparse.Namespace) -> int:
    from .runner import run_kernel
    from .artifacts import write_artifacts
    from .policy import check
    from .config import load_config

    repo = Path(args.repo).resolve()
    out  = Path(args.out).resolve()
    config = load_config(repo)

    outputs = run_kernel(repo_path=repo, config=config)
    manifest = write_artifacts(outputs, out)

    report = check(
        outputs_a_manifest=manifest,
        outputs_b_manifest=None,
        gate_results=outputs.gate_results,
        mutation_results=outputs.mutation_results,
        meta_ci_report=outputs.meta_ci_report,
    )

    if args.ci:
        # CI mode: emit compact summary to stdout
        summary = {
            "manifestHash": manifest["manifestHash"],
            "policyOk": report.ok,
            "violations": [v.description for v in report.violations if v.fatal],
        }
        print(json.dumps(summary, sort_keys=True))

    if not report.ok:
        for v in report.violations:
            if v.fatal:
                print(f"CI FAIL [{v.rule}]: {v.description}", file=sys.stderr)
        return 1

    print(f"OK  manifest: {manifest['manifestHash']}")
    return 0


def _cmd_replay_check(args: argparse.Namespace) -> int:
    """
    Spawn `args.runs` fresh subprocesses, each running `qs-kernel run`.
    Compare manifests. Fail if any pair differs.
    """
    import tempfile

    repo = Path(args.repo).resolve()
    n = getattr(args, "runs", 2)

    manifests: list[dict] = []
    tmp_dirs: list[Path] = []

    for i in range(n):
        tmp = Path(tempfile.mkdtemp(prefix=f"qs-run-{i}-"))
        tmp_dirs.append(tmp)

        result = subprocess.run(
            [sys.executable, "-m", "src.qs_kernel", "run",
             "--repo", str(repo), "--out", str(tmp)],
            capture_output=True,
            text=True,
            cwd=str(repo),
        )
        if result.returncode != 0:
            print(f"Run {i}: subprocess failed:\n{result.stderr}", file=sys.stderr)
            return result.returncode

        from .artifacts import load_manifest
        m = load_manifest(tmp)
        manifests.append(m)
        print(f"Run {i}: manifestHash = {m.get('manifestHash', '?')}")

    # Compare all pairs
    hashes = [m.get("manifestHash", "") for m in manifests]
    if len(set(hashes)) != 1:
        print("REPLAY FAIL: manifestHash differs across runs:", file=sys.stderr)
        for i, h in enumerate(hashes):
            print(f"  run {i}: {h}", file=sys.stderr)
        return 2

    print(f"REPLAY OK ({n} runs): {hashes[0]}")
    return 0


def _cmd_print_hashes(args: argparse.Namespace) -> int:
    from .artifacts import print_hashes
    out = Path(args.out).resolve()
    try:
        print_hashes(out)
        return 0
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qs-kernel",
        description="Quantum Star kernel bootstrap runner",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = sub.add_parser("run", help="Run kernel once and write artifacts")
    p_run.add_argument("--repo", default=".", help="Path to repo root")
    p_run.add_argument("--out", default="/tmp/qs-kernel-out", help="Output directory")
    p_run.add_argument("--ci", action="store_true", help="CI mode: JSON summary on stdout")

    # replay-check
    p_replay = sub.add_parser("replay-check", help="Determinism check via fresh subprocesses")
    p_replay.add_argument("--repo", default=".", help="Path to repo root")
    p_replay.add_argument("--runs", type=int, default=2, help="Number of runs (default 2)")

    # print-hashes
    p_hashes = sub.add_parser("print-hashes", help="Print artifact hashes from a run dir")
    p_hashes.add_argument("--out", required=True, help="Output directory from a previous run")

    args = parser.parse_args(argv)

    if args.command == "run":
        return _cmd_run(args)
    if args.command == "replay-check":
        return _cmd_replay_check(args)
    if args.command == "print-hashes":
        return _cmd_print_hashes(args)

    parser.print_help()
    return 1
