"""
Golden corpus conformance runner.

cases.json is intentionally plain JSON (strings, numbers, booleans, lists,
objects only) so any language's implementation can load the exact same
fixture file and reproduce these `expect` values bit-for-bit. This test is
the Python reference implementation's own conformance check against that
file — the same role any other-language implementation's test suite would
play.
"""
import json
from pathlib import Path

import pytest

from src.nic_v1 import (
    Edge,
    NICError,
    canonical_path,
    canonicalize_url,
    check_no_unknown_edges,
    compute_edge_id,
    compute_set_hash,
    compute_witness_hash,
    glob_match,
)
from src.proof_v1 import verify_proof_schema

CORPUS_PATH = Path(__file__).parent.parent / "golden_corpus" / "cases.json"


def _load_cases():
    with open(CORPUS_PATH, encoding="utf-8") as f:
        corpus = json.load(f)
    return corpus["cases"]


def _run_op(op: str, args: dict):
    if op == "canonical_path":
        return canonical_path(args["raw"]).hex()
    if op == "glob_match":
        return glob_match(args["pattern"], args["path"])
    if op == "canonicalize_url":
        return canonicalize_url(args["raw_url"])
    if op == "compute_edge_id":
        return compute_edge_id(args["from_"], args["type"], args["to"])
    if op == "compute_set_hash":
        return compute_set_hash(args["edge_ids"])
    if op == "compute_witness_hash":
        return compute_witness_hash(args["edge_ids"])
    if op == "check_no_unknown_edges":
        edges = [Edge(from_=e["from_"], type=e["type"], to=e["to"]) for e in args["edges"]]
        waived = frozenset(args["waived_edge_ids"])
        return check_no_unknown_edges(edges, waived_edge_ids=waived)
    if op == "verify_proof_schema":
        return verify_proof_schema(args["obj"])
    raise NotImplementedError(f"Unknown op {op!r} in golden corpus")


CASES = _load_cases()


class TestGoldenCorpusStructure:
    def test_corpus_version_is_frozen(self):
        with open(CORPUS_PATH, encoding="utf-8") as f:
            corpus = json.load(f)
        assert corpus["version"] == "golden_corpus.v1"

    def test_all_four_categories_present(self):
        categories = {c["category"] for c in CASES}
        assert categories == {"canonical", "boundary", "adversarial", "equivalence"}

    def test_case_ids_are_unique(self):
        ids = [c["id"] for c in CASES]
        assert len(ids) == len(set(ids))


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_golden_case(case):
    if "expect_error" in case:
        with pytest.raises(NICError, match=case["expect_error"]):
            _run_op(case["op"], case["args"])
    else:
        assert _run_op(case["op"], case["args"]) == case["expect"]


class TestEquivalenceClaim:
    """
    The equivalence category is the actual convergence proof: distinct
    source representations (reordered ids, NFC vs NFD bytes, scheme
    casing) must produce identical canonical output.
    """

    def test_set_hash_converges_across_input_order(self):
        pair = [c for c in CASES if c["id"].startswith("equiv-001")]
        assert len(pair) == 2
        assert _run_op(pair[0]["op"], pair[0]["args"]) == _run_op(pair[1]["op"], pair[1]["args"])

    def test_canonical_path_converges_across_unicode_form(self):
        pair = [c for c in CASES if c["id"].startswith("equiv-002")]
        assert len(pair) == 2
        assert _run_op(pair[0]["op"], pair[0]["args"]) == _run_op(pair[1]["op"], pair[1]["args"])

    def test_url_converges_across_scheme_casing(self):
        pair = [c for c in CASES if c["id"].startswith("equiv-003")]
        assert len(pair) == 2
        assert _run_op(pair[0]["op"], pair[0]["args"]) == _run_op(pair[1]["op"], pair[1]["args"])
