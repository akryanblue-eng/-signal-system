package nic

import (
	"encoding/hex"
	"encoding/json"
	"strings"
	"testing"
)

// ─── §3 Canonical JSON tests ──────────────────────────────────────────────────

func TestCanonJSON_Null(t *testing.T) {
	b, err := CanonJSON(nil)
	assertNoError(t, err)
	assertEqual(t, "null", string(b))
}

func TestCanonJSON_Bool(t *testing.T) {
	b, err := CanonJSON(true)
	assertNoError(t, err)
	assertEqual(t, "true", string(b))

	b, err = CanonJSON(false)
	assertNoError(t, err)
	assertEqual(t, "false", string(b))
}

func TestCanonJSON_Integer(t *testing.T) {
	b, err := CanonJSON(int64(0))
	assertNoError(t, err)
	assertEqual(t, "0", string(b))

	b, err = CanonJSON(int64(42))
	assertNoError(t, err)
	assertEqual(t, "42", string(b))

	b, err = CanonJSON(int64(-1))
	assertNoError(t, err)
	assertEqual(t, "-1", string(b))
}

func TestCanonJSON_String_Basic(t *testing.T) {
	b, err := CanonJSON("hello")
	assertNoError(t, err)
	assertEqual(t, `"hello"`, string(b))
}

func TestCanonJSON_String_EscapeBackslash(t *testing.T) {
	b, err := CanonJSON(`a\b`)
	assertNoError(t, err)
	assertEqual(t, `"a\\b"`, string(b))
}

func TestCanonJSON_String_EscapeQuote(t *testing.T) {
	b, err := CanonJSON(`a"b`)
	assertNoError(t, err)
	assertEqual(t, `"a\"b"`, string(b))
}

func TestCanonJSON_String_ControlChar(t *testing.T) {
	b, err := CanonJSON("\x00\x01\x1f")
	assertNoError(t, err)
	assertEqual(t, "\"\\u0000\\u0001\\u001f\"", string(b))
}

func TestCanonJSON_String_NonASCII_NotEscaped(t *testing.T) {
	// Non-ASCII characters must be emitted as UTF-8 bytes, not \uXXXX.
	b, err := CanonJSON("café")
	assertNoError(t, err)
	// "café" in UTF-8: c=0x63, a=0x61, f=0x66, é=0xC3 0xA9
	assertEqual(t, "\"caf\xc3\xa9\"", string(b))
}

func TestCanonJSON_Array(t *testing.T) {
	b, err := CanonJSON([]interface{}{"a", "b"})
	assertNoError(t, err)
	assertEqual(t, `["a","b"]`, string(b))
}

func TestCanonJSON_Array_Empty(t *testing.T) {
	b, err := CanonJSON([]interface{}{})
	assertNoError(t, err)
	assertEqual(t, `[]`, string(b))
}

func TestCanonJSON_Object_KeyOrder(t *testing.T) {
	// Keys must be sorted by UTF-16 code-unit order (which for ASCII is
	// lexicographic byte order).
	obj := map[string]interface{}{
		"z": "last",
		"a": "first",
		"m": "middle",
	}
	b, err := CanonJSON(obj)
	assertNoError(t, err)
	assertEqual(t, `{"a":"first","m":"middle","z":"last"}`, string(b))
}

func TestCanonJSON_Object_NoSpaces(t *testing.T) {
	obj := map[string]interface{}{"k": "v"}
	b, err := CanonJSON(obj)
	assertNoError(t, err)
	// No spaces after : or ,
	if strings.Contains(string(b), " ") {
		t.Errorf("canon_json object must not contain spaces, got: %s", string(b))
	}
}

func TestCanonJSON_EdgeIDObject(t *testing.T) {
	// §8: edge_id object has keys "from", "to", "type".
	// In sorted order: "from" < "to" < "type" (lexicographic).
	obj := map[string]interface{}{
		"from": "a",
		"to":   "b",
		"type": "imports",
	}
	b, err := CanonJSON(obj)
	assertNoError(t, err)
	assertEqual(t, `{"from":"a","to":"b","type":"imports"}`, string(b))
}

// ─── §6 Canonical Path tests ──────────────────────────────────────────────────

func TestCanonicalPath_Simple(t *testing.T) {
	b, err := CanonicalPath("foo/bar.py")
	assertNoError(t, err)
	assertEqual(t, "foo/bar.py", string(b))
}

func TestCanonicalPath_DotSegments(t *testing.T) {
	b, err := CanonicalPath("a/./b")
	assertNoError(t, err)
	assertEqual(t, "a/b", string(b))
}

func TestCanonicalPath_DoubleDotCollapse(t *testing.T) {
	b, err := CanonicalPath("a/b/../c")
	assertNoError(t, err)
	assertEqual(t, "a/c", string(b))
}

func TestCanonicalPath_TrailingSlash(t *testing.T) {
	b, err := CanonicalPath("a/b/")
	assertNoError(t, err)
	assertEqual(t, "a/b", string(b))
}

func TestCanonicalPath_DoubleSlash(t *testing.T) {
	b, err := CanonicalPath("a//b")
	assertNoError(t, err)
	assertEqual(t, "a/b", string(b))
}

func TestCanonicalPath_Backslash(t *testing.T) {
	// Backslash is replaced with forward slash.
	b, err := CanonicalPath(`a\b`)
	assertNoError(t, err)
	assertEqual(t, "a/b", string(b))
}

func TestCanonicalPath_RejectAbsolute(t *testing.T) {
	_, err := CanonicalPath("/etc/passwd")
	assertError(t, err, "absolute path")
}

func TestCanonicalPath_RejectDriveQualified(t *testing.T) {
	_, err := CanonicalPath("C:/Users/foo")
	assertError(t, err, "drive-qualified path")
}

func TestCanonicalPath_RejectEscapesRoot(t *testing.T) {
	_, err := CanonicalPath("../secret")
	assertError(t, err, "'..'")
}

func TestCanonicalPath_RejectEscapesRootDeep(t *testing.T) {
	_, err := CanonicalPath("a/../../secret")
	assertError(t, err, "'..'")
}

func TestCanonicalPath_NFCNormalization(t *testing.T) {
	// "é" as NFD (e + combining acute) should be normalized to NFC.
	nfd := "é" // NFD é
	nfc := "é"  // NFC é
	b, err := CanonicalPath("dir/" + nfd + "/file")
	assertNoError(t, err)
	assertEqual(t, "dir/"+nfc+"/file", string(b))
}

func TestCanonicalPath_Empty(t *testing.T) {
	// Empty path: all segments are empty/dot, result is "".
	b, err := CanonicalPath("")
	assertNoError(t, err)
	assertEqual(t, "", string(b))
}

func TestCanonicalPath_HexEncoded(t *testing.T) {
	// §11.1: canonical_path result is hex-encoded bytes.
	h, err := CanonicalPathHex("foo/bar")
	assertNoError(t, err)
	expected := hex.EncodeToString([]byte("foo/bar"))
	assertEqual(t, expected, h)
}

// ─── §5 Glob Match tests ──────────────────────────────────────────────────────

func TestGlobMatch_Literal(t *testing.T) {
	ok, err := GlobMatch("foo.py", "foo.py")
	assertNoError(t, err)
	assertEqual(t, true, ok)
}

func TestGlobMatch_LiteralMiss(t *testing.T) {
	ok, err := GlobMatch("foo.py", "bar.py")
	assertNoError(t, err)
	assertEqual(t, false, ok)
}

func TestGlobMatch_QuestionMark(t *testing.T) {
	ok, err := GlobMatch("fo?.py", "foo.py")
	assertNoError(t, err)
	assertEqual(t, true, ok)
}

func TestGlobMatch_QuestionMarkNoSlash(t *testing.T) {
	// ? must not match /
	ok, err := GlobMatch("a?b", "a/b")
	assertNoError(t, err)
	assertEqual(t, false, ok)
}

func TestGlobMatch_StarInSegment(t *testing.T) {
	ok, err := GlobMatch("*.py", "foo.py")
	assertNoError(t, err)
	assertEqual(t, true, ok)
}

func TestGlobMatch_StarDoesNotCrossSlash(t *testing.T) {
	ok, err := GlobMatch("*.py", "a/foo.py")
	assertNoError(t, err)
	assertEqual(t, false, ok)
}

func TestGlobMatch_StarInMiddle(t *testing.T) {
	ok, err := GlobMatch("foo*bar", "fooXXXbar")
	assertNoError(t, err)
	assertEqual(t, true, ok)
}

func TestGlobMatch_DoubleStarExact(t *testing.T) {
	// ** alone matches any string including empty.
	ok, err := GlobMatch("**", "")
	assertNoError(t, err)
	assertEqual(t, true, ok)

	ok, err = GlobMatch("**", "a/b/c")
	assertNoError(t, err)
	assertEqual(t, true, ok)
}

func TestGlobMatch_DoubleStarPrefix(t *testing.T) {
	// **/*.py matches c.py and a/b/c.py.
	ok, err := GlobMatch("**/*.py", "c.py")
	assertNoError(t, err)
	assertEqual(t, true, ok)

	ok, err = GlobMatch("**/*.py", "a/b/c.py")
	assertNoError(t, err)
	assertEqual(t, true, ok)
}

func TestGlobMatch_DoubleStarSuffix(t *testing.T) {
	// a/** matches a and a/b/c.
	ok, err := GlobMatch("a/**", "a")
	assertNoError(t, err)
	assertEqual(t, true, ok)

	ok, err = GlobMatch("a/**", "a/b/c")
	assertNoError(t, err)
	assertEqual(t, true, ok)
}

func TestGlobMatch_DoubleStarMiddle(t *testing.T) {
	// a/**/c matches a/c and a/x/y/c.
	ok, err := GlobMatch("a/**/c", "a/c")
	assertNoError(t, err)
	assertEqual(t, true, ok)

	ok, err = GlobMatch("a/**/c", "a/x/y/c")
	assertNoError(t, err)
	assertEqual(t, true, ok)
}

func TestGlobMatch_ForbiddenCharacters(t *testing.T) {
	for _, pat := range []string{"[abc]", "{a,b}", "!foo", "a]b", "a{b"} {
		_, err := GlobMatch(pat, "anything")
		if err == nil {
			t.Errorf("expected error for forbidden pattern %q, got nil", pat)
		}
	}
}

func TestGlobMatch_FullStringAnchor(t *testing.T) {
	// Pattern must match the entire string.
	ok, err := GlobMatch("foo", "foobar")
	assertNoError(t, err)
	assertEqual(t, false, ok)

	ok, err = GlobMatch("foo", "barfoo")
	assertNoError(t, err)
	assertEqual(t, false, ok)
}

func TestGlobMatch_CaseSensitive(t *testing.T) {
	ok, err := GlobMatch("Foo.py", "foo.py")
	assertNoError(t, err)
	assertEqual(t, false, ok)
}

// ─── §7 URL Canonicalization tests ───────────────────────────────────────────

func TestCanonicalizeURL_LowercaseScheme(t *testing.T) {
	got, err := CanonicalizeURL("HTTP://example.com/path")
	assertNoError(t, err)
	assertEqual(t, "http://example.com/path", got)
}

func TestCanonicalizeURL_LowercaseHost(t *testing.T) {
	got, err := CanonicalizeURL("https://EXAMPLE.COM/path")
	assertNoError(t, err)
	assertEqual(t, "https://example.com/path", got)
}

func TestCanonicalizeURL_DropDefaultPortHTTP(t *testing.T) {
	got, err := CanonicalizeURL("http://example.com:80/path")
	assertNoError(t, err)
	assertEqual(t, "http://example.com/path", got)
}

func TestCanonicalizeURL_DropDefaultPortHTTPS(t *testing.T) {
	got, err := CanonicalizeURL("https://example.com:443/path")
	assertNoError(t, err)
	assertEqual(t, "https://example.com/path", got)
}

func TestCanonicalizeURL_KeepNonDefaultPort(t *testing.T) {
	got, err := CanonicalizeURL("https://example.com:8443/path")
	assertNoError(t, err)
	assertEqual(t, "https://example.com:8443/path", got)
}

func TestCanonicalizeURL_DropFragment(t *testing.T) {
	got, err := CanonicalizeURL("https://example.com/path#section")
	assertNoError(t, err)
	assertEqual(t, "https://example.com/path", got)
}

func TestCanonicalizeURL_OmitEmptyQuery(t *testing.T) {
	got, err := CanonicalizeURL("https://example.com/path?")
	assertNoError(t, err)
	// Empty query: omit the '?'.
	assertEqual(t, "https://example.com/path", got)
}

func TestCanonicalizeURL_KeepQuery(t *testing.T) {
	got, err := CanonicalizeURL("https://example.com/path?q=1")
	assertNoError(t, err)
	assertEqual(t, "https://example.com/path?q=1", got)
}

func TestCanonicalizeURL_PercentEncodingUppercase(t *testing.T) {
	got, err := CanonicalizeURL("https://example.com/path%2ffile")
	assertNoError(t, err)
	assertEqual(t, "https://example.com/path%2Ffile", got)
}

func TestCanonicalizeURL_PathDotSegments(t *testing.T) {
	got, err := CanonicalizeURL("https://example.com/a/./b")
	assertNoError(t, err)
	assertEqual(t, "https://example.com/a/b", got)
}

func TestCanonicalizeURL_PathDoubleDot(t *testing.T) {
	got, err := CanonicalizeURL("https://example.com/a/b/../c")
	assertNoError(t, err)
	assertEqual(t, "https://example.com/a/c", got)
}

func TestCanonicalizeURL_PathLeadingDoubleDotPreserved(t *testing.T) {
	// From §7.1 worked example: /../../a → /../a
	got, err := CanonicalizeURL("https://example.com/../../a")
	assertNoError(t, err)
	assertEqual(t, "https://example.com/../a", got)
}

func TestCanonicalizeURL_PathRootedDoubleDot(t *testing.T) {
	// From §7.1 worked example: /../a → /a (leading .. cancels the empty segment from /)
	got, err := CanonicalizeURL("https://example.com/../a")
	assertNoError(t, err)
	assertEqual(t, "https://example.com/a", got)
}

func TestCanonicalizeURL_Userinfo(t *testing.T) {
	got, err := CanonicalizeURL("https://user:pass@EXAMPLE.COM/path")
	assertNoError(t, err)
	// userinfo preserved verbatim, host lowercased.
	assertEqual(t, "https://user:pass@example.com/path", got)
}

func TestCanonicalizeURL_QueryPercentEncoding(t *testing.T) {
	got, err := CanonicalizeURL("https://example.com/p?k=%2f")
	assertNoError(t, err)
	assertEqual(t, "https://example.com/p?k=%2F", got)
}

// ─── §8 Hash Domain tests ─────────────────────────────────────────────────────

func TestComputeEdgeID_Basic(t *testing.T) {
	// edge_id = sha256(canon_json({"from": from, "to": to, "type": type}))
	// Keys in sorted order: "from" < "to" < "type"
	id, err := ComputeEdgeID("a", "imports", "b")
	assertNoError(t, err)
	// Manually compute: sha256(`{"from":"a","to":"b","type":"imports"}`)
	expected := sha256Hex([]byte(`{"from":"a","to":"b","type":"imports"}`))
	assertEqual(t, expected, id)
}

func TestComputeEdgeID_UnknownType(t *testing.T) {
	// UNKNOWN type edges should be computable.
	id, err := ComputeEdgeID("x", "UNKNOWN", "y")
	assertNoError(t, err)
	expected := sha256Hex([]byte(`{"from":"x","to":"y","type":"UNKNOWN"}`))
	assertEqual(t, expected, id)
}

func TestComputeSetHash_Empty(t *testing.T) {
	// Empty list: sha256 of zero bytes.
	h := ComputeSetHash([]string{})
	expected := sha256Hex([]byte{})
	assertEqual(t, expected, h)
}

func TestComputeSetHash_Sorted(t *testing.T) {
	// set_hash sorts edge_ids before hashing.
	ids := []string{"bbb", "aaa", "ccc"}
	h := ComputeSetHash(ids)
	// Expect sha256("aaabbbccc")
	expected := sha256Hex([]byte("aaabbbccc"))
	assertEqual(t, expected, h)
}

func TestComputeSetHash_OrderIndependent(t *testing.T) {
	// set_hash is order-independent.
	h1 := ComputeSetHash([]string{"x", "y"})
	h2 := ComputeSetHash([]string{"y", "x"})
	assertEqual(t, h1, h2)
}

func TestComputeWitnessHash_Empty(t *testing.T) {
	h := ComputeWitnessHash([]string{})
	expected := sha256Hex([]byte{})
	assertEqual(t, expected, h)
}

func TestComputeWitnessHash_OrderDependent(t *testing.T) {
	// witness_hash respects order; different order → different hash.
	h1 := ComputeWitnessHash([]string{"x", "y"})
	h2 := ComputeWitnessHash([]string{"y", "x"})
	if h1 == h2 {
		t.Error("witness_hash should be order-dependent, but x,y and y,x gave the same hash")
	}
}

func TestComputeWitnessHash_Basic(t *testing.T) {
	// witness_hash feeds bytes in order, no separator.
	ids := []string{"aaa", "bbb"}
	h := ComputeWitnessHash(ids)
	expected := sha256Hex([]byte("aaabbb"))
	assertEqual(t, expected, h)
}

func TestCheckNoUnknownEdges_NoUnknown(t *testing.T) {
	edges := []Edge{
		{From: "a", Type: "imports", To: "b"},
	}
	ok, err := CheckNoUnknownEdges(edges, nil)
	assertNoError(t, err)
	assertEqual(t, true, ok)
}

func TestCheckNoUnknownEdges_UnknownWaived(t *testing.T) {
	edges := []Edge{
		{From: "a", Type: "UNKNOWN", To: "b"},
	}
	id, err := ComputeEdgeID("a", "UNKNOWN", "b")
	assertNoError(t, err)
	ok, err := CheckNoUnknownEdges(edges, []string{id})
	assertNoError(t, err)
	assertEqual(t, true, ok)
}

func TestCheckNoUnknownEdges_UnknownNotWaived(t *testing.T) {
	edges := []Edge{
		{From: "a", Type: "UNKNOWN", To: "b"},
	}
	ok, err := CheckNoUnknownEdges(edges, []string{})
	assertNoError(t, err)
	assertEqual(t, false, ok)
}

func TestCheckNoUnknownEdges_NonUnknownNeedsNoWaiver(t *testing.T) {
	// Edges that are not type UNKNOWN never require waiving.
	edges := []Edge{
		{From: "a", Type: "imports", To: "b"},
		{From: "c", Type: "uses", To: "d"},
	}
	ok, err := CheckNoUnknownEdges(edges, []string{})
	assertNoError(t, err)
	assertEqual(t, true, ok)
}

// ─── §9 ProofV1 Schema tests ──────────────────────────────────────────────────

func TestVerifyProofSchema_Valid(t *testing.T) {
	obj := map[string]interface{}{
		"spec_version":      "nic.proof.v1",
		"hash_alg_id":       "sha256",
		"snapshot_mode":     "git_tree",
		"snapshot_id":       "abc123",
		"extractor_version": "1.0.0",
		"result":            "PASS",
		"proof_payload":     map[string]interface{}{},
	}
	assertEqual(t, true, VerifyProofSchema(obj))
}

func TestVerifyProofSchema_ValidManifest(t *testing.T) {
	obj := map[string]interface{}{
		"spec_version":      "nic.proof.v1",
		"hash_alg_id":       "sha256",
		"snapshot_mode":     "manifest",
		"snapshot_id":       "deadbeef",
		"extractor_version": "v2",
		"result":            "FAIL",
		"proof_payload":     map[string]interface{}{"key": "value"},
	}
	assertEqual(t, true, VerifyProofSchema(obj))
}

func TestVerifyProofSchema_NotObject(t *testing.T) {
	assertEqual(t, false, VerifyProofSchema("not an object"))
	assertEqual(t, false, VerifyProofSchema(nil))
	assertEqual(t, false, VerifyProofSchema([]interface{}{}))
}

func TestVerifyProofSchema_MissingField(t *testing.T) {
	obj := map[string]interface{}{
		"spec_version":      "nic.proof.v1",
		"hash_alg_id":       "sha256",
		"snapshot_mode":     "git_tree",
		"snapshot_id":       "abc123",
		"extractor_version": "1.0.0",
		"result":            "PASS",
		// proof_payload missing
	}
	assertEqual(t, false, VerifyProofSchema(obj))
}

func TestVerifyProofSchema_ExtraField(t *testing.T) {
	obj := map[string]interface{}{
		"spec_version":      "nic.proof.v1",
		"hash_alg_id":       "sha256",
		"snapshot_mode":     "git_tree",
		"snapshot_id":       "abc123",
		"extractor_version": "1.0.0",
		"result":            "PASS",
		"proof_payload":     map[string]interface{}{},
		"extra_key":         "not allowed",
	}
	assertEqual(t, false, VerifyProofSchema(obj))
}

func TestVerifyProofSchema_WrongSpecVersion(t *testing.T) {
	obj := map[string]interface{}{
		"spec_version":      "nic.proof.v2", // wrong
		"hash_alg_id":       "sha256",
		"snapshot_mode":     "git_tree",
		"snapshot_id":       "abc123",
		"extractor_version": "1.0.0",
		"result":            "PASS",
		"proof_payload":     map[string]interface{}{},
	}
	assertEqual(t, false, VerifyProofSchema(obj))
}

func TestVerifyProofSchema_WrongHashAlg(t *testing.T) {
	obj := map[string]interface{}{
		"spec_version":      "nic.proof.v1",
		"hash_alg_id":       "sha512", // wrong
		"snapshot_mode":     "git_tree",
		"snapshot_id":       "abc123",
		"extractor_version": "1.0.0",
		"result":            "PASS",
		"proof_payload":     map[string]interface{}{},
	}
	assertEqual(t, false, VerifyProofSchema(obj))
}

func TestVerifyProofSchema_WrongSnapshotMode(t *testing.T) {
	obj := map[string]interface{}{
		"spec_version":      "nic.proof.v1",
		"hash_alg_id":       "sha256",
		"snapshot_mode":     "filesystem", // wrong
		"snapshot_id":       "abc123",
		"extractor_version": "1.0.0",
		"result":            "PASS",
		"proof_payload":     map[string]interface{}{},
	}
	assertEqual(t, false, VerifyProofSchema(obj))
}

func TestVerifyProofSchema_WrongResult(t *testing.T) {
	obj := map[string]interface{}{
		"spec_version":      "nic.proof.v1",
		"hash_alg_id":       "sha256",
		"snapshot_mode":     "git_tree",
		"snapshot_id":       "abc123",
		"extractor_version": "1.0.0",
		"result":            "DIAGNOSTIC", // wrong — not valid at this layer
		"proof_payload":     map[string]interface{}{},
	}
	assertEqual(t, false, VerifyProofSchema(obj))
}

func TestVerifyProofSchema_EmptySnapshotID(t *testing.T) {
	obj := map[string]interface{}{
		"spec_version":      "nic.proof.v1",
		"hash_alg_id":       "sha256",
		"snapshot_mode":     "git_tree",
		"snapshot_id":       "", // must be non-empty
		"extractor_version": "1.0.0",
		"result":            "PASS",
		"proof_payload":     map[string]interface{}{},
	}
	assertEqual(t, false, VerifyProofSchema(obj))
}

func TestVerifyProofSchema_EmptyExtractorVersion(t *testing.T) {
	obj := map[string]interface{}{
		"spec_version":      "nic.proof.v1",
		"hash_alg_id":       "sha256",
		"snapshot_mode":     "git_tree",
		"snapshot_id":       "abc123",
		"extractor_version": "", // must be non-empty
		"result":            "PASS",
		"proof_payload":     map[string]interface{}{},
	}
	assertEqual(t, false, VerifyProofSchema(obj))
}

func TestVerifyProofSchema_ProofPayloadNotObject(t *testing.T) {
	obj := map[string]interface{}{
		"spec_version":      "nic.proof.v1",
		"hash_alg_id":       "sha256",
		"snapshot_mode":     "git_tree",
		"snapshot_id":       "abc123",
		"extractor_version": "1.0.0",
		"result":            "PASS",
		"proof_payload":     "not an object", // wrong type
	}
	assertEqual(t, false, VerifyProofSchema(obj))
}

// ─── §9.2 Proof Schema Hash tests ────────────────────────────────────────────

func TestProofSchemaHash_Deterministic(t *testing.T) {
	h1, err := ProofSchemaHash()
	assertNoError(t, err)
	h2, err := ProofSchemaHash()
	assertNoError(t, err)
	assertEqual(t, h1, h2)
}

func TestProofSchemaHash_IsHex64(t *testing.T) {
	h, err := ProofSchemaHash()
	assertNoError(t, err)
	if len(h) != 64 {
		t.Errorf("proof_schema_hash expected 64 hex chars, got %d: %q", len(h), h)
	}
	for _, c := range h {
		if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')) {
			t.Errorf("proof_schema_hash contains non-lowercase-hex character: %c", c)
		}
	}
}

func TestProofSchemaHash_MatchesManualComputation(t *testing.T) {
	// Compute manually: the descriptor object with known sorted keys.
	// required_fields sorted: extractor_version, hash_alg_id, proof_payload,
	//   result, snapshot_id, snapshot_mode, spec_version
	// snapshot_modes sorted: git_tree, manifest
	// results sorted: FAIL, PASS
	// Object keys sorted (UTF-16 order): hash_alg_id, required_fields, results,
	//   snapshot_modes, spec_version
	descriptor := `{"hash_alg_id":"sha256","required_fields":["extractor_version","hash_alg_id","proof_payload","result","snapshot_id","snapshot_mode","spec_version"],"results":["FAIL","PASS"],"snapshot_modes":["git_tree","manifest"],"spec_version":"nic.proof.v1"}`
	expected := sha256Hex([]byte(descriptor))

	got, err := ProofSchemaHash()
	assertNoError(t, err)
	assertEqual(t, expected, got)
}

// ─── §10 Registry Hash tests ──────────────────────────────────────────────────

func TestRegistryHash_Basic(t *testing.T) {
	registryJSON := `{
		"version": "edge_extractor.v1",
		"recognizers": {
			"import_py": {
				"input_domain": "python",
				"match_rule": "import .*",
				"edge_type": "imports"
			}
		}
	}`
	var doc interface{}
	if err := json.Unmarshal([]byte(registryJSON), &doc); err != nil {
		t.Fatalf("failed to parse registry JSON: %v", err)
	}
	h, err := RegistryHash(doc)
	assertNoError(t, err)
	if len(h) != 64 {
		t.Errorf("registry_hash expected 64 hex chars, got %d", len(h))
	}
}

func TestRegistryHash_Deterministic(t *testing.T) {
	registryJSON := `{"version":"edge_extractor.v1","recognizers":{}}`
	var doc interface{}
	json.Unmarshal([]byte(registryJSON), &doc)

	h1, _ := RegistryHash(doc)
	h2, _ := RegistryHash(doc)
	assertEqual(t, h1, h2)
}

func TestRegistryHash_ChangeSensitive(t *testing.T) {
	// A change in the registry must change the hash.
	var doc1, doc2 interface{}
	json.Unmarshal([]byte(`{"version":"edge_extractor.v1","recognizers":{}}`), &doc1)
	json.Unmarshal([]byte(`{"version":"edge_extractor.v2","recognizers":{}}`), &doc2)

	h1, _ := RegistryHash(doc1)
	h2, _ := RegistryHash(doc2)
	if h1 == h2 {
		t.Error("registry_hash must change when content changes")
	}
}

// ─── Integration tests ───────────────────────────────────────────────────────

func TestEdgeIDConsistency(t *testing.T) {
	// check_no_unknown_edges computes edge_ids internally and must match
	// what compute_edge_id returns directly.
	id, err := ComputeEdgeID("src.py", "UNKNOWN", "dst.js")
	assertNoError(t, err)

	edges := []Edge{{From: "src.py", Type: "UNKNOWN", To: "dst.js"}}

	// With the correct ID in the waived set → true.
	ok, err := CheckNoUnknownEdges(edges, []string{id})
	assertNoError(t, err)
	assertEqual(t, true, ok)

	// With wrong ID → false.
	ok, err = CheckNoUnknownEdges(edges, []string{"wrongid"})
	assertNoError(t, err)
	assertEqual(t, false, ok)
}

func TestSetHashVsWitnessHash(t *testing.T) {
	// For a single element, set_hash and witness_hash are identical.
	ids := []string{"abc123"}
	sh := ComputeSetHash(ids)
	wh := ComputeWitnessHash(ids)
	assertEqual(t, sh, wh)
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

func assertNoError(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func assertError(t *testing.T, err error, substr string) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected error containing %q, got nil", substr)
	}
	if !strings.Contains(err.Error(), substr) {
		t.Fatalf("expected error containing %q, got: %v", substr, err)
	}
}

func assertEqual(t *testing.T, expected, actual interface{}) {
	t.Helper()
	if expected != actual {
		t.Fatalf("expected %v, got %v", expected, actual)
	}
}
