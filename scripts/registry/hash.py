"""
registry/hash.py — deterministic hashing of registry state and schema versions.

All hashes use sha256 over a canonicalized (sort_keys) JSON representation.
Output format: "sha256:<first 24 hex chars>" — matches VCL hash convention.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from registry.runtime import RegistrySnapshot


def _major(schema_version_str: str) -> int:
    """Extract major version number from 'X.Y' or 'X' schema version string."""
    try:
        return int(str(schema_version_str).split(".")[0])
    except (ValueError, IndexError, AttributeError):
        return 0


def get_registry_version_hash(snapshot: "RegistrySnapshot") -> str:
    """
    Compute deterministic sha256 of a RegistrySnapshot.

    Canonical form sorts all lists and dict keys so equivalent snapshots
    always produce the same hash regardless of insertion order.
    """
    canonical: dict = {
        "e_types": sorted(snapshot.e_types),
        "a_types": sorted(snapshot.a_types),
        "r_types": sorted(snapshot.r_types),
        "arc_grammar_map": {
            k: sorted(v)
            for k, v in sorted(snapshot.arc_grammar_map.items())
        },
        "resolution_conditions": _sort_recursive(snapshot.resolution_conditions),
        "knob_registry": _sort_recursive(snapshot.knob_registry),
    }
    raw = json.dumps(canonical, sort_keys=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:24]}"


def _sort_recursive(obj: Any) -> Any:
    """Recursively sort dict keys for canonical JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sort_recursive(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sort_recursive(i) for i in obj]
    return obj
