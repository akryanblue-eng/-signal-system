"""
audit_extractor — pure text → Op set extractor for DSVM-0 audit.

CONTRACT (do not violate):
  - Pure function: takes source text, returns frozenset of Op strings.
  - No role awareness.  No policy lookup.  No CI logic.  No file path logic.
  - No side effects.
  - Designed to be swapped for an AST-based implementation without
    changing the call site or the Op vocabulary.

Op vocabulary (from policy/audit_policy.v1.json):
  STATE_INIT       — TravelerState(...) constructor call
  TIME_READ        — Date() call
  RANDOM_READ      — UUID() call
  (future: NETWORK_IO, FILESYSTEM_WRITE, etc.)

Extraction strategy (v1 — token-aware, not regex):
  1. Strip line comments (//) before scanning.
  2. Tokenise into identifier + punctuation tokens.
  3. Match constructor-call pattern: IDENTIFIER LPAREN where IDENTIFIER
     is in state_root_types.
  4. Match known entropy/side-effect call patterns by identifier.

This is intentionally conservative: it may produce false negatives
(unknown wrappers) but never false positives from substring collisions.
"""

from __future__ import annotations
import re
from typing import FrozenSet

# ---------------------------------------------------------------------------
# Op vocabulary — must match policy/audit_policy.v1.json
# ---------------------------------------------------------------------------

STATE_INIT  = "STATE_INIT"
TIME_READ   = "TIME_READ"
RANDOM_READ = "RANDOM_READ"

# ---------------------------------------------------------------------------
# Token-aware scanner helpers
# ---------------------------------------------------------------------------

# Tokeniser: identifier chars and single-char punctuation tokens.
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[^\s]")

_COMMENT_LINE = re.compile(r"//[^\n]*")
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(source: str) -> str:
    source = _COMMENT_BLOCK.sub(" ", source)
    source = _COMMENT_LINE.sub(" ", source)
    return source


def _tokenise(source: str) -> list[str]:
    return _TOKEN.findall(source)


def _is_call(tokens: list[str], idx: int) -> bool:
    """True if tokens[idx] is an identifier immediately followed by '('."""
    return idx + 1 < len(tokens) and tokens[idx + 1] == "("


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_ops(source: str, state_root_types: frozenset[str]) -> FrozenSet[str]:
    """Return the set of Op strings present in *source*.

    Args:
        source: Raw Swift source text.
        state_root_types: Set of type names that constitute state roots
            (loaded from policy/state_types.v1.json by the caller).

    Returns:
        Frozenset of Op string constants.  Never raises.
    """
    ops: set[str] = set()
    clean = _strip_comments(source)
    tokens = _tokenise(clean)

    for i, tok in enumerate(tokens):
        if not _is_call(tokens, i):
            continue
        if tok in state_root_types:
            ops.add(STATE_INIT)
        elif tok == "Date":
            ops.add(TIME_READ)
        elif tok == "UUID":
            ops.add(RANDOM_READ)

    return frozenset(ops)
