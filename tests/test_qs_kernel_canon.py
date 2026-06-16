"""
Tests for CJSON canonical serialization (src/qs_kernel/canon.py).

Verifies: sort_keys, forbidden types, determinism, hash stability,
CJSONL ordering, roundtrip, NaN/Infinity rejection.
"""
import json
import math
import pytest

from src.qs_kernel.canon import (
    CJSONEncodeError, canonical_hash, canonical_serialize, cjsonl_bytes, sha256_hex,
)


# ──────────────────────────────────────────────────────────────────────────────
# Canonical serialization basics
# ──────────────────────────────────────────────────────────────────────────────

class TestCanonicalSerialize:
    def test_produces_bytes(self):
        assert isinstance(canonical_serialize({}), bytes)

    def test_utf8_encoding(self):
        result = canonical_serialize({"k": "αβγ"})
        assert result.decode("utf-8") == '{"k":"αβγ"}'

    def test_sort_keys(self):
        obj = {"z": 1, "a": 2, "m": 3}
        result = canonical_serialize(obj)
        assert result == b'{"a":2,"m":3,"z":1}'

    def test_sort_keys_nested(self):
        obj = {"z": {"b": 1, "a": 2}, "a": 0}
        result = canonical_serialize(obj).decode()
        assert result.index('"a":') < result.index('"b":')

    def test_compact_separators(self):
        result = canonical_serialize({"k": [1, 2]})
        assert b" " not in result

    def test_bool_before_int(self):
        assert canonical_serialize(True) == b"true"
        assert canonical_serialize(False) == b"false"

    def test_null(self):
        assert canonical_serialize(None) == b"null"

    def test_int(self):
        assert canonical_serialize(42) == b"42"

    def test_string(self):
        assert canonical_serialize("hello") == b'"hello"'

    def test_list_order_preserved(self):
        # arrays: order is caller's responsibility, not changed by serializer
        result = canonical_serialize([3, 1, 2])
        assert result == b"[3,1,2]"

    def test_empty_dict(self):
        assert canonical_serialize({}) == b"{}"

    def test_empty_list(self):
        assert canonical_serialize([]) == b"[]"

    def test_finite_float_allowed(self):
        result = canonical_serialize({"f": 1.5})
        assert b"1.5" in result

    def test_idempotent(self):
        obj = {"b": [2, 1], "a": {"y": 9, "x": 8}}
        b1 = canonical_serialize(obj)
        b2 = canonical_serialize(obj)
        assert b1 == b2


# ──────────────────────────────────────────────────────────────────────────────
# Forbidden types
# ──────────────────────────────────────────────────────────────────────────────

class TestForbiddenTypes:
    def test_nan_rejected(self):
        with pytest.raises(CJSONEncodeError, match="NaN"):
            canonical_serialize({"v": float("nan")})

    def test_inf_rejected(self):
        with pytest.raises(CJSONEncodeError):
            canonical_serialize(float("inf"))

    def test_neg_inf_rejected(self):
        with pytest.raises(CJSONEncodeError):
            canonical_serialize(float("-inf"))

    def test_non_string_key_rejected(self):
        with pytest.raises(CJSONEncodeError, match="Non-string"):
            canonical_serialize({1: "v"})  # type: ignore

    def test_set_rejected(self):
        with pytest.raises(CJSONEncodeError, match="Non-CJSON type"):
            canonical_serialize({1, 2, 3})  # type: ignore

    def test_class_instance_rejected(self):
        class Foo:
            pass
        with pytest.raises(CJSONEncodeError):
            canonical_serialize(Foo())

    def test_bytes_rejected(self):
        with pytest.raises(CJSONEncodeError):
            canonical_serialize(b"raw bytes")

    def test_nested_nan_rejected(self):
        with pytest.raises(CJSONEncodeError):
            canonical_serialize({"a": {"b": float("nan")}})

    def test_nan_in_list_rejected(self):
        with pytest.raises(CJSONEncodeError):
            canonical_serialize([1, float("nan"), 3])


# ──────────────────────────────────────────────────────────────────────────────
# Hashing
# ──────────────────────────────────────────────────────────────────────────────

class TestCanonicalHash:
    def test_returns_hex_string(self):
        h = canonical_hash({"k": "v"})
        assert isinstance(h, str)
        assert len(h) == 64

    def test_deterministic(self):
        h1 = canonical_hash({"b": 2, "a": 1})
        h2 = canonical_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_different_objects_different_hashes(self):
        assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})

    def test_sha256_hex(self):
        import hashlib
        data = b"hello"
        assert sha256_hex(data) == hashlib.sha256(data).hexdigest()

    def test_canonical_hash_matches_sha256_of_canonical_bytes(self):
        obj = {"z": 1, "a": 2}
        h = canonical_hash(obj)
        expected = sha256_hex(canonical_serialize(obj))
        assert h == expected


# ──────────────────────────────────────────────────────────────────────────────
# CJSONL
# ──────────────────────────────────────────────────────────────────────────────

class TestCJSONL:
    def test_empty_produces_empty_bytes(self):
        assert cjsonl_bytes([]) == b""

    def test_each_record_on_own_line(self):
        records = [{"a": 1}, {"b": 2}]
        result = cjsonl_bytes(records)
        lines = result.split(b"\n")
        assert lines[-1] == b""  # trailing newline
        assert len([l for l in lines if l]) == 2

    def test_each_line_is_valid_json(self):
        records = [{"z": 3, "a": 1}, {"y": 2}]
        result = cjsonl_bytes(records)
        for line in result.splitlines():
            obj = json.loads(line)
            assert isinstance(obj, dict)

    def test_keys_sorted_per_line(self):
        records = [{"z": 3, "a": 1}]
        line = cjsonl_bytes(records).splitlines()[0]
        parsed = json.loads(line)
        assert list(parsed.keys()) == sorted(parsed.keys())

    def test_deterministic_across_calls(self):
        records = [{"a": i, "b": i * 2} for i in range(5)]
        assert cjsonl_bytes(records) == cjsonl_bytes(records)
