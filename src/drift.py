"""
Drift Injection Library — CVP-v1.2

Each injector takes a canonical log string and returns a perturbed version.
Injectors are composable and deterministic (seeded RNG only).
"""
import random
import string


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def noise_lines(log: str, *, count: int = 5, seed: int = 0) -> str:
    """Insert random printable-ASCII noise lines at random positions."""
    rng = _rng(seed)
    lines = log.splitlines(keepends=True)
    chars = string.ascii_letters + string.digits + " _=-+[]{}|"
    for _ in range(count):
        noise = "".join(rng.choices(chars, k=rng.randint(8, 60))) + "\n"
        pos = rng.randint(0, len(lines))
        lines.insert(pos, noise)
    return "".join(lines)


def shuffle_lines(log: str, *, seed: int = 0) -> str:
    """Reorder lines randomly. CVL1 extraction must be order-independent."""
    rng = _rng(seed)
    lines = log.splitlines(keepends=True)
    rng.shuffle(lines)
    return "".join(lines)


def crlf_normalize(log: str) -> str:
    """Replace LF with CRLF (Windows-style line endings)."""
    return log.replace("\n", "\r\n")


def duplicate_fields(log: str) -> str:
    """Emit each canonical field line twice consecutively."""
    out = []
    for line in log.splitlines(keepends=True):
        out.append(line)
        if any(line.startswith(f"{f}:") for f in ("run_id", "build_id", "trace_id",
                                                    "commit", "certificate", "verdict")):
            out.append(line)
    return "".join(out)


def truncate(log: str, *, keep_fraction: float = 0.5) -> str:
    """Truncate log to a fraction of its length (simulates partial write)."""
    cut = max(0, int(len(log) * keep_fraction))
    return log[:cut]


def corrupt_encoding(log: str, *, seed: int = 0) -> bytes:
    """
    Return bytes with injected invalid UTF-8 sequences in noise positions.
    Callers must decode with errors='replace' to handle this.
    """
    rng = _rng(seed)
    data = bytearray(log.encode("utf-8"))
    bad_bytes = bytes([0x80, 0xBF, 0xFE, 0xFF])
    for _ in range(10):
        pos = rng.randint(0, len(data) - 1)
        data.insert(pos, rng.choice(bad_bytes))
    return bytes(data)


def case_mangle_keys(log: str) -> str:
    """Uppercase the field-name portion of canonical lines (breaks CVL1 strict match)."""
    out = []
    for line in log.splitlines(keepends=True):
        for field in ("run_id", "build_id", "trace_id", "commit", "certificate", "verdict"):
            if line.startswith(f"{field}:"):
                line = field.upper() + line[len(field):]
                break
        out.append(line)
    return "".join(out)


def leading_whitespace(log: str) -> str:
    """Prepend spaces to each line (tests that extraction strips leading whitespace)."""
    return "".join("  " + line for line in log.splitlines(keepends=True))


# Registry — ordered by severity (least to most destructive)
ALL_INJECTORS: list[tuple[str, callable]] = [
    ("noise_lines",        lambda s: noise_lines(s)),
    ("shuffle_lines",      lambda s: shuffle_lines(s)),
    ("crlf_normalize",     lambda s: crlf_normalize(s)),
    ("duplicate_fields",   lambda s: duplicate_fields(s)),
    ("leading_whitespace", lambda s: leading_whitespace(s)),
    ("truncate_75pct",     lambda s: truncate(s, keep_fraction=0.75)),
    ("truncate_50pct",     lambda s: truncate(s, keep_fraction=0.50)),
    ("truncate_25pct",     lambda s: truncate(s, keep_fraction=0.25)),
    ("case_mangle_keys",   lambda s: case_mangle_keys(s)),
    # corrupt_encoding returns bytes; handled separately in immunity_test
]
