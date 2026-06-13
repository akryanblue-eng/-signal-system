import random
import string


def transform(stream: bytes, rng: random.Random) -> bytes:
    """Interleave noise lines between existing lines (tests line-isolation resilience)."""
    chars = (string.ascii_letters + string.digits + " _=-+[]{}|").encode()
    lines = stream.split(b"\n")
    out = []
    for line in lines:
        out.append(line)
        if rng.random() < 0.4:
            noise = bytes(rng.choices(chars, k=rng.randint(8, 50)))
            out.append(noise)
    return b"\n".join(out)
