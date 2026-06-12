import random

_BAD_BYTES = bytes([0x80, 0xBF, 0xFE, 0xFF, 0xC0, 0xC1])


def transform(stream: bytes, rng: random.Random) -> bytes:
    """Inject invalid UTF-8 bytes at random positions in non-field lines."""
    lines = stream.split(b"\n")
    out = []
    for line in lines:
        # Only corrupt lines that don't start with a known canonical field prefix
        if b":" in line and not any(
            line.startswith(f) for f in (b"commit:", b"certificate:", b"run_id:",
                                          b"build_id:", b"trace_id:", b"verdict:")
        ):
            data = bytearray(line)
            for _ in range(rng.randint(1, 3)):
                if data:
                    pos = rng.randint(0, len(data) - 1)
                    data.insert(pos, rng.choice(_BAD_BYTES))
            out.append(bytes(data))
        else:
            out.append(line)
    return b"\n".join(out)
