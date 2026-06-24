"""
NIC v1.1 — Normative Import Closure

Frozen primitives that close the remaining representation-ambiguity surface
so that two independent, language-agnostic implementations converge on
identical edge_ids and hashes given the same snapshot.

  Freeze Commit A — Snapshot Identity
      snapshot_id = git tree object hash at HEAD (NOT commit hash).
      Commit hash depends on author/timestamp/parent/message; tree hash is a
      pure function of content. Two repos with identical contents but
      different commit metadata must converge.

  Freeze Commit B — Glob Language
      Grammar is exactly `*`, `?`, `**`. No `[...]`, `{...}`, or `!`.
      Fail-closed: any forbidden syntax in a pattern is rejected outright.

  Freeze Commit C — Canonical Path Pipeline
      Frozen step order, no recovery, no best-effort cleanup:
        1. UTF-8 decode        4. dot-segment collapse
        2. NFC normalize       5. repo-root validation
        3. separator normalize  6. emit CanonicalPath bytes

  Freeze Commit D — ExternalResource URL Canonicalization
      scheme/host lowercased, default ports removed, path dot-segments
      normalized. Percent-encoding is NEVER decoded or re-encoded — only
      hex-digit casing is normalized. %2F never becomes "/".

  Freeze Commit E — Candidate Recognition Contract
      candidate := recognizer match (not match + extraction success).
      A match that cannot resolve deterministically emits UNKNOWN.
      UNKNOWN is a violation unless explicitly waived.

  Freeze Commit F — Hash Domain
      Every hash operates on edge_id only — never serialized edges, never
      JSON blobs. Set ordering = sorted(edge_id). Witness ordering =
      caller-supplied witness order (no re-sorting).

  Hash Algorithm Registry
      HASH_ALG is fixed to sha256. No runtime negotiation. Changing it
      requires a NIC version bump, not a configuration option.
"""
import hashlib
import json
import re
import subprocess
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlsplit, urlunsplit

HASH_ALG = "sha256"


class NICError(Exception):
    pass


def _canon_json(obj) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


# ------------------------------------------------------------------ #
# Freeze Commit A — Snapshot Identity                                   #
# ------------------------------------------------------------------ #

def compute_snapshot_id(repo_path: "str | Path" = ".") -> str:
    """
    NIC-SNAP-1 (git_tree mode): snapshot_id is the HEAD tree object hash,
    never the commit hash.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise NICError(f"Failed to compute git tree snapshot id: {e}") from e
    return result.stdout.strip()


def compute_manifest_snapshot_id(manifest: dict) -> str:
    """
    NIC-SNAP-2 (manifest mode) fallback for non-git environments.
    manifest = {"version": "snapshot.manifest.v1",
                "entries": [{"path", "sha256", "size_bytes"}, ...]}
    Mutually exclusive with git_tree mode (NIC-SNAP-3) — callers choose one.
    """
    if manifest.get("version") != "snapshot.manifest.v1":
        raise NICError(
            f"Manifest version mismatch: expected 'snapshot.manifest.v1', "
            f"got {manifest.get('version')!r}"
        )
    entries = sorted(manifest.get("entries", []), key=lambda e: e["path"])
    h = hashlib.sha256()
    for entry in entries:
        h.update(_canon_json({
            "path": entry["path"],
            "sha256": entry["sha256"],
            "size_bytes": entry["size_bytes"],
        }))
    return h.hexdigest()


# ------------------------------------------------------------------ #
# Freeze Commit B — Glob Language                                       #
# ------------------------------------------------------------------ #

_GLOB_FORBIDDEN_CHARS = frozenset("[]{}!")


def glob_match(pattern: str, path: str) -> bool:
    """
    NIC-GLOB-1: grammar is exactly `*` `?` `**`. Evaluated on canonical
    paths, bytewise case-sensitive over UTF-8 NFC strings. `*` and `?` do
    not match `/`; `**` matches across `/`.

    Fail-closed: patterns containing [ ] { } ! are rejected (NICError),
    never silently treated as literals or partially honored.
    """
    forbidden = _GLOB_FORBIDDEN_CHARS.intersection(pattern)
    if forbidden:
        raise NICError(
            f"Glob pattern {pattern!r} uses forbidden syntax {sorted(forbidden)} "
            f"— NIC-GLOB-1 permits only '*', '?', '**'"
        )
    regex = _glob_to_regex(pattern)
    return re.fullmatch(regex, path) is not None


def _glob_to_regex(pattern: str) -> str:
    """
    `**` as a whole path segment matches zero or more full directory
    segments (so `**/*.py` matches both `c.py` and `a/b/c.py`); elsewhere
    `*`/`**` only match within a single segment.
    """
    segments = pattern.split("/")
    n = len(segments)
    tokens = [_glob_segment_to_regex(seg) if seg != "**" else None for seg in segments]
    suppress_after = set()
    suppress_before = set()
    for idx, seg in enumerate(segments):
        if seg != "**":
            continue
        if n == 1:
            tokens[idx] = ".*"
        elif idx == 0:
            tokens[idx] = "(?:.*/)?"
            suppress_after.add(idx)
        elif idx == n - 1:
            tokens[idx] = "(?:/.*)?"
            suppress_before.add(idx)
        else:
            tokens[idx] = "(?:.*/)?"
            suppress_after.add(idx)

    result = tokens[0]
    for idx in range(1, n):
        if idx in suppress_before or (idx - 1) in suppress_after:
            result += tokens[idx]
        else:
            result += "/" + tokens[idx]
    return result


def _glob_segment_to_regex(segment: str) -> str:
    parts = []
    i, n = 0, len(segment)
    while i < n:
        c = segment[i]
        if c == "*":
            if i + 1 < n and segment[i + 1] == "*":
                parts.append(".*")
                i += 2
            else:
                parts.append("[^/]*")
                i += 1
        elif c == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(c))
            i += 1
    return "".join(parts)


# ------------------------------------------------------------------ #
# Freeze Commit C — Canonical Path Pipeline                             #
# ------------------------------------------------------------------ #

def canonical_path(raw: "bytes | str") -> bytes:
    """
    Frozen pipeline. Any step failing rejects with NICError — no recovery,
    no best-effort cleanup, no implementation discretion.

      1. UTF-8 decode
      2. NFC normalize
      3. separator normalize (\\ -> /), reject absolute/drive-qualified input
      4. dot-segment collapse, reject escape past repo root via '..'
      5. repo-root validation (implied by step 4's reject-on-escape)
      6. emit CanonicalPath bytes
    """
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise NICError(f"Path is not valid UTF-8: {e}") from e
    else:
        text = raw
        try:
            text.encode("utf-8")
        except UnicodeEncodeError as e:
            raise NICError(f"Path is not valid UTF-8: {e}") from e

    text = unicodedata.normalize("NFC", text)
    text = text.replace("\\", "/")

    if text.startswith("/"):
        raise NICError(f"Absolute path rejected: {text!r}")
    first_segment = text.split("/", 1)[0]
    if ":" in first_segment:
        raise NICError(f"Drive-qualified path rejected: {text!r}")

    collapsed: list[str] = []
    for seg in text.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if not collapsed:
                raise NICError(f"Path escapes repo root via '..': {text!r}")
            collapsed.pop()
        else:
            collapsed.append(seg)

    return "/".join(collapsed).encode("utf-8")


# ------------------------------------------------------------------ #
# Freeze Commit D — ExternalResource URL Canonicalization                #
# ------------------------------------------------------------------ #

_PCT_RE = re.compile(r"%([0-9A-Fa-f]{2})")
_DEFAULT_PORTS = {"http": 80, "https": 443}


def canonicalize_url(raw_url: str) -> str:
    """
    NIC-EXT-1: conservative canonical URL — treats percent-encoding as
    syntax, not semantics.

      - scheme, host lowercased
      - default port removed
      - path dot-segments normalized
      - percent-encoding octets preserved verbatim; only hex-digit casing
        is normalized to uppercase (%af -> %AF). %2F never becomes "/".
    """
    parts = urlsplit(raw_url)
    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()

    port = parts.port
    if port is not None and _DEFAULT_PORTS.get(scheme) == port:
        port = None

    userinfo = ""
    if parts.username:
        userinfo = parts.username
        if parts.password:
            userinfo += f":{parts.password}"
        userinfo += "@"

    netloc = userinfo + hostname
    if port is not None:
        netloc += f":{port}"

    path = _normalize_url_dot_segments(parts.path)
    path = _PCT_RE.sub(lambda m: "%" + m.group(1).upper(), path)
    query = _PCT_RE.sub(lambda m: "%" + m.group(1).upper(), parts.query)

    return urlunsplit((scheme, netloc, path, query, ""))


def _normalize_url_dot_segments(path: str) -> str:
    if not path:
        return path
    leading_slash = path.startswith("/")
    collapsed: list[str] = []
    for seg in path.split("/"):
        if seg == ".":
            continue
        elif seg == "..":
            if collapsed and collapsed[-1] != "..":
                collapsed.pop()
            else:
                collapsed.append(seg)
        else:
            collapsed.append(seg)
    result = "/".join(collapsed)
    if leading_slash and not result.startswith("/"):
        result = "/" + result
    return result


# ------------------------------------------------------------------ #
# ExternalResource                                                       #
# ------------------------------------------------------------------ #

_URL_SCHEMES = frozenset({"http", "https"})
_VALID_SCHEMES = frozenset({"http", "https", "exec", "env", "cli", "clock", "rng"})


@dataclass(frozen=True)
class ExternalResource:
    scheme: str
    identifier: str
    qualifiers: Optional[str] = None


def make_external_resource(
    scheme: str, identifier: str, qualifiers: Optional[str] = None
) -> ExternalResource:
    if scheme not in _VALID_SCHEMES:
        raise NICError(
            f"Unknown ExternalResource scheme {scheme!r} — "
            f"must be one of {sorted(_VALID_SCHEMES)}"
        )
    if scheme in _URL_SCHEMES:
        identifier = canonicalize_url(identifier)
    return ExternalResource(scheme=scheme, identifier=identifier, qualifiers=qualifiers)


def external_resource_to_canonical_string(resource: ExternalResource) -> str:
    """
    Canonical string form used as the `to` field when hashing an edge that
    targets an ExternalResource. Omission of qualifiers (None) is distinct
    from an empty string — the key is omitted entirely when None.
    """
    obj = {"identifier": resource.identifier, "scheme": resource.scheme}
    if resource.qualifiers is not None:
        obj["qualifiers"] = resource.qualifiers
    return _canon_json(obj).decode("utf-8")


# ------------------------------------------------------------------ #
# Edge / Freeze Commit E — Candidate Recognition Contract                #
# ------------------------------------------------------------------ #

UNKNOWN_EDGE_TYPE = "UNKNOWN"


@dataclass(frozen=True)
class Edge:
    from_: str
    type: str
    to: str
    edge_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", compute_edge_id(self.from_, self.type, self.to))


def compute_edge_id(from_: str, edge_type: str, to: str) -> str:
    """edge_id = SHA256(canon_json({from, type, to})) — HASH_ALG is fixed."""
    payload = _canon_json({"from": from_, "to": to, "type": edge_type})
    return hashlib.sha256(payload).hexdigest()


def check_no_unknown_edges(
    edges: Iterable[Edge], waived_edge_ids: frozenset = frozenset()
) -> bool:
    """
    NIC-CAND-1: a recognizer match that cannot resolve deterministically
    emits UNKNOWN. UNKNOWN is a violation unless explicitly waived by
    edge_id. Returns True iff the trace contains no un-waived UNKNOWN edges.
    """
    return all(
        not (edge.type == UNKNOWN_EDGE_TYPE and edge.edge_id not in waived_edge_ids)
        for edge in edges
    )


# ------------------------------------------------------------------ #
# Freeze Commit F — Hash Domain                                         #
# ------------------------------------------------------------------ #

def compute_set_hash(edge_ids: Iterable[str]) -> str:
    """Set ordering: sorted(edge_id). Hash domain is edge_id only."""
    h = hashlib.sha256()
    for eid in sorted(edge_ids):
        h.update(eid.encode("ascii"))
    return h.hexdigest()


def compute_witness_hash(edge_ids: Iterable[str]) -> str:
    """Witness ordering: caller-supplied order, never re-sorted."""
    h = hashlib.sha256()
    for eid in edge_ids:
        h.update(eid.encode("ascii"))
    return h.hexdigest()
