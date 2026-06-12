import random
import string


def transform(stream: bytes, rng: random.Random) -> bytes:
    """Prepend and append random noise lines to the stream."""
    chars = (string.ascii_letters + string.digits + " _-=+").encode()
    count = rng.randint(3, 10)
    noise_lines = []
    for _ in range(count):
        line = bytes(rng.choices(chars, k=rng.randint(10, 60)))
        noise_lines.append(line)
    prefix = b"\n".join(noise_lines[:count // 2]) + b"\n"
    suffix = b"\n" + b"\n".join(noise_lines[count // 2:])
    return prefix + stream + suffix
