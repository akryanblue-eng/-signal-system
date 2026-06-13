import random


def transform(stream: bytes, rng: random.Random) -> bytes:
    """Randomly replace LF with CRLF on a per-line basis."""
    lines = stream.split(b"\n")
    out = []
    for line in lines:
        ending = b"\r\n" if rng.random() < 0.5 else b"\n"
        out.append(line + ending)
    return b"".join(out)
