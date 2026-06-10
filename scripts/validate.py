#!/usr/bin/env python3
"""
Schema validator — checks all JSON files against their schemas.
Requires: pip install jsonschema
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

LAYER_SCHEMA = {
    "stories": "story.schema.json",
    "perturbations": "perturbation.schema.json",
    "constraints": "constraint.schema.json",
    "attractors": "attractor.schema.json",
}


def load_schema(name: str) -> dict:
    return json.loads((ROOT / "schemas" / name).read_text())


def validate_dir(layer: str, schema_name: str) -> list[str]:
    errors = []
    d = ROOT / layer
    if not d.exists():
        return errors
    schema = load_schema(schema_name)
    for f in sorted(d.glob("*.json")):
        obj = json.loads(f.read_text())
        if HAS_JSONSCHEMA:
            try:
                jsonschema.validate(obj, schema)
            except jsonschema.ValidationError as e:
                errors.append(f"{f.name}: {e.message}")
        else:
            for req in schema.get("required", []):
                if req not in obj:
                    errors.append(f"{f.name}: missing required field '{req}'")
    return errors


def main() -> int:
    if not HAS_JSONSCHEMA:
        print("WARNING: jsonschema not installed. Running basic required-field checks only.")
        print("Install with: pip install jsonschema\n")

    all_errors = []
    for layer, schema_name in LAYER_SCHEMA.items():
        errs = validate_dir(layer, schema_name)
        all_errors.extend(errs)

    if all_errors:
        print(f"{len(all_errors)} validation error(s):")
        for e in all_errors:
            print(f"  {e}")
        return 1
    else:
        print("All files valid.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
