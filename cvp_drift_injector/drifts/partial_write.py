import random


def transform(stream: bytes, rng: random.Random) -> bytes:
    """
    Simulate partial write: truncate to a random fraction of the stream.
    Fraction is chosen uniformly from [0.5, 1.0) so canonical lines may survive.
    """
    keep = rng.uniform(0.5, 1.0)
    cut = int(len(stream) * keep)
    return stream[:cut]
