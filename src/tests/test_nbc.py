"""
Tests for NBC — Normative Boundary Compiler.

Covers Freeze Commit G (Boundary First) plus the NBC contract itself:
root_set / forbidden_sources / forbidden_edge_types filtering, the AST-based
repo scan, and the boundary-gates-trace ordering.
"""
import textwrap

import pytest

from src.nbc import (
    BoundaryEdge,
    FORBIDDEN_EDGE_TYPES,
    NICTraceResult,
    NormativeBoundaryCompiler,
    gate_trace,
)


# ------------------------------------------------------------------ #
# NBC Contract — check()                                               #
# ------------------------------------------------------------------ #

class TestBoundaryCheck:
    def test_clean_edges_pass(self):
        nbc = NormativeBoundaryCompiler(
            root_set={"normalizer_v1.py"},
            forbidden_sources=("docs/",),
        )
        edges = [BoundaryEdge(from_="normalizer_v1.py", edge_type="import", to="hashlib")]
        verdict = nbc.check(edges)
        assert verdict.status == "PASS"
        assert verdict.violations == ()

    def test_normative_import_of_docs_fails(self):
        nbc = NormativeBoundaryCompiler(
            root_set={"normalizer_v1.py"},
            forbidden_sources=("docs/",),
        )
        edge = BoundaryEdge(from_="normalizer_v1.py", edge_type="import", to="docs/readme")
        verdict = nbc.check([edge])
        assert verdict.status == "FAIL"
        assert verdict.violations == (edge,)

    def test_edge_outside_root_set_ignored(self):
        nbc = NormativeBoundaryCompiler(
            root_set={"normalizer_v1.py"},
            forbidden_sources=("docs/",),
        )
        edge = BoundaryEdge(from_="some_other_file.py", edge_type="import", to="docs/readme")
        verdict = nbc.check([edge])
        assert verdict.status == "PASS"

    def test_non_dependency_edge_type_ignored(self):
        nbc = NormativeBoundaryCompiler(
            root_set={"normalizer_v1.py"},
            forbidden_sources=("docs/",),
            forbidden_edge_types=FORBIDDEN_EDGE_TYPES,
        )
        edge = BoundaryEdge(from_="normalizer_v1.py", edge_type="comment_mentions", to="docs/readme")
        verdict = nbc.check([edge])
        assert verdict.status == "PASS"

    def test_target_outside_forbidden_sources_ignored(self):
        nbc = NormativeBoundaryCompiler(
            root_set={"normalizer_v1.py"},
            forbidden_sources=("docs/",),
        )
        edge = BoundaryEdge(from_="normalizer_v1.py", edge_type="import", to="hashlib")
        verdict = nbc.check([edge])
        assert verdict.status == "PASS"

    def test_no_edges_passes(self):
        nbc = NormativeBoundaryCompiler(root_set={"x.py"}, forbidden_sources=("docs/",))
        verdict = nbc.check([])
        assert verdict.status == "PASS"

    def test_multiple_violations_all_reported(self):
        nbc = NormativeBoundaryCompiler(
            root_set={"a.py", "b.py"},
            forbidden_sources=("docs/", "notion.so"),
        )
        edges = [
            BoundaryEdge(from_="a.py", edge_type="import", to="docs/x"),
            BoundaryEdge(from_="b.py", edge_type="file_read", to="notion.so/page"),
            BoundaryEdge(from_="a.py", edge_type="import", to="hashlib"),
        ]
        verdict = nbc.check(edges)
        assert verdict.status == "FAIL"
        assert len(verdict.violations) == 2


# ------------------------------------------------------------------ #
# NBC Contract — check_repo()                                          #
# ------------------------------------------------------------------ #

class TestBoundaryCheckRepo:
    def test_clean_file_passes(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("import hashlib\n\nx = 'just a string'\n", encoding="utf-8")
        nbc = NormativeBoundaryCompiler(root_set=set(), forbidden_sources=("docs/",))
        verdict = nbc.check_repo([f])
        assert verdict.status == "PASS"

    def test_import_of_forbidden_source_fails(self, tmp_path):
        f = tmp_path / "dirty.py"
        f.write_text(
            textwrap.dedent(
                """
                from docs.readme import something
                """
            ),
            encoding="utf-8",
        )
        nbc = NormativeBoundaryCompiler(root_set=set(), forbidden_sources=("docs.",))
        verdict = nbc.check_repo([f])
        assert verdict.status == "FAIL"
        assert any(v.edge_type == "import" for v in verdict.violations)

    def test_string_literal_referencing_forbidden_source_fails(self, tmp_path):
        f = tmp_path / "dirty.py"
        f.write_text('PATH = "docs/some_notion_export.md"\n', encoding="utf-8")
        nbc = NormativeBoundaryCompiler(root_set=set(), forbidden_sources=("docs/",))
        verdict = nbc.check_repo([f])
        assert verdict.status == "FAIL"
        assert any(v.edge_type == "file_read" for v in verdict.violations)

    def test_violation_records_source_file_path(self, tmp_path):
        f = tmp_path / "dirty.py"
        f.write_text('PATH = "docs/x"\n', encoding="utf-8")
        nbc = NormativeBoundaryCompiler(root_set=set(), forbidden_sources=("docs/",))
        verdict = nbc.check_repo([f])
        assert verdict.violations[0].from_ == str(f)


# ------------------------------------------------------------------ #
# Freeze Commit G — Boundary First                                      #
# ------------------------------------------------------------------ #

class TestBoundaryFirst:
    def test_boundary_pass_yields_valid_trace(self):
        nbc = NormativeBoundaryCompiler(root_set=set(), forbidden_sources=("docs/",))
        verdict = nbc.check([])
        result = gate_trace(verdict, lambda: "deadbeef")
        assert result == NICTraceResult(status="VALID", trace_hash="deadbeef")

    def test_boundary_fail_yields_diagnostic_trace_with_no_hash(self):
        nbc = NormativeBoundaryCompiler(root_set={"a.py"}, forbidden_sources=("docs/",))
        edge = BoundaryEdge(from_="a.py", edge_type="import", to="docs/x")
        verdict = nbc.check([edge])
        result = gate_trace(verdict, lambda: "deadbeef")
        assert result.status == "DIAGNOSTIC"
        assert result.trace_hash is None

    def test_trace_compute_not_invoked_when_boundary_fails(self):
        nbc = NormativeBoundaryCompiler(root_set={"a.py"}, forbidden_sources=("docs/",))
        edge = BoundaryEdge(from_="a.py", edge_type="import", to="docs/x")
        verdict = nbc.check([edge])

        calls = []

        def compute():
            calls.append(1)
            return "should-not-be-called"

        gate_trace(verdict, compute)
        assert calls == []

    def test_trace_compute_invoked_exactly_once_when_boundary_passes(self):
        nbc = NormativeBoundaryCompiler(root_set=set(), forbidden_sources=("docs/",))
        verdict = nbc.check([])

        calls = []

        def compute():
            calls.append(1)
            return "hash"

        gate_trace(verdict, compute)
        assert calls == [1]

    def test_diagnostic_status_never_valid(self):
        nbc = NormativeBoundaryCompiler(root_set={"a.py"}, forbidden_sources=("docs/",))
        edge = BoundaryEdge(from_="a.py", edge_type="import", to="docs/x")
        verdict = nbc.check([edge])
        result = gate_trace(verdict, lambda: "x")
        assert result.status != "VALID"
