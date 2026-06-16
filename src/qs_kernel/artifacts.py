"""
Artifact serialization: write KernelOutputs to <out>/kernel-run/*.

File layout:
  systemGraph.cjson          — single canonical JSON object
  executionTraces.cjsonl     — line-delimited, sorted by (worldId, intentId, traceHash)
  gateResults.cjsonl         — sorted by gateId
  mutationResults.cjsonl     — sorted by (mutationId, gateId)
  violationGraph.cjson       — single object
  failureWitnesses.cjsonl    — sorted by witnessId
  metaCiReport.cjson         — single object (§54)
  manifest.cjson             — hashes + kernelVersion; environment excluded from hash
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import TYPE_CHECKING

from .canon import canonical_hash, canonical_serialize, cjsonl_bytes, sha256_hex
from .runner import KernelOutputs, _KERNEL_VERSION, _environment_dict

if TYPE_CHECKING:
    pass


_KERNEL_RUN_DIR = "kernel-run"


def _write(path: Path, data: bytes) -> str:
    """Write bytes to path, return sha256 hex of what was written."""
    path.write_bytes(data)
    return sha256_hex(data)


def write_artifacts(outputs: KernelOutputs, out_dir: Path) -> dict:
    """
    Write all artifact files to <out_dir>/kernel-run/.
    Returns the manifest dict (with hashes and identity hash).
    """
    run_dir = out_dir / _KERNEL_RUN_DIR
    run_dir.mkdir(parents=True, exist_ok=True)

    hashes = {}

    # systemGraph.cjson
    hashes["systemGraph.cjson"] = _write(
        run_dir / "systemGraph.cjson",
        canonical_serialize(outputs.system_graph),
    )

    # executionTraces.cjsonl  (sorted by (worldId, intentId, traceHash))
    hashes["executionTraces.cjsonl"] = _write(
        run_dir / "executionTraces.cjsonl",
        cjsonl_bytes(outputs.execution_traces),
    )

    # gateResults.cjsonl  (sorted by gateId)
    hashes["gateResults.cjsonl"] = _write(
        run_dir / "gateResults.cjsonl",
        cjsonl_bytes(outputs.gate_results),
    )

    # mutationResults.cjsonl  (sorted by (mutationId, gateId))
    hashes["mutationResults.cjsonl"] = _write(
        run_dir / "mutationResults.cjsonl",
        cjsonl_bytes(outputs.mutation_results),
    )

    # violationGraph.cjson
    hashes["violationGraph.cjson"] = _write(
        run_dir / "violationGraph.cjson",
        canonical_serialize(outputs.violation_graph),
    )

    # failureWitnesses.cjsonl  (sorted by witnessId)
    hashes["failureWitnesses.cjsonl"] = _write(
        run_dir / "failureWitnesses.cjsonl",
        cjsonl_bytes(outputs.failure_witnesses),
    )

    # metaCiReport.cjson  (§54)
    hashes["metaCiReport.cjson"] = _write(
        run_dir / "metaCiReport.cjson",
        canonical_serialize(outputs.meta_ci_report),
    )

    # Manifest identity = SHA-256 over {kernelVersion, hashes} — environment excluded
    identity_payload = {
        "hashes": hashes,
        "kernelVersion": _KERNEL_VERSION,
    }
    manifest_hash = canonical_hash(identity_payload)

    manifest = {
        **identity_payload,
        "environment": _environment_dict(),    # recorded, not in identity hash
        "manifestHash": manifest_hash,
    }

    _write(run_dir / "manifest.cjson", canonical_serialize(manifest))
    return manifest


def load_manifest(out_dir: Path) -> dict:
    """Load manifest from a previously written artifact directory."""
    manifest_path = out_dir / _KERNEL_RUN_DIR / "manifest.cjson"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest at {manifest_path}")
    return json.loads(manifest_path.read_text("utf-8"))


def print_hashes(out_dir: Path) -> None:
    """Print hashes from a previously written artifact directory to stdout."""
    manifest = load_manifest(out_dir)
    print(f"manifestHash: {manifest.get('manifestHash', '—')}")
    for name, h in sorted(manifest.get("hashes", {}).items()):
        print(f"  {name}: {h}")
