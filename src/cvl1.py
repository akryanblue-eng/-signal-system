"""
CVL1 — Canonical Line Extractor

Extracts named fields from a (possibly adversarially perturbed) log.
Rules:
  - Field line format: `^<name>:\\s+<value>` (case-sensitive name, leading ws stripped)
  - On duplicate fields, first occurrence wins
  - CRLF and LF both accepted
  - Non-UTF8 bytes decoded with replacement
  - Returns None for a field if not found or if value fails format validation
"""
import re
from typing import Union

# Canonical field names in emission order (used for ordering, not enforced at extraction)
CANONICAL_FIELDS = ("run_id", "build_id", "trace_id", "commit", "certificate", "verdict")

# Validation patterns per field
_VALIDATORS: dict[str, re.Pattern] = {
    "commit":      re.compile(r"^[0-9a-f]{64}$"),
    "certificate": re.compile(r"^[0-9a-f]{64}$"),
    "verdict":     re.compile(r"^(OK|FAIL)$"),
}

_FIELD_RE = re.compile(r"^([a-z_]+):\s+(\S+)\s*$")


def extract(log: Union[str, bytes], fields: tuple[str, ...] = CANONICAL_FIELDS) -> dict[str, str | None]:
    """
    Extract named fields from log text. Accepts str or bytes (decoded leniently).
    Returns dict mapping field name → value string, or None if absent/invalid.
    """
    if isinstance(log, bytes):
        text = log.decode("utf-8", errors="replace")
    else:
        text = log

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    found: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        m = _FIELD_RE.match(line)
        if not m:
            continue
        name, value = m.group(1), m.group(2)
        if name in fields and name not in found:
            found[name] = value

    result: dict[str, str | None] = {}
    for field in fields:
        raw = found.get(field)
        if raw is None:
            result[field] = None
            continue
        validator = _VALIDATORS.get(field)
        result[field] = raw if (validator is None or validator.match(raw)) else None

    return result
