import random

# Field names that constitute canonical CVL1 lines — preserved in place
CVL1_FIELDS = {b"run_id", b"build_id", b"trace_id", b"commit", b"certificate", b"verdict"}


def _is_cvl1(line: bytes) -> bool:
    field = line.split(b":")[0].strip()
    return field in CVL1_FIELDS


def transform(stream: bytes, rng: random.Random) -> bytes:
    """Shuffle non-CVL1 lines only; canonical lines remain in their original positions."""
    lines = stream.split(b"\n")
    cvl1_positions = [(i, l) for i, l in enumerate(lines) if _is_cvl1(l)]
    non_cvl1 = [l for l in lines if not _is_cvl1(l)]
    rng.shuffle(non_cvl1)

    result = list(non_cvl1)
    for pos, line in cvl1_positions:
        insert_at = min(pos, len(result))
        result.insert(insert_at, line)
    return b"\n".join(result)
