"""
Tests for EdgeExtractor v1 — the frozen recognizer registry.
"""
import pytest

from src.edge_extractor_v1 import (
    EdgeExtractorError,
    EdgeExtractorRegistry,
    REGISTRY_VERSION,
    compute_extractor_version,
)

MINIMAL_REGISTRY = {
    "version": "edge_extractor.v1",
    "recognizers": {
        "IMPORT_PY_V1": {
            "input_domain": "python_source",
            "match_rule": "ast_import_statement",
            "edge_type": "import",
        },
    },
}


class TestRegistryLoading:
    def test_loads_valid_registry(self):
        registry = EdgeExtractorRegistry(MINIMAL_REGISTRY)
        assert registry.recognizer_ids() == frozenset({"IMPORT_PY_V1"})

    def test_rejects_wrong_version(self):
        bad = {**MINIMAL_REGISTRY, "version": "edge_extractor.v2"}
        with pytest.raises(EdgeExtractorError, match="version mismatch"):
            EdgeExtractorRegistry(bad)

    def test_rejects_recognizer_missing_fields(self):
        bad = {
            "version": "edge_extractor.v1",
            "recognizers": {"X": {"input_domain": "python_source"}},
        }
        with pytest.raises(EdgeExtractorError, match="missing fields"):
            EdgeExtractorRegistry(bad)

    def test_rejects_recognizer_with_extra_fields(self):
        bad = {
            "version": "edge_extractor.v1",
            "recognizers": {
                "X": {
                    "input_domain": "python_source",
                    "match_rule": "ast_import_statement",
                    "edge_type": "import",
                    "discovery": "runtime_plugin",
                }
            },
        }
        with pytest.raises(EdgeExtractorError, match="unexpected fields"):
            EdgeExtractorRegistry(bad)

    def test_from_file_loads_frozen_registry(self):
        registry = EdgeExtractorRegistry.from_file("src/edge_extractor_v1.json")
        assert registry.recognizer_ids() == frozenset(
            {"IMPORT_PY_V1", "IMPORT_TS_V1", "URL_REFERENCE_V1", "FILE_REFERENCE_V1"}
        )


class TestGet:
    def test_get_returns_frozen_spec(self):
        registry = EdgeExtractorRegistry(MINIMAL_REGISTRY)
        spec = registry.get("IMPORT_PY_V1")
        assert spec.input_domain == "python_source"
        assert spec.match_rule == "ast_import_statement"
        assert spec.edge_type == "import"

    def test_get_unknown_recognizer_raises(self):
        registry = EdgeExtractorRegistry(MINIMAL_REGISTRY)
        with pytest.raises(EdgeExtractorError, match="Unknown recognizer_id"):
            registry.get("DOES_NOT_EXIST")


class TestExtractorVersion:
    def test_deterministic(self):
        assert compute_extractor_version(MINIMAL_REGISTRY) == compute_extractor_version(
            MINIMAL_REGISTRY
        )

    def test_changes_with_recognizer_semantics(self):
        v1 = compute_extractor_version(MINIMAL_REGISTRY)
        changed = {
            "version": "edge_extractor.v1",
            "recognizers": {
                "IMPORT_PY_V1": {
                    "input_domain": "python_source",
                    "match_rule": "ast_import_statement_v2",
                    "edge_type": "import",
                },
            },
        }
        assert compute_extractor_version(changed) != v1

    def test_changes_with_recognizer_set(self):
        v1 = compute_extractor_version(MINIMAL_REGISTRY)
        added = {
            "version": "edge_extractor.v1",
            "recognizers": {
                **MINIMAL_REGISTRY["recognizers"],
                "IMPORT_TS_V1": {
                    "input_domain": "typescript_source",
                    "match_rule": "es_import_statement",
                    "edge_type": "import",
                },
            },
        }
        assert compute_extractor_version(added) != v1

    def test_registry_exposes_its_own_extractor_version(self):
        registry = EdgeExtractorRegistry(MINIMAL_REGISTRY)
        assert registry.extractor_version == compute_extractor_version(MINIMAL_REGISTRY)

    def test_is_64_char_hex(self):
        version = compute_extractor_version(MINIMAL_REGISTRY)
        assert len(version) == 64
        int(version, 16)
