"""
Tests for the golden corpus manifest — an auditability artifact, not a
hand-maintained one. The committed manifest.json must always equal
compute_manifest() recomputed live; any drift (schema, registry, or
corpus changed without regenerating the manifest) must fail here.
"""
import json

from src.golden_corpus.manifest import MANIFEST_PATH, compute_manifest


class TestManifestFields:
    def test_required_keys_present(self):
        manifest = compute_manifest()
        assert set(manifest.keys()) == {
            "proof_schema_hash", "registry_hash", "hash_alg", "case_count",
        }

    def test_hash_alg_matches_registry(self):
        assert compute_manifest()["hash_alg"] == "sha256"

    def test_proof_schema_hash_is_64_char_hex(self):
        h = compute_manifest()["proof_schema_hash"]
        assert len(h) == 64
        int(h, 16)

    def test_registry_hash_is_64_char_hex(self):
        h = compute_manifest()["registry_hash"]
        assert len(h) == 64
        int(h, 16)

    def test_case_count_matches_corpus(self):
        from src.golden_corpus.manifest import CASES_PATH
        with open(CASES_PATH, encoding="utf-8") as f:
            corpus = json.load(f)
        assert compute_manifest()["case_count"] == len(corpus["cases"])

    def test_deterministic(self):
        assert compute_manifest() == compute_manifest()


class TestCommittedManifestIsCurrent:
    def test_manifest_on_disk_matches_recomputed_manifest(self):
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            on_disk = json.load(f)
        assert on_disk == compute_manifest(), (
            "golden_corpus/manifest.json is stale — regenerate with "
            "`python -m src.golden_corpus.manifest`"
        )
