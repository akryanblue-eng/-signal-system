#!/usr/bin/env python3
"""
Regenerate eiac/tests/fixtures/vectors.json from the fixture objects in
eiac/tests/fixtures.py.

Run after any change to eiac/canon.py or eiac/schema.py that is intended to
change canonical bytes or hashes. Per docs/eiac-schema-v1.0.md §1.4.6, these
vectors are normative interop anchors, not documentation -- regenerating
them is a deliberate, reviewable act, not something to do casually.

Usage:
    python eiac/tests/generate_vectors.py
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eiac.canon import canon, hash_of
from eiac.tests.fixtures import (
    bundle_minimal,
    bundle_with_ops,
    env_full,
    env_minimal,
    proof_for,
)

OUT = Path(__file__).parent / "fixtures" / "vectors.json"


def main() -> None:
    vectors = {}
    for name, obj in [
        ("env_minimal", env_minimal()),
        ("env_full", env_full()),
        ("bundle_minimal", bundle_minimal()),
        ("bundle_with_ops", bundle_with_ops()),
    ]:
        vectors[name] = {
            "canon_hex": canon(obj.to_canon()).hex(),
            "hash_hex": hash_of(obj).hex(),
        }

    proof = proof_for(env_full(), bundle_with_ops())
    vectors["proof_env_full_bundle_with_ops"] = {
        "canon_hex": canon(proof.to_canon()).hex(),
        "hash_hex": hash_of(proof).hex(),
    }

    OUT.write_text(json.dumps(vectors, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(vectors)} vectors to {OUT}")


if __name__ == "__main__":
    main()
