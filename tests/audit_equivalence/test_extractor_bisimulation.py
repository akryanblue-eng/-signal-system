"""
Bisimulation baseline: audit_extractor must agree with the grep-based
sensor on every fixture.

Purpose: proves the token-aware extractor is a valid drop-in replacement
for the grep sensor BEFORE CI is switched to use it.  Until this test
suite passes at 100%, grep remains the CI gate; the extractor is shadow-only.

Drift classification:
  UNDER-CLASSIFICATION — extractor misses an op that grep finds
  OVER-CLASSIFICATION  — extractor emits an op that grep does not find
  MATCH                — no difference (required for migration approval)
"""
import re
import subprocess
from pathlib import Path

import pytest

from src.audit_extractor import extract_ops, STATE_INIT, TIME_READ, RANDOM_READ

# ---------------------------------------------------------------------------
# State types (loaded from schema — never hardcoded in tests)
# ---------------------------------------------------------------------------
import json

_POLICY_DIR = Path(__file__).parent.parent.parent / "policy"
_STATE_TYPES = frozenset(
    json.loads((_POLICY_DIR / "state_types.v1.json").read_text())["state_root_types"]
)

# ---------------------------------------------------------------------------
# Grep-based reference extractor (the ground truth for bisimulation)
# ---------------------------------------------------------------------------

_OP_GREP_PATTERNS: list[tuple[str, str]] = [
    # (op, pattern) — must match the audit script's detection logic exactly
    (STATE_INIT,  r"TravelerState\("),
    (TIME_READ,   r"Date\(\)"),
    (RANDOM_READ, r"UUID\(\)"),
]
_COMMENT_LINE = re.compile(r"//[^\n]*")
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)


def _grep_extract(source: str) -> frozenset[str]:
    """Reference extractor: mirrors audit_dsvm.sh grep logic."""
    clean = _COMMENT_BLOCK.sub(" ", source)
    clean = _COMMENT_LINE.sub(" ", clean)
    ops: set[str] = set()
    for op, pat in _OP_GREP_PATTERNS:
        if re.search(pat, clean):
            ops.add(op)
    return frozenset(ops)


def _classify_drift(grep_ops: frozenset[str], ast_ops: frozenset[str]) -> str:
    missing = grep_ops - ast_ops
    extra   = ast_ops - grep_ops
    if missing and extra:
        return "SUBSTITUTION_DRIFT"
    if missing:
        return "UNDER-CLASSIFICATION"
    if extra:
        return "OVER-CLASSIFICATION"
    return "MATCH"


# ---------------------------------------------------------------------------
# Fixture corpus
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_FIXTURES = sorted(_FIXTURES_DIR.glob("*.swift"))


# ---------------------------------------------------------------------------
# Per-fixture bisimulation tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.stem)
def test_extractor_matches_grep(fixture: Path) -> None:
    source = fixture.read_text(encoding="utf-8")
    grep_ops = _grep_extract(source)
    ast_ops  = extract_ops(source, _STATE_TYPES)
    drift    = _classify_drift(grep_ops, ast_ops)
    assert drift == "MATCH", (
        f"Bisimulation failure in {fixture.name}\n"
        f"  drift:    {drift}\n"
        f"  grep ops: {sorted(grep_ops)}\n"
        f"  ast ops:  {sorted(ast_ops)}"
    )


# ---------------------------------------------------------------------------
# Invariant: comments must never contribute ops
# ---------------------------------------------------------------------------

def test_comment_ops_ignored() -> None:
    source = "// TravelerState()\n// Date()\n// UUID()\n"
    assert extract_ops(source, _STATE_TYPES) == frozenset()


# ---------------------------------------------------------------------------
# Invariant: substring identifiers must not trigger ops
# ---------------------------------------------------------------------------

def test_no_substring_collision() -> None:
    source = (
        "func processLatest(_ x: Bool) { x }\n"
        'let label = "OracleTravelerStateRunner"\n'
        "let speculative = true\n"
    )
    assert extract_ops(source, _STATE_TYPES) == frozenset()


# ---------------------------------------------------------------------------
# Pinned fixture expectations (golden ops per file)
# These encode the semantic contract of each fixture explicitly.
# If a fixture changes, this test surfaces the delta.
# ---------------------------------------------------------------------------

_GOLDEN: dict[str, frozenset[str]] = {
    "case_state_init":        frozenset({STATE_INIT}),
    "case_time_read":         frozenset({TIME_READ}),
    "case_mixed":             frozenset({STATE_INIT, TIME_READ}),
    "case_no_ops":            frozenset(),
    "case_substring_boundary": frozenset(),
}


@pytest.mark.parametrize("stem,expected", _GOLDEN.items())
def test_golden_ops(stem: str, expected: frozenset[str]) -> None:
    fixture = _FIXTURES_DIR / f"{stem}.swift"
    source  = fixture.read_text(encoding="utf-8")
    actual  = extract_ops(source, _STATE_TYPES)
    assert actual == expected, (
        f"Golden mismatch for {stem}\n"
        f"  expected: {sorted(expected)}\n"
        f"  actual:   {sorted(actual)}"
    )
