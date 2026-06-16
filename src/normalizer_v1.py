"""
Normalizer v1 — Authority Boundary

The Normalizer is the sole authority over:
  1. What an operation is
  2. What arguments are semantically meaningful
  3. How arguments are canonicalized
  4. How events are ordered
  5. How trace hashes are computed

Nothing upstream makes semantic decisions. Everything downstream observes
CanonicalOpTrace only.

Canonical type system (permitted):
  String | Integer | Boolean | Enum | Identifier | Array<CanonicalValue> | Object<String, CanonicalValue>

Explicitly forbidden value kinds:
  Float / NaN / Infinity / parser-specific IDs / AST node references /
  token positions / source locations

Forbidden event-level fields (representation artifacts):
  line, column, offset, parser, nid, tid, ast_kind

Ordering algebra (v1):
  CanonicalOrder(event) = (file_path, source_order_index)
  Supplied by extractor; consumed and discarded by normalizer.

Trace hash definition:
  event_hash  = SHA256(canon_json({"op": op, "args": args}))
  trace_hash  = SHA256(event_hash_1 || event_hash_2 || ...)
"""
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


_FORBIDDEN_EVENT_FIELDS = frozenset({
    "line", "column", "offset", "parser", "nid", "tid", "ast_kind",
})

_REQUIRED_EVENT_FIELDS = frozenset({"op", "args"})

# Ordering metadata consumed by normalizer and stripped before hashing.
_ORDERING_FIELDS = frozenset({"file_path", "source_order_index"})

_PERMITTED_EVENT_FIELDS = _REQUIRED_EVENT_FIELDS | {"scope"} | _ORDERING_FIELDS


class NormalizerError(Exception):
    pass


@dataclass(frozen=True)
class CanonicalEvent:
    op: str
    args: dict
    scope: Optional[str] = None


@dataclass(frozen=True)
class CanonicalOpTrace:
    events: tuple           # tuple[CanonicalEvent, ...]
    trace_hash: str         # hex-encoded SHA256


class NormalizerV1:
    """
    Normalizer v1. Owns the op registry, canonical type system, ordering
    algebra, and trace hash computation.
    """

    REGISTRY_VERSION = "op_registry.v1"

    def __init__(self, registry: dict) -> None:
        version = registry.get("version")
        if version != self.REGISTRY_VERSION:
            raise NormalizerError(
                f"Registry version mismatch: expected {self.REGISTRY_VERSION!r}, "
                f"got {version!r}"
            )
        self._ops: dict[str, dict] = registry.get("ops", {})

    @classmethod
    def from_file(cls, path: str | Path) -> "NormalizerV1":
        with open(path, encoding="utf-8") as f:
            registry = json.load(f)
        return cls(registry)

    def normalize(self, raw_events: list[dict]) -> CanonicalOpTrace:
        """
        Normalize raw extractor events into a CanonicalOpTrace.

        Each raw event dict may include ordering metadata (file_path,
        source_order_index) which the normalizer uses for sequencing then
        discards. The resulting CanonicalOpTrace contains no provenance.
        """
        ordered = _order_events(raw_events)
        events = [self._normalize_event(raw) for raw in ordered]
        trace_hash = self._compute_trace_hash(events)
        return CanonicalOpTrace(events=tuple(events), trace_hash=trace_hash)

    # ------------------------------------------------------------------ #
    # Event normalization                                                   #
    # ------------------------------------------------------------------ #

    def _normalize_event(self, raw: dict) -> CanonicalEvent:
        payload_keys = set(raw.keys()) - _ORDERING_FIELDS

        missing = _REQUIRED_EVENT_FIELDS - payload_keys
        if missing:
            raise NormalizerError(
                f"Event missing required fields: {sorted(missing)}"
            )

        forbidden = payload_keys & _FORBIDDEN_EVENT_FIELDS
        if forbidden:
            raise NormalizerError(
                f"Event contains forbidden representation fields: {sorted(forbidden)}"
            )

        unknown = payload_keys - (_REQUIRED_EVENT_FIELDS | {"scope"})
        if unknown:
            raise NormalizerError(
                f"Event contains unknown fields: {sorted(unknown)}"
            )

        op = raw["op"]
        if not isinstance(op, str) or not op:
            raise NormalizerError(f"op must be a non-empty string, got {op!r}")

        if op not in self._ops:
            raise NormalizerError(f"Unknown op {op!r} — not in registry")

        args_raw = raw["args"]
        if not isinstance(args_raw, dict):
            raise NormalizerError(
                f"args must be an object, got {type(args_raw).__name__!r}"
            )

        arg_schema = self._ops[op].get("args", {})
        args = self._canonicalize_args(args_raw, arg_schema, op)

        scope = raw.get("scope")
        if scope is not None and not isinstance(scope, str):
            raise NormalizerError(
                f"scope must be a string, got {type(scope).__name__!r}"
            )

        return CanonicalEvent(op=op, args=args, scope=scope)

    def _canonicalize_args(
        self, args_raw: dict, schema: dict, op: str
    ) -> dict:
        missing = set(schema.keys()) - set(args_raw.keys())
        if missing:
            raise NormalizerError(
                f"Op {op!r} missing required args: {sorted(missing)}"
            )
        extra = set(args_raw.keys()) - set(schema.keys())
        if extra:
            raise NormalizerError(
                f"Op {op!r} has unexpected args: {sorted(extra)}"
            )
        return {
            k: _canonicalize_value(args_raw[k], schema[k], f"{op}.args.{k}")
            for k in schema
        }

    # ------------------------------------------------------------------ #
    # Hashing                                                               #
    # ------------------------------------------------------------------ #

    def _compute_event_hash(self, event: CanonicalEvent) -> bytes:
        canonical_bytes = _canon_json({"args": event.args, "op": event.op})
        return hashlib.sha256(canonical_bytes).digest()

    def _compute_trace_hash(self, events: list[CanonicalEvent]) -> str:
        h = hashlib.sha256()
        for event in events:
            h.update(self._compute_event_hash(event))
        return h.hexdigest()


# ------------------------------------------------------------------ #
# Module-level helpers                                                  #
# ------------------------------------------------------------------ #

def _order_events(raw_events: list[dict]) -> list[dict]:
    """
    Order raw events by (file_path, source_order_index).
    Events missing ordering metadata default to ("", 0).
    """
    def sort_key(e: dict) -> tuple:
        fp = e.get("file_path", "")
        idx = e.get("source_order_index", 0)
        if not isinstance(fp, str):
            raise NormalizerError(
                f"file_path must be a string, got {type(fp).__name__!r}"
            )
        if not isinstance(idx, int) or isinstance(idx, bool):
            raise NormalizerError(
                f"source_order_index must be an integer, got {type(idx).__name__!r}"
            )
        return (fp, idx)

    return sorted(raw_events, key=sort_key)


def _canonicalize_value(value: Any, expected_type: str, path: str) -> Any:
    """
    Validate and canonicalize a value according to its declared type.
    Floats, NaN, and Infinity are rejected at every level.
    """
    if isinstance(value, float):
        raise NormalizerError(
            f"{path}: Float values are forbidden in canonical events"
        )

    if expected_type == "String":
        if not isinstance(value, str):
            raise NormalizerError(
                f"{path}: expected String, got {type(value).__name__!r}"
            )
        return unicodedata.normalize("NFC", value)

    elif expected_type == "Integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise NormalizerError(
                f"{path}: expected Integer, got {type(value).__name__!r}"
            )
        return value

    elif expected_type == "Boolean":
        if not isinstance(value, bool):
            raise NormalizerError(
                f"{path}: expected Boolean, got {type(value).__name__!r}"
            )
        return value

    elif expected_type in ("Identifier", "Enum"):
        if not isinstance(value, dict):
            raise NormalizerError(
                f"{path}: expected tagged object for {expected_type}, "
                f"got {type(value).__name__!r}"
            )
        tag = value.get("type")
        if tag != expected_type:
            raise NormalizerError(
                f"{path}: tagged type mismatch — expected {expected_type!r}, "
                f"got {tag!r}"
            )
        inner = value.get("value")
        if not isinstance(inner, str) or not inner:
            raise NormalizerError(
                f"{path}: {expected_type}.value must be a non-empty string"
            )
        return {"type": expected_type, "value": unicodedata.normalize("NFC", inner)}

    elif expected_type == "Array":
        if not isinstance(value, list):
            raise NormalizerError(
                f"{path}: expected Array, got {type(value).__name__!r}"
            )
        return [
            _canonicalize_value(v, _infer_type(v, f"{path}[{i}]"), f"{path}[{i}]")
            for i, v in enumerate(value)
        ]

    elif expected_type == "Object":
        if not isinstance(value, dict):
            raise NormalizerError(
                f"{path}: expected Object, got {type(value).__name__!r}"
            )
        return {
            k: _canonicalize_value(
                value[k], _infer_type(value[k], f"{path}.{k}"), f"{path}.{k}"
            )
            for k in sorted(value.keys())
        }

    else:
        raise NormalizerError(
            f"{path}: unknown type {expected_type!r} in registry"
        )


def _infer_type(value: Any, path: str) -> str:
    """
    Infer canonical type name from a Python value for Array/Object elements.
    """
    if isinstance(value, float):
        raise NormalizerError(
            f"{path}: Float values are forbidden in canonical events"
        )
    if isinstance(value, bool):
        return "Boolean"
    if isinstance(value, int):
        return "Integer"
    if isinstance(value, str):
        return "String"
    if isinstance(value, list):
        return "Array"
    if isinstance(value, dict):
        tag = value.get("type")
        if tag in ("Identifier", "Enum"):
            return tag
        return "Object"
    raise NormalizerError(
        f"{path}: value of type {type(value).__name__!r} is not a CanonicalValue"
    )


def _canon_json(obj: Any) -> bytes:
    """Canonical JSON: keys sorted, no whitespace, UTF-8."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
