"""CVL1 immunity: canonical fields survive resilient drift injectors."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from cvp_drift_injector.engine import apply_drift
from cvp_drift_injector.config import DriftConfig
from src.cvl1 import extract

FIXTURE = pathlib.Path(__file__).parent.parent / "fixtures" / "sample_stdout_1.txt"
BASELINE_COMMIT = "edb1735ccfa34f0f89206649ce4d1451da280f9563fdc712247bfc7acb81d8a6"
BASELINE_CERT   = "f56a64c3d9b1b4d8383c7d74693cd55cff8eb4ff077c3646fd2bacb13fbab178"


def _stream() -> bytes:
    return FIXTURE.read_bytes()


def _check(config: DriftConfig, seed: int = 42):
    corrupted = apply_drift(_stream(), config, seed)
    fields = extract(corrupted)
    assert fields["commit"]      == BASELINE_COMMIT, f"commit mismatch after {config}"
    assert fields["certificate"] == BASELINE_CERT,   f"cert mismatch after {config}"


def test_noise_injection_survives():
    _check(DriftConfig(noise_injection=True))


def test_interleave_survives():
    _check(DriftConfig(interleave_noise=True))


def test_line_ending_mutation_survives():
    _check(DriftConfig(line_ending_mutation=True))


def test_flush_delay_survives():
    _check(DriftConfig(flush_delay=True))


def test_shuffle_non_cvl_survives():
    _check(DriftConfig(shuffle_non_cvl=True))


def test_combined_resilient_survives():
    _check(DriftConfig(
        noise_injection=True,
        interleave_noise=True,
        line_ending_mutation=True,
        flush_delay=True,
    ))


def test_cvl1_survives_max_non_destructive_drift():
    """CVL1 lines must be present in max-drift output (no partial_write)."""
    config = DriftConfig(
        chunk_split=True,
        interleave_noise=True,
        shuffle_non_cvl=True,
        utf8_corrupt=True,
        line_ending_mutation=True,
        flush_delay=True,
        noise_injection=True,
        partial_write=False,  # partial_write is inherently destructive
    )
    corrupted = apply_drift(_stream(), config, seed=42)
    assert b"commit" in corrupted, "commit field must survive non-destructive max drift"
