"""
Canonical JSON (CJSON) serialization.

Rules (strict mode):
  - UTF-8 bytes, no BOM
  - Object keys sorted lexicographically at every level
  - Arrays must use semantic ordering (caller's responsibility — this module
    validates but does not impose semantic sort)
  - Forbidden types → hard fail (CJSONEncodeError), never silently coerce
  - No prototype leakage: only plain dicts, lists, str, int, float (finite only),
    bool, None

Hash rule: SHA-256(canonical_bytes).hexdigest()
"""
from __future__ import annotations
import hashlib
import json
import math
from typing import Any


class CJSONEncodeError(TypeError):
    """Raised when a value cannot be represented in canonical JSON."""


_ALLOWED_SCALAR = (bool, int, str, type(None))


def _validate(obj: Any, path: str = "$") -> None:
    """Walk obj recursively and reject any forbidden value or type."""
    if isinstance(obj, bool):
        return  # bool before int (bool subclasses int)
    if isinstance(obj, int):
        return
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise CJSONEncodeError(f"NaN/Infinity not allowed at {path}: {obj!r}")
        return
    if isinstance(obj, str):
        return
    if obj is None:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise CJSONEncodeError(
                    f"Non-string dict key at {path}: {k!r} ({type(k).__name__})"
                )
            _validate(v, f"{path}.{k}")
        return
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            _validate(v, f"{path}[{i}]")
        return
    raise CJSONEncodeError(
        f"Non-CJSON type at {path}: {type(obj).__name__!r}. "
        "Allowed: dict, list, str, int, float (finite), bool, None. "
        "Forbidden: undefined, NaN, Infinity, Map, Set, Date, class instances, functions."
    )


def canonical_serialize(obj: Any) -> bytes:
    """
    Serialize obj to canonical JSON bytes.
    - sort_keys=True at every level
    - compact separators (no extra whitespace)
    - UTF-8 encoded
    - Validates first; raises CJSONEncodeError on any forbidden type
    """
    _validate(obj)
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(obj: Any) -> str:
    """SHA-256(canonical_bytes), hex-encoded. Primary artifact identity function."""
    return sha256_hex(canonical_serialize(obj))


def cjsonl_bytes(records: list[Any]) -> bytes:
    """
    Produce CJSONL bytes: one canonical JSON object per line, UTF-8.
    Records must already be in the desired stable order — caller sorts.
    """
    lines = [canonical_serialize(r) + b"\n" for r in records]
    return b"".join(lines)
