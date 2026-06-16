"""
Kernel config loader.

Single source of truth: qs-kernel.config.cjson at repo root.
If absent, built-in defaults are used (useful for tests).

Schema:
  {
    "canonicalVersion": "1.0",
    "repoMapping": {
      "compilerModules":    ["src/pcp_kernel.py"],
      "projectionModules":  ["src/pcp_term.py", "src/pcp_rewrite.py"],
      "commitExecutor":     "src/pcp_kernel.py"
    },
    "gateSpecPath":         "invariants",
    "mutationSpecPath":     "invariants/04_gate_failure_map.json",
    "intentFixturesPath":   "e12_fixtures"
  }
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path

from .canon import sha256_hex


_CANONICAL_VERSION = "1.0"

_DEFAULT_REPO_MAPPING = {
    "compilerModules": ["src/pcp_kernel.py"],
    "projectionModules": ["src/pcp_term.py", "src/pcp_rewrite.py"],
    "commitExecutor": "src/pcp_kernel.py",
}


@dataclass(frozen=True)
class RepoMapping:
    compiler_modules: tuple[str, ...]
    projection_modules: tuple[str, ...]
    commit_executor: str


@dataclass(frozen=True)
class KernelConfig:
    canonical_version: str
    repo_mapping: RepoMapping
    gate_spec_path: str
    mutation_spec_path: str
    intent_fixtures_path: str

    @property
    def canonical_version_hash(self) -> str:
        return sha256_hex(self.canonical_version.encode("utf-8"))

    def to_dict(self) -> dict:
        return {
            "canonicalVersion": self.canonical_version,
            "gateSpecPath": self.gate_spec_path,
            "intentFixturesPath": self.intent_fixtures_path,
            "mutationSpecPath": self.mutation_spec_path,
            "repoMapping": {
                "commitExecutor": self.repo_mapping.commit_executor,
                "compilerModules": sorted(self.repo_mapping.compiler_modules),
                "projectionModules": sorted(self.repo_mapping.projection_modules),
            },
        }


_DEFAULT_CONFIG = KernelConfig(
    canonical_version=_CANONICAL_VERSION,
    repo_mapping=RepoMapping(
        compiler_modules=tuple(sorted(_DEFAULT_REPO_MAPPING["compilerModules"])),
        projection_modules=tuple(sorted(_DEFAULT_REPO_MAPPING["projectionModules"])),
        commit_executor=_DEFAULT_REPO_MAPPING["commitExecutor"],
    ),
    gate_spec_path="invariants",
    mutation_spec_path="invariants/04_gate_failure_map.json",
    intent_fixtures_path="e12_fixtures",
)


def load_config(repo_path: Path) -> KernelConfig:
    """
    Load qs-kernel.config.cjson from repo_path.
    Falls back to built-in defaults if the file does not exist.
    Raises ValueError if the file exists but is malformed.
    """
    config_file = repo_path / "qs-kernel.config.cjson"
    if not config_file.exists():
        return _DEFAULT_CONFIG

    try:
        raw = json.loads(config_file.read_text("utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"qs-kernel.config.cjson is not valid JSON: {e}") from e

    rm = raw.get("repoMapping", _DEFAULT_REPO_MAPPING)
    return KernelConfig(
        canonical_version=str(raw.get("canonicalVersion", _CANONICAL_VERSION)),
        repo_mapping=RepoMapping(
            compiler_modules=tuple(sorted(rm.get("compilerModules", _DEFAULT_REPO_MAPPING["compilerModules"]))),
            projection_modules=tuple(sorted(rm.get("projectionModules", _DEFAULT_REPO_MAPPING["projectionModules"]))),
            commit_executor=str(rm.get("commitExecutor", _DEFAULT_REPO_MAPPING["commitExecutor"])),
        ),
        gate_spec_path=str(raw.get("gateSpecPath", "invariants")),
        mutation_spec_path=str(raw.get("mutationSpecPath", "invariants/04_gate_failure_map.json")),
        intent_fixtures_path=str(raw.get("intentFixturesPath", "e12_fixtures")),
    )
