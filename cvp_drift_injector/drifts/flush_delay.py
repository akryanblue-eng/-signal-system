import random


def transform(stream: bytes, rng: random.Random) -> bytes:
    """
    Simulate delayed flush: reorder adjacent non-canonical lines to model
    out-of-order buffer delivery. Canonical field lines are not reordered.
    """
    from .shuffle import _is_cvl1
    lines = stream.split(b"\n")
    i = 0
    out = list(lines)
    while i < len(out) - 1:
        if not _is_cvl1(out[i]) and not _is_cvl1(out[i + 1]):
            if rng.random() < 0.3:
                out[i], out[i + 1] = out[i + 1], out[i]
                i += 2
                continue
        i += 1
    return b"\n".join(out)
