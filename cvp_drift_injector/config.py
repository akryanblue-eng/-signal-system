from dataclasses import dataclass


@dataclass(frozen=True)
class DriftConfig:
    chunk_split: bool = False
    interleave_noise: bool = False
    shuffle_non_cvl: bool = False
    utf8_corrupt: bool = False
    line_ending_mutation: bool = False
    flush_delay: bool = False
    partial_write: bool = False
    noise_injection: bool = False


MAX_DRIFT = DriftConfig(
    chunk_split=True,
    interleave_noise=True,
    shuffle_non_cvl=True,
    utf8_corrupt=True,
    line_ending_mutation=True,
    flush_delay=True,
    partial_write=True,
    noise_injection=True,
)

NO_DRIFT = DriftConfig()
