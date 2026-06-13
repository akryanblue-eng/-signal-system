"""Determinism: same (stream, config, seed) → identical output."""
import pathlib
from cvp_drift_injector.engine import apply_drift
from cvp_drift_injector.config import DriftConfig, MAX_DRIFT

FIXTURE = pathlib.Path(__file__).parent.parent / "fixtures" / "sample_stdout_1.txt"


def _stream() -> bytes:
    return FIXTURE.read_bytes()


def test_same_seed_same_output():
    s = _stream()
    assert apply_drift(s, MAX_DRIFT, seed=42) == apply_drift(s, MAX_DRIFT, seed=42)


def test_different_seed_different_output():
    s = _stream()
    out_42 = apply_drift(s, MAX_DRIFT, seed=42)
    out_99 = apply_drift(s, MAX_DRIFT, seed=99)
    assert out_42 != out_99


def test_different_config_different_output():
    s = _stream()
    cfg_a = DriftConfig(noise_injection=True)
    cfg_b = DriftConfig(utf8_corrupt=True)
    assert apply_drift(s, cfg_a, seed=42) != apply_drift(s, cfg_b, seed=42)


def test_no_drift_identity():
    from cvp_drift_injector.config import NO_DRIFT
    s = _stream()
    assert apply_drift(s, NO_DRIFT, seed=42) == s


def test_repeated_calls_are_stable():
    s = _stream()
    outputs = [apply_drift(s, MAX_DRIFT, seed=7) for _ in range(10)]
    assert all(o == outputs[0] for o in outputs)
