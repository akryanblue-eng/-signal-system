"""
Golden Corpus Manifest — auditability artifact.

manifest.json lets anyone state "corpus C was validated against schema S,
registry R, algorithm A" without reconstructing that history from commits.
It is generated, not hand-edited: compute_manifest() derives every field
from the live schema, registry, and corpus, so the manifest cannot drift
from what it describes without the drift being test-detectable.
"""
import json
from pathlib import Path

from src.edge_extractor_v1 import EdgeExtractorRegistry
from src.nic_v1 import HASH_ALG
from src.proof_v1 import compute_proof_schema_hash

_CORPUS_DIR = Path(__file__).parent
CASES_PATH = _CORPUS_DIR / "cases.json"
MANIFEST_PATH = _CORPUS_DIR / "manifest.json"
REGISTRY_PATH = _CORPUS_DIR.parent / "edge_extractor_v1.json"


def compute_manifest() -> dict:
    with open(CASES_PATH, encoding="utf-8") as f:
        corpus = json.load(f)
    registry = EdgeExtractorRegistry.from_file(REGISTRY_PATH)
    return {
        "proof_schema_hash": compute_proof_schema_hash(),
        "registry_hash": registry.extractor_version,
        "hash_alg": HASH_ALG,
        "case_count": len(corpus["cases"]),
    }


def write_manifest() -> dict:
    manifest = compute_manifest()
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps(write_manifest(), indent=2, sort_keys=True))
