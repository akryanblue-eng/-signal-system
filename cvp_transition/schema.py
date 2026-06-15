"""
transition_morphism.json schema validation.
Returns a list of error strings; empty list = valid.
"""
import json
from pathlib import Path
from typing import Any

from .witness import REQUIRED_WITNESS_FIELDS

VALID_ARTIFACT_VALUES = {"unchanged", "modified_with_diff", "removed"}
VALID_CHANGE_TYPES = {"semantic", "structural", "deterministic"}
VALID_COMPONENTS = {"cvl1_extraction", "drift_engine", "verify_kernel", "artifact_schema"}
VALID_TRANSITION_TYPES = {"EXTENSION", "REFINEMENT", "BREAKING", "REPLACEMENT"}


def validate_schema(morphism: dict) -> list[str]:
    errors: list[str] = []

    # Required top-level fields
    for field in ("from_version", "to_version", "artifact_mapping",
                  "invariants_preserved", "invariants_added",
                  "breaking_changes", "transition_type", "independent_execution"):
        if field not in morphism:
            errors.append(f"missing required field: {field!r}")

    if errors:
        return errors  # structural issues prevent further checks

    if morphism["from_version"] != "1.2":
        errors.append(f"from_version must be '1.2', got {morphism['from_version']!r}")

    if morphism.get("transition_type") not in VALID_TRANSITION_TYPES:
        errors.append(
            f"transition_type must be one of {VALID_TRANSITION_TYPES}, "
            f"got {morphism.get('transition_type')!r}"
        )

    mapping = morphism.get("artifact_mapping", {})
    for component in VALID_COMPONENTS:
        if component not in mapping:
            errors.append(f"artifact_mapping missing component: {component!r}")
        elif mapping[component] not in VALID_ARTIFACT_VALUES:
            errors.append(
                f"artifact_mapping[{component!r}] must be one of "
                f"{VALID_ARTIFACT_VALUES}, got {mapping[component]!r}"
            )

    for entry in morphism.get("breaking_changes", []):
        if not isinstance(entry, dict):
            errors.append("breaking_changes entries must be objects")
            continue
        for field in ("component", "type", "description"):
            if field not in entry:
                errors.append(f"breaking_change entry missing field: {field!r}")
        if entry.get("component") not in VALID_COMPONENTS:
            errors.append(f"breaking_change component {entry.get('component')!r} unknown")
        if entry.get("type") not in VALID_CHANGE_TYPES:
            errors.append(f"breaking_change type {entry.get('type')!r} unknown")

    # EXTENSION and REFINEMENT must declare no breaking changes
    if morphism.get("transition_type") in ("EXTENSION", "REFINEMENT"):
        if morphism.get("breaking_changes"):
            errors.append(
                f"transition_type={morphism['transition_type']!r} must have "
                "empty breaking_changes"
            )

    witnesses = morphism.get("independent_execution", [])
    if not isinstance(witnesses, list):
        errors.append("independent_execution must be an array")
    else:
        for i, w in enumerate(witnesses):
            for field in REQUIRED_WITNESS_FIELDS:
                if field not in w:
                    errors.append(
                        f"independent_execution[{i}] missing field: {field!r}"
                    )

    return errors


def load(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)
