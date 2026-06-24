"""
NBC — Normative Boundary Compiler

Statically enforces the epistemic firewall: no normative artifact (anything
feeding NormalizerV1, NIC-BOUNDARY, or NIC-TRACE) may depend on or reference
any informative artifact (docs, README, Notion exports, UI).

Verdict is binary. No severity levels, no warnings, no advisory mode — NBC
is a compiler for the firewall itself, not a linter.

Freeze Commit G — Boundary First:
  Execution order is NBC -> NIC-BOUNDARY -> NIC-TRACE. A NIC-TRACE judgment
  is invalid if NIC-BOUNDARY fails. A trace may still be computed for
  diagnostic purposes when the boundary fails, but it carries no
  equivalence claim (status=DIAGNOSTIC, never VALID).
"""
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

FORBIDDEN_EDGE_TYPES = frozenset({
    "import", "dynamic_import", "file_read", "codegen_dependency",
})


@dataclass(frozen=True)
class BoundaryEdge:
    from_: str
    edge_type: str
    to: str


@dataclass(frozen=True)
class BoundaryVerdict:
    status: str          # "PASS" | "FAIL"
    violations: tuple    # tuple[BoundaryEdge, ...]


class NormativeBoundaryCompiler:
    """
    root_set: normative entrypoints — files/modules that constitute the
        normative layer (e.g. normalizer_v1.py, nic_v1.py).
    forbidden_sources: path/URL prefixes identifying the informative layer
        (docs/, README, notion.so, etc.).
    forbidden_edge_types: edge types that constitute a dependency
        relationship; anything else is ignored even if it targets a
        forbidden source (e.g. a comment mentioning "docs/" is not a
        dependency).
    """

    def __init__(
        self,
        root_set: Iterable[str],
        forbidden_sources: Iterable[str],
        forbidden_edge_types: Iterable[str] = FORBIDDEN_EDGE_TYPES,
    ) -> None:
        self.root_set = frozenset(root_set)
        self.forbidden_sources = tuple(forbidden_sources)
        self.forbidden_edge_types = frozenset(forbidden_edge_types)

    def check(self, edges: Iterable[BoundaryEdge]) -> BoundaryVerdict:
        violations = [
            edge
            for edge in edges
            if edge.from_ in self.root_set
            and edge.edge_type in self.forbidden_edge_types
            and self._is_forbidden_source(edge.to)
        ]
        status = "FAIL" if violations else "PASS"
        return BoundaryVerdict(status=status, violations=tuple(violations))

    def check_repo(self, file_paths: Iterable["str | Path"]) -> BoundaryVerdict:
        """
        Scans each normative source file's AST for import statements and
        string-literal references that point at a forbidden source. This is
        the concrete enforcement mechanism: a normative module must not
        import from, or embed a path/URL literal referencing, the
        informative layer.
        """
        violations = []
        for raw_path in file_paths:
            path = Path(raw_path)
            from_ = str(path)
            for edge_type, target in _scan_python_file(path):
                if self._is_forbidden_source(target):
                    violations.append(
                        BoundaryEdge(from_=from_, edge_type=edge_type, to=target)
                    )
        status = "FAIL" if violations else "PASS"
        return BoundaryVerdict(status=status, violations=tuple(violations))

    def _is_forbidden_source(self, target: str) -> bool:
        return any(target.startswith(prefix) for prefix in self.forbidden_sources)


def _scan_python_file(path: Path) -> list[tuple[str, str]]:
    """Returns [(edge_type, target), ...] for imports and string literals."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    findings: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                findings.append(("import", alias.name))
        elif isinstance(node, ast.ImportFrom):
            findings.append(("import", node.module or ""))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            findings.append(("file_read", node.value))
    return findings


# ------------------------------------------------------------------ #
# Freeze Commit G — Boundary First                                      #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class NICTraceResult:
    status: str                    # "VALID" | "DIAGNOSTIC"
    trace_hash: Optional[str]


def gate_trace(boundary_verdict: BoundaryVerdict, compute_trace_hash) -> NICTraceResult:
    """
    NIC-TRACE judgments are invalid if NIC-BOUNDARY fails. When the boundary
    fails, a trace may still be computed for diagnostic visibility, but it
    is marked DIAGNOSTIC and carries no equivalence claim. compute_trace_hash
    is a zero-arg callable invoked lazily — only when the boundary passes
    does its result become a VALID judgment.
    """
    if boundary_verdict.status != "PASS":
        return NICTraceResult(status="DIAGNOSTIC", trace_hash=None)
    return NICTraceResult(status="VALID", trace_hash=compute_trace_hash())
