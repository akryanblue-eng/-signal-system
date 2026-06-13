"""Stability sweep: compute stability_score across drift × seed matrix."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from cvp_drift_injector.config import DriftConfig
from cvp_drift_injector.runner import run_stability_sweep
from src.cvl1 import extract

FIXTURE = pathlib.Path(__file__).parent.parent / "fixtures" / "sample_stdout_1.txt"
BASELINE = {
    "commit":      "edb1735ccfa34f0f89206649ce4d1451da280f9563fdc712247bfc7acb81d8a6",
    "certificate": "f56a64c3d9b1b4d8383c7d74693cd55cff8eb4ff077c3646fd2bacb13fbab178",
}

RESILIENT_CONFIGS = [
    ("noise_injection",       DriftConfig(noise_injection=True)),
    ("interleave_noise",      DriftConfig(interleave_noise=True)),
    ("line_ending_mutation",  DriftConfig(line_ending_mutation=True)),
    ("flush_delay",           DriftConfig(flush_delay=True)),
    ("shuffle_non_cvl",       DriftConfig(shuffle_non_cvl=True)),
    ("combined_resilient",    DriftConfig(
        noise_injection=True, interleave_noise=True,
        line_ending_mutation=True, flush_delay=True,
    )),
]

SEEDS = [0, 1, 42, 99, 1337]


def test_stability_score_perfect_on_resilient_configs():
    stream = FIXTURE.read_bytes()
    score = run_stability_sweep(
        stream=stream,
        configs=RESILIENT_CONFIGS,
        seeds=SEEDS,
        cvl1_extractor=extract,
        expected=BASELINE,
        verbose=False,
    )
    assert score == 1.0, f"Expected stability_score=1.0, got {score}"
