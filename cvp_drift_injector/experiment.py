import hashlib
import sys
from dataclasses import dataclass, field
from typing import Optional

from .config import DriftConfig
from .engine import apply_drift


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def config_to_severity(config: DriftConfig) -> float:
    return sum([
        config.chunk_split,
        config.interleave_noise,
        config.shuffle_non_cvl,
        config.utf8_corrupt,
        config.line_ending_mutation,
        config.flush_delay,
        config.partial_write,
        config.noise_injection,
    ]) / 8.0


@dataclass
class ExperimentResult:
    drift_type: str
    seed: int
    input_sha256: str
    output_sha256: str
    severity: float
    cvl1_recovered: Optional[dict]   # filled by caller after CVL1 extraction
    canonical_hash_match: Optional[bool]
    outcome: str                      # "PASS" | "FAIL" | "PENDING"
    note: str = ""


def run_experiment(
    stream: bytes,
    config: DriftConfig,
    drift_name: str,
    seed: int = 42,
) -> tuple[bytes, ExperimentResult]:
    """
    Apply drift and return (corrupted_stream, result).
    CVL1 extraction and canonical_hash_match are filled in by the caller.
    """
    corrupted = apply_drift(stream, config, seed)
    result = ExperimentResult(
        drift_type=drift_name,
        seed=seed,
        input_sha256=_sha256_hex(stream),
        output_sha256=_sha256_hex(corrupted),
        severity=config_to_severity(config),
        cvl1_recovered=None,
        canonical_hash_match=None,
        outcome="PENDING",
        note="",
    )
    return corrupted, result
