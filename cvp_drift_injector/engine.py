import random

from .config import DriftConfig
from .seeds import derive_seed
from .drifts import (
    chunk_split, interleave, shuffle, utf8_corrupt,
    line_endings, flush_delay, partial_write, noise,
)


def apply_drift(stream: bytes, config: DriftConfig, seed: int = 42) -> bytes:
    """
    Apply the enabled drift transforms in deterministic order.
    Same (stream, config, seed) always produces the same output.
    No hidden global state. No OS or time dependency.
    """
    s = derive_seed(stream, str(config), seed)
    rng = random.Random(s)
    out = stream
    if config.chunk_split:
        out = chunk_split.transform(out, rng)
    if config.interleave_noise:
        out = interleave.transform(out, rng)
    if config.shuffle_non_cvl:
        out = shuffle.transform(out, rng)
    if config.utf8_corrupt:
        out = utf8_corrupt.transform(out, rng)
    if config.line_ending_mutation:
        out = line_endings.transform(out, rng)
    if config.flush_delay:
        out = flush_delay.transform(out, rng)
    if config.partial_write:
        out = partial_write.transform(out, rng)
    if config.noise_injection:
        out = noise.transform(out, rng)
    return out
