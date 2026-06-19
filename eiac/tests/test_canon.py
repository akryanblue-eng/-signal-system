"""Canonical encoding determinism and §1.4.6 test vectors."""
import json
from pathlib import Path

import pytest

from eiac.canon import canon, content_hash, hash_of
from eiac.tests.fixtures import (
    bundle_minimal,
    bundle_with_ops,
    env_full,
    env_minimal,
    proof_for,
)

VECTORS_PATH = Path(__file__).parent / "fixtures" / "vectors.json"


def test_canon_is_deterministic():
    obj = env_full()
    assert canon(obj.to_canon()) == canon(obj.to_canon())


def test_canon_rejects_float():
    with pytest.raises(TypeError):
        canon(1.5)


def test_canon_rejects_nan_and_infinity():
    with pytest.raises(TypeError):
        canon(float("nan"))
    with pytest.raises(TypeError):
        canon(float("inf"))


def test_canon_map_key_order_is_insensitive_to_input_order():
    a = canon({"b": 1, "a": 2})
    b = canon({"a": 2, "b": 1})
    assert a == b


def test_canon_array_order_is_significant():
    assert canon([1, 2]) != canon([2, 1])


def test_hash_is_domain_separated_by_schema_tag():
    same_shape_different_tag_a = content_hash("EIAC/A/v1", {"x": 1})
    same_shape_different_tag_b = content_hash("EIAC/B/v1", {"x": 1})
    assert same_shape_different_tag_a != same_shape_different_tag_b


@pytest.mark.parametrize(
    "name,obj",
    [
        ("env_minimal", env_minimal()),
        ("env_full", env_full()),
        ("bundle_minimal", bundle_minimal()),
        ("bundle_with_ops", bundle_with_ops()),
    ],
)
def test_against_locked_vectors(name, obj):
    vectors = json.loads(VECTORS_PATH.read_text())
    vector = vectors[name]
    assert canon(obj.to_canon()).hex() == vector["canon_hex"]
    assert hash_of(obj).hex() == vector["hash_hex"]


def test_proof_against_locked_vector():
    vectors = json.loads(VECTORS_PATH.read_text())
    vector = vectors["proof_env_full_bundle_with_ops"]
    proof = proof_for(env_full(), bundle_with_ops())
    assert canon(proof.to_canon()).hex() == vector["canon_hex"]
    assert hash_of(proof).hex() == vector["hash_hex"]
