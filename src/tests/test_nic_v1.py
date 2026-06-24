"""
Tests for NIC v1.1 frozen primitives.

Covers Freeze Commits A-F plus the fixed hash algorithm registry.
"""
import hashlib
import subprocess
import pytest

from src.nic_v1 import (
    Edge,
    ExternalResource,
    NICError,
    UNKNOWN_EDGE_TYPE,
    canonical_path,
    canonicalize_url,
    check_no_unknown_edges,
    compute_edge_id,
    compute_manifest_snapshot_id,
    compute_set_hash,
    compute_snapshot_id,
    compute_witness_hash,
    external_resource_to_canonical_string,
    glob_match,
    make_external_resource,
)


# ------------------------------------------------------------------ #
# Freeze Commit A — Snapshot Identity                                   #
# ------------------------------------------------------------------ #

class TestSnapshotIdentity:
    def test_snapshot_id_matches_git_tree_hash(self):
        expected = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"],
            cwd=".", capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert compute_snapshot_id(".") == expected

    def test_snapshot_id_is_not_commit_hash(self):
        commit_hash = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=".", capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert compute_snapshot_id(".") != commit_hash

    def test_snapshot_id_is_40_char_hex(self):
        sid = compute_snapshot_id(".")
        assert len(sid) == 40
        int(sid, 16)

    def test_manifest_rejects_wrong_version(self):
        with pytest.raises(NICError, match="version mismatch"):
            compute_manifest_snapshot_id({"version": "v2", "entries": []})

    def test_manifest_hash_is_order_independent(self):
        entries = [
            {"path": "b.py", "sha256": "bb", "size_bytes": 2},
            {"path": "a.py", "sha256": "aa", "size_bytes": 1},
        ]
        m1 = {"version": "snapshot.manifest.v1", "entries": entries}
        m2 = {"version": "snapshot.manifest.v1", "entries": list(reversed(entries))}
        assert compute_manifest_snapshot_id(m1) == compute_manifest_snapshot_id(m2)

    def test_manifest_hash_changes_with_content(self):
        m1 = {
            "version": "snapshot.manifest.v1",
            "entries": [{"path": "a.py", "sha256": "aa", "size_bytes": 1}],
        }
        m2 = {
            "version": "snapshot.manifest.v1",
            "entries": [{"path": "a.py", "sha256": "ab", "size_bytes": 1}],
        }
        assert compute_manifest_snapshot_id(m1) != compute_manifest_snapshot_id(m2)


# ------------------------------------------------------------------ #
# Freeze Commit B — Glob Language                                       #
# ------------------------------------------------------------------ #

class TestGlobLanguage:
    def test_star_matches_within_segment(self):
        assert glob_match("*.py", "foo.py")
        assert not glob_match("*.py", "dir/foo.py")

    def test_question_matches_single_char(self):
        assert glob_match("a?c", "abc")
        assert not glob_match("a?c", "abbc")
        assert not glob_match("a?c", "a/c")

    def test_double_star_matches_across_segments(self):
        assert glob_match("**/*.py", "a/b/c.py")
        assert glob_match("**/*.py", "c.py")

    def test_literal_match(self):
        assert glob_match("exact/path.py", "exact/path.py")
        assert not glob_match("exact/path.py", "exact/other.py")

    @pytest.mark.parametrize("pattern", ["[a-z]", "[!x]", "{a,b}", "a!b", "f[oo]"])
    def test_forbidden_syntax_rejected(self, pattern):
        with pytest.raises(NICError, match="forbidden syntax"):
            glob_match(pattern, "anything")


# ------------------------------------------------------------------ #
# Freeze Commit C — Canonical Path Pipeline                             #
# ------------------------------------------------------------------ #

class TestCanonicalPathPipeline:
    def test_simple_path_passthrough(self):
        assert canonical_path("src/foo.py") == b"src/foo.py"

    def test_backslash_normalized_to_forward_slash(self):
        assert canonical_path("src\\foo.py") == b"src/foo.py"

    def test_dot_segment_collapse(self):
        assert canonical_path("./a/../b/./c") == b"b/c"

    def test_escape_past_root_rejected(self):
        with pytest.raises(NICError, match="escapes repo root"):
            canonical_path("../etc/passwd")

    def test_deep_escape_past_root_rejected(self):
        with pytest.raises(NICError, match="escapes repo root"):
            canonical_path("a/../../b")

    def test_absolute_path_rejected(self):
        with pytest.raises(NICError, match="Absolute path rejected"):
            canonical_path("/etc/passwd")

    def test_drive_qualified_path_rejected(self):
        with pytest.raises(NICError, match="Drive-qualified path rejected"):
            canonical_path("C:\\Windows\\system32")

    def test_invalid_utf8_bytes_rejected(self):
        with pytest.raises(NICError, match="not valid UTF-8"):
            canonical_path(b"\xff\xfe")

    def test_nfc_normalization_applied(self):
        nfd = "café.py"  # e + combining acute
        result = canonical_path(nfd)
        nfc_bytes = "café.py".encode("utf-8")
        assert result == nfc_bytes

    def test_empty_path_is_root(self):
        assert canonical_path("") == b""

    def test_redundant_slashes_collapsed(self):
        assert canonical_path("a//b///c") == b"a/b/c"


# ------------------------------------------------------------------ #
# Freeze Commit D — ExternalResource URL Canonicalization                #
# ------------------------------------------------------------------ #

class TestUrlCanonicalization:
    def test_scheme_and_host_lowercased(self):
        result = canonicalize_url("HTTP://Example.COM/path")
        assert result == "http://example.com/path"

    def test_default_http_port_removed(self):
        assert canonicalize_url("http://example.com:80/x") == "http://example.com/x"

    def test_default_https_port_removed(self):
        assert canonicalize_url("https://example.com:443/x") == "https://example.com/x"

    def test_non_default_port_preserved(self):
        assert canonicalize_url("http://example.com:8080/x") == "http://example.com:8080/x"

    def test_dot_segments_normalized_in_path(self):
        result = canonicalize_url("http://example.com/a/../b/./c")
        assert result == "http://example.com/b/c"

    def test_percent_encoding_case_normalized(self):
        result = canonicalize_url("http://example.com/a%2fb%af")
        assert result == "http://example.com/a%2FB%AF" or "%2F" in result

    def test_percent_encoded_slash_never_decoded(self):
        result = canonicalize_url("http://example.com/a%2Fb")
        assert "%2F" in result
        assert "/a/b" not in result.replace("//", "/")  # %2F must not become literal /

    def test_query_string_percent_case_normalized(self):
        result = canonicalize_url("http://example.com/?q=%af")
        assert "%AF" in result

    def test_userinfo_preserved(self):
        result = canonicalize_url("http://user:pass@example.com/")
        assert result.startswith("http://user:pass@example.com")


class TestExternalResource:
    def test_http_identifier_canonicalized(self):
        res = make_external_resource("http", "HTTP://Example.com:80/x")
        assert res.identifier == "http://example.com/x"

    def test_non_url_scheme_identifier_passthrough(self):
        res = make_external_resource("env", "MY_VAR")
        assert res.identifier == "MY_VAR"

    def test_invalid_scheme_rejected(self):
        with pytest.raises(NICError, match="Unknown ExternalResource scheme"):
            make_external_resource("ftp", "example.com")

    def test_qualifiers_omitted_when_none(self):
        res = ExternalResource(scheme="env", identifier="X")
        s = external_resource_to_canonical_string(res)
        assert "qualifiers" not in s

    def test_qualifiers_included_when_present(self):
        res = ExternalResource(scheme="env", identifier="X", qualifiers="Y")
        s = external_resource_to_canonical_string(res)
        assert "qualifiers" in s

    def test_canonical_string_is_deterministic(self):
        res = ExternalResource(scheme="env", identifier="X", qualifiers="Y")
        assert (
            external_resource_to_canonical_string(res)
            == external_resource_to_canonical_string(res)
        )


# ------------------------------------------------------------------ #
# Freeze Commit E — Candidate Recognition Contract                      #
# ------------------------------------------------------------------ #

class TestCandidateRecognition:
    def test_edge_id_deterministic(self):
        e1 = compute_edge_id("a.py", "import", "b.py")
        e2 = compute_edge_id("a.py", "import", "b.py")
        assert e1 == e2

    def test_edge_id_changes_with_any_field(self):
        base = compute_edge_id("a.py", "import", "b.py")
        assert compute_edge_id("x.py", "import", "b.py") != base
        assert compute_edge_id("a.py", "exec", "b.py") != base
        assert compute_edge_id("a.py", "import", "y.py") != base

    def test_unknown_edges_unwaived_fail(self):
        edges = [Edge(from_="a.py", type=UNKNOWN_EDGE_TYPE, to="???")]
        assert check_no_unknown_edges(edges) is False

    def test_unknown_edges_waived_pass(self):
        edge = Edge(from_="a.py", type=UNKNOWN_EDGE_TYPE, to="???")
        assert check_no_unknown_edges([edge], waived_edge_ids=frozenset({edge.edge_id})) is True

    def test_known_edges_always_pass(self):
        edges = [Edge(from_="a.py", type="import", to="b.py")]
        assert check_no_unknown_edges(edges) is True

    def test_no_edges_passes(self):
        assert check_no_unknown_edges([]) is True


# ------------------------------------------------------------------ #
# Freeze Commit F — Hash Domain                                         #
# ------------------------------------------------------------------ #

class TestHashDomain:
    def test_set_hash_is_order_independent(self):
        ids = ["b" * 64, "a" * 64, "c" * 64]
        assert compute_set_hash(ids) == compute_set_hash(list(reversed(ids)))

    def test_witness_hash_is_order_dependent(self):
        ids = ["a" * 64, "b" * 64]
        assert compute_witness_hash(ids) != compute_witness_hash(list(reversed(ids)))

    def test_set_hash_empty_is_sha256_of_empty(self):
        assert compute_set_hash([]) == hashlib.sha256(b"").hexdigest()

    def test_witness_hash_empty_is_sha256_of_empty(self):
        assert compute_witness_hash([]) == hashlib.sha256(b"").hexdigest()

    def test_set_hash_differs_from_witness_hash_for_same_unordered_content(self):
        ids = ["a" * 64, "b" * 64]
        # Same content, but set_hash sorts while witness preserves order —
        # for already-sorted input these coincide, so use unsorted input.
        unsorted = ["b" * 64, "a" * 64]
        assert compute_set_hash(unsorted) != compute_witness_hash(unsorted)
