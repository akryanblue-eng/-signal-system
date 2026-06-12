import random


def transform(stream: bytes, rng: random.Random) -> bytes:
    """Split stream into variable-size chunks and reassemble (tests partial-read resilience)."""
    chunks = []
    i = 0
    while i < len(stream):
        size = rng.randint(1, 8)
        chunks.append(stream[i:i + size])
        i += size
    return b"".join(chunks)
