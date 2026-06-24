"""
EdgeExtractor v1 — Recognizer Registry

Freezes the candidate set that NIC-CAND-1 depends on: same recognizer set
=> same candidates => same edge_ids => same hashes. Each recognizer has a
frozen identifier and frozen semantics (input_domain, match_rule,
edge_type) — an instruction-set, not a plugin interface.

extractor_version fully determines recognizer behavior: it is derived by
hashing the frozen registry content, never assigned by hand. There is no
runtime registration, no discovery, no configuration — two implementations
loading the same registry file always compute the same extractor_version.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REGISTRY_VERSION = "edge_extractor.v1"

_REQUIRED_SPEC_FIELDS = frozenset({"input_domain", "match_rule", "edge_type"})


class EdgeExtractorError(Exception):
    pass


@dataclass(frozen=True)
class RecognizerSpec:
    recognizer_id: str
    input_domain: str
    match_rule: str
    edge_type: str


class EdgeExtractorRegistry:
    def __init__(self, registry: dict) -> None:
        version = registry.get("version")
        if version != REGISTRY_VERSION:
            raise EdgeExtractorError(
                f"Registry version mismatch: expected {REGISTRY_VERSION!r}, got {version!r}"
            )
        raw_recognizers = registry.get("recognizers", {})
        recognizers = {}
        for recognizer_id, spec in raw_recognizers.items():
            spec_keys = set(spec.keys())
            missing = _REQUIRED_SPEC_FIELDS - spec_keys
            if missing:
                raise EdgeExtractorError(
                    f"Recognizer {recognizer_id!r} missing fields: {sorted(missing)}"
                )
            extra = spec_keys - _REQUIRED_SPEC_FIELDS
            if extra:
                raise EdgeExtractorError(
                    f"Recognizer {recognizer_id!r} has unexpected fields: {sorted(extra)}"
                )
            recognizers[recognizer_id] = RecognizerSpec(
                recognizer_id=recognizer_id,
                input_domain=spec["input_domain"],
                match_rule=spec["match_rule"],
                edge_type=spec["edge_type"],
            )
        self._registry = registry
        self._recognizers: dict[str, RecognizerSpec] = recognizers
        self.extractor_version = compute_extractor_version(registry)

    @classmethod
    def from_file(cls, path: "str | Path") -> "EdgeExtractorRegistry":
        with open(path, encoding="utf-8") as f:
            registry = json.load(f)
        return cls(registry)

    def get(self, recognizer_id: str) -> RecognizerSpec:
        if recognizer_id not in self._recognizers:
            raise EdgeExtractorError(f"Unknown recognizer_id {recognizer_id!r}")
        return self._recognizers[recognizer_id]

    def recognizer_ids(self) -> frozenset:
        return frozenset(self._recognizers.keys())


def compute_extractor_version(registry: dict) -> str:
    """
    extractor_version = SHA256(canon_json(registry)). Any change to a
    recognizer's semantics — or to the recognizer set itself — changes
    extractor_version automatically; there is no separately-maintained
    version string to forget to bump.
    """
    canonical = json.dumps(
        registry, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
