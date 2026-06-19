"""Canonical encoding and content hashing (docs/eiac-schema-v1.0.md §1.2, §1.4).

`canon()` is a custom, dependency-free byte format -- not literal CBOR -- but
it satisfies every determinism rule locked in §1.4.1:

- map keys sorted by bytewise lexicographic order of their UTF-8 bytes
- integers minimally encoded, no floats, no NaN/Infinity
- raw UTF-8 strings, no normalization
- explicit length prefixes everywhere, no indefinite-length encodings
- binary data as literal bytes, never base64

Changing the byte layout below changes every H(x) in the system. If this
ever needs to change, the §1.4.6 test vectors in eiac/tests/fixtures/ must
be regenerated in the same change, not patched around.
"""
from __future__ import annotations

import hashlib
import struct
from typing import Any

_NULL = 0x00
_FALSE = 0x01
_TRUE = 0x02
_INT = 0x03
_STR = 0x04
_BYTES = 0x05
_ARRAY = 0x06
_MAP = 0x07


def canon(value: Any) -> bytes:
    if value is None:
        return bytes([_NULL])
    if isinstance(value, bool):
        return bytes([_TRUE if value else _FALSE])
    if isinstance(value, int):
        return _canon_int(value)
    if isinstance(value, float):
        raise TypeError("floating point values are forbidden in canonical encoding (schema §1.4.1)")
    if isinstance(value, str):
        return _canon_str(value)
    if isinstance(value, bytes):
        return _canon_bytes(value)
    if isinstance(value, (list, tuple)):
        return _canon_array(value)
    if isinstance(value, dict):
        return _canon_map(value)
    raise TypeError(f"non-canonical type: {type(value)!r}")


def _canon_int(value: int) -> bytes:
    sign = 0x00 if value >= 0 else 0x01
    magnitude = abs(value)
    length = max(1, (magnitude.bit_length() + 7) // 8)
    body = magnitude.to_bytes(length, "big")
    return bytes([_INT, sign]) + struct.pack(">I", len(body)) + body


def _canon_str(value: str) -> bytes:
    body = value.encode("utf-8")
    return bytes([_STR]) + struct.pack(">I", len(body)) + body


def _canon_bytes(value: bytes) -> bytes:
    return bytes([_BYTES]) + struct.pack(">I", len(value)) + value


def _canon_array(value) -> bytes:
    encoded = b"".join(canon(v) for v in value)
    return bytes([_ARRAY]) + struct.pack(">I", len(value)) + encoded


def _canon_map(value: dict) -> bytes:
    if not all(isinstance(k, str) for k in value):
        raise TypeError("canonical map keys must be strings")
    ordered_keys = sorted(value.keys(), key=lambda k: k.encode("utf-8"))
    parts = [struct.pack(">I", len(ordered_keys))]
    for k in ordered_keys:
        parts.append(_canon_str(k))
        parts.append(canon(value[k]))
    return bytes([_MAP]) + b"".join(parts)


def content_hash(schema_tag: str, value: Any) -> bytes:
    """H(x) = SHA-256("EIAC/v1.0|" || schema_tag || 0x00 || canon(x))  (schema §1.4.2)."""
    prefix = b"EIAC/v1.0|" + schema_tag.encode("utf-8") + b"\x00"
    return hashlib.sha256(prefix + canon(value)).digest()


def hash_of(obj: Any) -> bytes:
    """H(x) for any object exposing `.schema_tag` and `.to_canon()`."""
    return content_hash(obj.schema_tag, obj.to_canon())
