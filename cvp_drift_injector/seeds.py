import hashlib


def derive_seed(stream: bytes, config: str, base_seed: int = 0) -> int:
    """
    Content-addressed seed: same (stream, config, base_seed) → same drift sequence.
    Reproducible chaos — every experiment is replayable.
    """
    h = hashlib.sha256(stream + config.encode("utf-8")).hexdigest()
    return (int(h[:16], 16) ^ base_seed) % (2 ** 32)
