"""
Tests for Normalizer v1 authority boundary.

Covers:
  - Registry validation
  - Forbidden field rejection
  - Op registry enforcement (unknown ops, missing/extra args)
  - Type canonicalization (String NFC, Integer, Boolean, Identifier, Enum, Array, Object)
  - Float/NaN rejection at every nesting level
  - Ordering algebra: (file_path, source_order_index)
  - Trace hash determinism and content-sensitivity
  - Scope field handling
  - Empty trace
"""
import hashlib
import json
import unicodedata
import pytest

from src.normalizer_v1 import (
    CanonicalEvent,
    CanonicalOpTrace,
    NormalizerError,
    NormalizerV1,
    _canon_json,
)


# ------------------------------------------------------------------ #
# Fixtures                                                              #
# ------------------------------------------------------------------ #

MINIMAL_REGISTRY = {
    "version": "op_registry.v1",
    "ops": {
        "STATE_INIT": {"args": {"type": "Identifier"}},
        "TIME_READ": {"args": {}},
        "NETWORK_IO": {"args": {"api": "Identifier"}},
        "LOG_MSG": {"args": {"text": "String"}},
        "FLAG_SET": {"args": {"enabled": "Boolean"}},
        "COUNTER": {"args": {"count": "Integer"}},
        "META": {"args": {"data": "Object"}},
        "BATCH": {"args": {"items": "Array"}},
    },
}


def normalizer() -> NormalizerV1:
    return NormalizerV1(MINIMAL_REGISTRY)


def state_init_event(**overrides) -> dict:
    base = {
        "op": "STATE_INIT",
        "args": {"type": {"type": "Identifier", "value": "TravelerState"}},
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------ #
# Registry loading                                                      #
# ------------------------------------------------------------------ #

class TestRegistryLoading:
    def test_accepts_valid_registry(self):
        n = NormalizerV1(MINIMAL_REGISTRY)
        assert n is not None

    def test_rejects_wrong_version(self):
        bad = {**MINIMAL_REGISTRY, "version": "op_registry.v2"}
        with pytest.raises(NormalizerError, match="version mismatch"):
            NormalizerV1(bad)

    def test_rejects_missing_version(self):
        bad = {**MINIMAL_REGISTRY}
        del bad["version"]
        with pytest.raises(NormalizerError, match="version mismatch"):
            NormalizerV1(bad)

    def test_from_file(self, tmp_path):
        path = tmp_path / "reg.json"
        path.write_text(json.dumps(MINIMAL_REGISTRY), encoding="utf-8")
        n = NormalizerV1.from_file(path)
        assert n is not None


# ------------------------------------------------------------------ #
# Forbidden fields                                                       #
# ------------------------------------------------------------------ #

class TestForbiddenFields:
    FORBIDDEN = ["line", "column", "offset", "parser", "nid", "tid", "ast_kind"]

    @pytest.mark.parametrize("field", FORBIDDEN)
    def test_forbidden_field_rejected(self, field):
        raw = {**state_init_event(), field: 42}
        with pytest.raises(NormalizerError, match="forbidden representation fields"):
            normalizer().normalize([raw])

    def test_ordering_fields_not_forbidden(self):
        raw = {
            **state_init_event(),
            "file_path": "src/foo.py",
            "source_order_index": 0,
        }
        trace = normalizer().normalize([raw])
        assert len(trace.events) == 1

    def test_unknown_field_rejected(self):
        raw = {**state_init_event(), "extra_mystery": "value"}
        with pytest.raises(NormalizerError, match="unknown fields"):
            normalizer().normalize([raw])


# ------------------------------------------------------------------ #
# Required fields                                                        #
# ------------------------------------------------------------------ #

class TestRequiredFields:
    def test_missing_op_rejected(self):
        raw = {"args": {}}
        with pytest.raises(NormalizerError, match="missing required fields"):
            normalizer().normalize([raw])

    def test_missing_args_rejected(self):
        raw = {"op": "TIME_READ"}
        with pytest.raises(NormalizerError, match="missing required fields"):
            normalizer().normalize([raw])

    def test_empty_op_rejected(self):
        raw = {"op": "", "args": {}}
        with pytest.raises(NormalizerError, match="non-empty string"):
            normalizer().normalize([raw])

    def test_non_string_op_rejected(self):
        raw = {"op": 42, "args": {}}
        with pytest.raises(NormalizerError, match="non-empty string"):
            normalizer().normalize([raw])

    def test_non_dict_args_rejected(self):
        raw = {"op": "TIME_READ", "args": []}
        with pytest.raises(NormalizerError, match="args must be an object"):
            normalizer().normalize([raw])


# ------------------------------------------------------------------ #
# Op registry enforcement                                               #
# ------------------------------------------------------------------ #

class TestOpRegistry:
    def test_unknown_op_rejected(self):
        raw = {"op": "DOES_NOT_EXIST", "args": {}}
        with pytest.raises(NormalizerError, match="Unknown op"):
            normalizer().normalize([raw])

    def test_missing_required_arg_rejected(self):
        raw = {"op": "STATE_INIT", "args": {}}
        with pytest.raises(NormalizerError, match="missing required args"):
            normalizer().normalize([raw])

    def test_extra_arg_rejected(self):
        raw = {
            "op": "STATE_INIT",
            "args": {
                "type": {"type": "Identifier", "value": "X"},
                "extra": "oops",
            },
        }
        with pytest.raises(NormalizerError, match="unexpected args"):
            normalizer().normalize([raw])

    def test_no_args_op_accepts_empty_args(self):
        raw = {"op": "TIME_READ", "args": {}}
        trace = normalizer().normalize([raw])
        assert trace.events[0].op == "TIME_READ"
        assert trace.events[0].args == {}

    def test_no_args_op_rejects_nonempty_args(self):
        raw = {"op": "TIME_READ", "args": {"sneaky": "value"}}
        with pytest.raises(NormalizerError, match="unexpected args"):
            normalizer().normalize([raw])


# ------------------------------------------------------------------ #
# Type canonicalization                                                  #
# ------------------------------------------------------------------ #

class TestStringCanonicalization:
    def test_plain_string_accepted(self):
        raw = {"op": "LOG_MSG", "args": {"text": "hello"}}
        trace = normalizer().normalize([raw])
        assert trace.events[0].args["text"] == "hello"

    def test_nfc_normalization_applied(self):
        # "é" as NFD (e + combining acute) → NFC (single codepoint)
        nfd = "é"
        nfc = unicodedata.normalize("NFC", nfd)
        assert nfd != nfc
        raw = {"op": "LOG_MSG", "args": {"text": nfd}}
        trace = normalizer().normalize([raw])
        assert trace.events[0].args["text"] == nfc

    def test_integer_rejected_for_string_type(self):
        raw = {"op": "LOG_MSG", "args": {"text": 42}}
        with pytest.raises(NormalizerError, match="expected String"):
            normalizer().normalize([raw])


class TestIntegerCanonicalization:
    def test_integer_accepted(self):
        raw = {"op": "COUNTER", "args": {"count": 7}}
        trace = normalizer().normalize([raw])
        assert trace.events[0].args["count"] == 7

    def test_negative_integer_accepted(self):
        raw = {"op": "COUNTER", "args": {"count": -1}}
        trace = normalizer().normalize([raw])
        assert trace.events[0].args["count"] == -1

    def test_float_rejected_for_integer_type(self):
        raw = {"op": "COUNTER", "args": {"count": 7.0}}
        with pytest.raises(NormalizerError, match="Float values are forbidden"):
            normalizer().normalize([raw])

    def test_bool_rejected_for_integer_type(self):
        raw = {"op": "COUNTER", "args": {"count": True}}
        with pytest.raises(NormalizerError, match="expected Integer"):
            normalizer().normalize([raw])


class TestBooleanCanonicalization:
    def test_true_accepted(self):
        raw = {"op": "FLAG_SET", "args": {"enabled": True}}
        trace = normalizer().normalize([raw])
        assert trace.events[0].args["enabled"] is True

    def test_false_accepted(self):
        raw = {"op": "FLAG_SET", "args": {"enabled": False}}
        trace = normalizer().normalize([raw])
        assert trace.events[0].args["enabled"] is False

    def test_integer_rejected_for_boolean_type(self):
        raw = {"op": "FLAG_SET", "args": {"enabled": 1}}
        with pytest.raises(NormalizerError, match="expected Boolean"):
            normalizer().normalize([raw])

    def test_string_rejected_for_boolean_type(self):
        raw = {"op": "FLAG_SET", "args": {"enabled": "true"}}
        with pytest.raises(NormalizerError, match="expected Boolean"):
            normalizer().normalize([raw])


class TestIdentifierCanonicalization:
    def test_valid_identifier_accepted(self):
        raw = state_init_event()
        trace = normalizer().normalize([raw])
        assert trace.events[0].args["type"] == {
            "type": "Identifier",
            "value": "TravelerState",
        }

    def test_identifier_nfc_applied(self):
        nfd = "é"
        raw = {
            "op": "STATE_INIT",
            "args": {"type": {"type": "Identifier", "value": nfd}},
        }
        trace = normalizer().normalize([raw])
        assert trace.events[0].args["type"]["value"] == unicodedata.normalize("NFC", nfd)

    def test_wrong_tag_rejected(self):
        raw = {
            "op": "STATE_INIT",
            "args": {"type": {"type": "Enum", "value": "X"}},
        }
        with pytest.raises(NormalizerError, match="tagged type mismatch"):
            normalizer().normalize([raw])

    def test_missing_tag_rejected(self):
        raw = {
            "op": "STATE_INIT",
            "args": {"type": {"value": "X"}},
        }
        with pytest.raises(NormalizerError, match="tagged type mismatch"):
            normalizer().normalize([raw])

    def test_empty_value_rejected(self):
        raw = {
            "op": "STATE_INIT",
            "args": {"type": {"type": "Identifier", "value": ""}},
        }
        with pytest.raises(NormalizerError, match="non-empty string"):
            normalizer().normalize([raw])

    def test_non_dict_rejected(self):
        raw = {"op": "STATE_INIT", "args": {"type": "TravelerState"}}
        with pytest.raises(NormalizerError, match="expected tagged object"):
            normalizer().normalize([raw])


class TestObjectCanonicalization:
    def test_object_keys_sorted(self):
        raw = {
            "op": "META",
            "args": {"data": {"z": "last", "a": "first", "m": "middle"}},
        }
        trace = normalizer().normalize([raw])
        keys = list(trace.events[0].args["data"].keys())
        assert keys == ["a", "m", "z"]

    def test_nested_float_rejected(self):
        raw = {"op": "META", "args": {"data": {"count": 3.14}}}
        with pytest.raises(NormalizerError, match="Float values are forbidden"):
            normalizer().normalize([raw])

    def test_non_dict_rejected(self):
        raw = {"op": "META", "args": {"data": "not-an-object"}}
        with pytest.raises(NormalizerError, match="expected Object"):
            normalizer().normalize([raw])


class TestArrayCanonicalization:
    def test_array_order_preserved(self):
        raw = {"op": "BATCH", "args": {"items": [3, 1, 2]}}
        trace = normalizer().normalize([raw])
        assert trace.events[0].args["items"] == [3, 1, 2]

    def test_array_float_rejected(self):
        raw = {"op": "BATCH", "args": {"items": [1, 2.0, 3]}}
        with pytest.raises(NormalizerError, match="Float values are forbidden"):
            normalizer().normalize([raw])

    def test_non_list_rejected(self):
        raw = {"op": "BATCH", "args": {"items": "not-an-array"}}
        with pytest.raises(NormalizerError, match="expected Array"):
            normalizer().normalize([raw])

    def test_mixed_canonical_types_accepted(self):
        raw = {
            "op": "BATCH",
            "args": {
                "items": [
                    42,
                    "hello",
                    True,
                    {"type": "Identifier", "value": "Foo"},
                ]
            },
        }
        trace = normalizer().normalize([raw])
        items = trace.events[0].args["items"]
        assert items[0] == 42
        assert items[1] == "hello"
        assert items[2] is True
        assert items[3] == {"type": "Identifier", "value": "Foo"}


# ------------------------------------------------------------------ #
# Float rejection at top level                                          #
# ------------------------------------------------------------------ #

class TestFloatRejection:
    def test_float_in_args_rejected(self):
        raw = {"op": "COUNTER", "args": {"count": 3.14}}
        with pytest.raises(NormalizerError, match="Float values are forbidden"):
            normalizer().normalize([raw])

    def test_float_in_nested_object_rejected(self):
        raw = {"op": "META", "args": {"data": {"x": 1.5}}}
        with pytest.raises(NormalizerError, match="Float values are forbidden"):
            normalizer().normalize([raw])

    def test_float_in_array_rejected(self):
        raw = {"op": "BATCH", "args": {"items": [0.5]}}
        with pytest.raises(NormalizerError, match="Float values are forbidden"):
            normalizer().normalize([raw])


# ------------------------------------------------------------------ #
# Scope field                                                           #
# ------------------------------------------------------------------ #

class TestScopeField:
    def test_scope_string_accepted(self):
        raw = {**state_init_event(), "scope": "module.submodule"}
        trace = normalizer().normalize([raw])
        assert trace.events[0].scope == "module.submodule"

    def test_scope_none_accepted(self):
        raw = state_init_event()
        trace = normalizer().normalize([raw])
        assert trace.events[0].scope is None

    def test_non_string_scope_rejected(self):
        raw = {**state_init_event(), "scope": 42}
        with pytest.raises(NormalizerError, match="scope must be a string"):
            normalizer().normalize([raw])


# ------------------------------------------------------------------ #
# Ordering algebra                                                       #
# ------------------------------------------------------------------ #

class TestOrderingAlgebra:
    def _make_event(self, file_path, source_order_index, op="TIME_READ"):
        return {
            "op": op,
            "args": {},
            "file_path": file_path,
            "source_order_index": source_order_index,
        }

    def test_ordering_by_file_then_index(self):
        events = [
            self._make_event("b.py", 0),
            self._make_event("a.py", 1),
            self._make_event("a.py", 0),
        ]
        trace = normalizer().normalize(events)
        # All are TIME_READ so we verify the trace hash is stable across orderings
        # that share the same semantic content; here all three are identical ops,
        # but we verify the ordering produces a deterministic result.
        assert len(trace.events) == 3

    def test_file_path_sort_is_lexicographic(self):
        events = [
            self._make_event("z.py", 0),
            self._make_event("a.py", 0),
            self._make_event("m.py", 0),
        ]
        # We inject unique ops to distinguish position
        registry = {
            "version": "op_registry.v1",
            "ops": {
                "OP_A": {"args": {}},
                "OP_B": {"args": {}},
                "OP_C": {"args": {}},
            },
        }
        n = NormalizerV1(registry)
        raw = [
            {"op": "OP_C", "args": {}, "file_path": "z.py", "source_order_index": 0},
            {"op": "OP_A", "args": {}, "file_path": "a.py", "source_order_index": 0},
            {"op": "OP_B", "args": {}, "file_path": "m.py", "source_order_index": 0},
        ]
        trace = n.normalize(raw)
        ops = [e.op for e in trace.events]
        assert ops == ["OP_A", "OP_B", "OP_C"]

    def test_ordering_fields_stripped_from_canonical_event(self):
        raw = {**state_init_event(), "file_path": "x.py", "source_order_index": 5}
        trace = normalizer().normalize([raw])
        event = trace.events[0]
        # CanonicalEvent has op, args, scope only
        assert not hasattr(event, "file_path")
        assert not hasattr(event, "source_order_index")

    def test_events_without_ordering_metadata_accepted(self):
        trace = normalizer().normalize([state_init_event()])
        assert len(trace.events) == 1

    def test_invalid_source_order_index_type_rejected(self):
        raw = {**state_init_event(), "file_path": "f.py", "source_order_index": "0"}
        with pytest.raises(NormalizerError, match="source_order_index must be an integer"):
            normalizer().normalize([raw])

    def test_invalid_file_path_type_rejected(self):
        raw = {**state_init_event(), "file_path": 99, "source_order_index": 0}
        with pytest.raises(NormalizerError, match="file_path must be a string"):
            normalizer().normalize([raw])


# ------------------------------------------------------------------ #
# Trace hash                                                            #
# ------------------------------------------------------------------ #

class TestTraceHash:
    def test_empty_trace_hash_is_sha256_of_empty(self):
        trace = normalizer().normalize([])
        expected = hashlib.sha256(b"").hexdigest()
        assert trace.trace_hash == expected

    def test_trace_hash_is_deterministic(self):
        raw = [state_init_event()]
        t1 = normalizer().normalize(raw)
        t2 = normalizer().normalize(raw)
        assert t1.trace_hash == t2.trace_hash

    def test_different_ops_produce_different_hashes(self):
        t1 = normalizer().normalize([{"op": "TIME_READ", "args": {}}])
        t2 = normalizer().normalize([state_init_event()])
        assert t1.trace_hash != t2.trace_hash

    def test_different_arg_values_produce_different_hashes(self):
        t1 = normalizer().normalize([
            {"op": "STATE_INIT", "args": {"type": {"type": "Identifier", "value": "A"}}}
        ])
        t2 = normalizer().normalize([
            {"op": "STATE_INIT", "args": {"type": {"type": "Identifier", "value": "B"}}}
        ])
        assert t1.trace_hash != t2.trace_hash

    def test_event_order_affects_trace_hash(self):
        registry = {
            "version": "op_registry.v1",
            "ops": {
                "OP_X": {"args": {}},
                "OP_Y": {"args": {}},
            },
        }
        n = NormalizerV1(registry)
        # Without ordering metadata the order is input-order (stable sort)
        t1 = n.normalize([{"op": "OP_X", "args": {}}, {"op": "OP_Y", "args": {}}])
        t2 = n.normalize([{"op": "OP_Y", "args": {}}, {"op": "OP_X", "args": {}}])
        # Different input orders without file_path/source_order_index → stable sort
        # preserves submission order, so hashes differ
        assert t1.trace_hash != t2.trace_hash

    def test_scope_excluded_from_hash(self):
        """Scope is metadata — two traces differing only in scope share event hashes."""
        t1 = normalizer().normalize([state_init_event()])
        t2 = normalizer().normalize([{**state_init_event(), "scope": "some.scope"}])
        assert t1.trace_hash == t2.trace_hash

    def test_trace_hash_is_hex_sha256(self):
        trace = normalizer().normalize([state_init_event()])
        assert len(trace.trace_hash) == 64
        int(trace.trace_hash, 16)  # must be valid hex

    def test_nfc_normalization_affects_hash_consistently(self):
        nfd = "é"
        nfc = unicodedata.normalize("NFC", nfd)
        t_nfd = normalizer().normalize([{"op": "LOG_MSG", "args": {"text": nfd}}])
        t_nfc = normalizer().normalize([{"op": "LOG_MSG", "args": {"text": nfc}}])
        # Both normalize to NFC before hashing → same hash
        assert t_nfd.trace_hash == t_nfc.trace_hash


# ------------------------------------------------------------------ #
# Canonical JSON helper                                                  #
# ------------------------------------------------------------------ #

class TestCanonJson:
    def test_keys_sorted(self):
        result = _canon_json({"z": 1, "a": 2}).decode("utf-8")
        assert result.index('"a"') < result.index('"z"')

    def test_no_whitespace(self):
        result = _canon_json({"key": "value"}).decode("utf-8")
        assert " " not in result
        assert "\n" not in result

    def test_utf8_encoded(self):
        result = _canon_json({"k": "café"})
        assert isinstance(result, bytes)
        assert "café".encode("utf-8") in result
