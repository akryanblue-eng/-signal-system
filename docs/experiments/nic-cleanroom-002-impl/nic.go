// Package nic implements the NIC v1.1 deterministic core: canonicalization
// and hashing primitives as specified in docs/nic-v1.1-spec.md.
package nic

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"unicode/utf8"

	"golang.org/x/text/unicode/norm"
)

// ─── §3 Canonical JSON ────────────────────────────────────────────────────────

// CanonJSON returns the canonical JSON encoding of v as a byte slice.
// v must be one of: nil, bool, int64, string, []interface{}, map[string]interface{}.
// The spec does not define behavior for float or other numeric types.
func CanonJSON(v interface{}) ([]byte, error) {
	return canonJSONValue(v)
}

func canonJSONValue(v interface{}) ([]byte, error) {
	if v == nil {
		return []byte("null"), nil
	}
	switch val := v.(type) {
	case bool:
		if val {
			return []byte("true"), nil
		}
		return []byte("false"), nil
	case int:
		return []byte(fmt.Sprintf("%d", val)), nil
	case int64:
		return []byte(fmt.Sprintf("%d", val)), nil
	case json.Number:
		// Only integers are defined; use the number as-is if it has no decimal point.
		s := string(val)
		if strings.ContainsAny(s, ".eE") {
			return nil, fmt.Errorf("canon_json: non-integer number not defined: %s", s)
		}
		return []byte(s), nil
	case float64:
		// json.Unmarshal produces float64 for numbers. Convert to int64 if it is
		// an exact integer; otherwise reject per spec.
		i := int64(val)
		if float64(i) != val {
			return nil, fmt.Errorf("canon_json: non-integer float64 not defined: %v", val)
		}
		return []byte(fmt.Sprintf("%d", i)), nil
	case string:
		return canonJSONString(val), nil
	case []interface{}:
		return canonJSONArray(val)
	case map[string]interface{}:
		return canonJSONObject(val)
	default:
		return nil, fmt.Errorf("canon_json: unsupported type %T", v)
	}
}

// canonJSONString encodes a Go string as a canonical JSON string literal.
// Non-ASCII characters are emitted as UTF-8 bytes (not \uXXXX escaped).
func canonJSONString(s string) []byte {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch {
		case r == '\\':
			b.WriteString(`\\`)
		case r == '"':
			b.WriteString(`\"`)
		case r < 0x20: // U+0000–U+001F: control characters
			// Escape as \uXXXX (4-digit lowercase hex)
			fmt.Fprintf(&b, `\u%04x`, r)
		default:
			// Emit as UTF-8 bytes, including non-ASCII.
			b.WriteRune(r)
		}
	}
	b.WriteByte('"')
	return []byte(b.String())
}

func canonJSONArray(arr []interface{}) ([]byte, error) {
	var b strings.Builder
	b.WriteByte('[')
	for i, elem := range arr {
		if i > 0 {
			b.WriteByte(',')
		}
		enc, err := canonJSONValue(elem)
		if err != nil {
			return nil, err
		}
		b.Write(enc)
	}
	b.WriteByte(']')
	return []byte(b.String()), nil
}

func canonJSONObject(obj map[string]interface{}) ([]byte, error) {
	// Sort keys by ordinary string comparison (UTF-16 code-unit order).
	// For keys consisting only of characters in BMP (U+0000–U+FFFF), UTF-16
	// code-unit order is identical to Unicode codepoint order, which for
	// ASCII-only keys is also identical to Go's byte-level string comparison.
	// The spec's registry and schema keys are all ASCII, so Go's default sort
	// is correct. For non-BMP keys the proper comparison is by UTF-16 code units;
	// implement that generically to be safe.
	keys := make([]string, 0, len(obj))
	for k := range obj {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		return utf16Less(keys[i], keys[j])
	})

	var b strings.Builder
	b.WriteByte('{')
	for i, k := range keys {
		if i > 0 {
			b.WriteByte(',')
		}
		b.Write(canonJSONString(k))
		b.WriteByte(':')
		enc, err := canonJSONValue(obj[k])
		if err != nil {
			return nil, err
		}
		b.Write(enc)
	}
	b.WriteByte('}')
	return []byte(b.String()), nil
}

// utf16Less reports whether string a comes before string b in UTF-16 code-unit
// order, as required by §3.
func utf16Less(a, b string) bool {
	ua := toUTF16Units(a)
	ub := toUTF16Units(b)
	n := len(ua)
	if len(ub) < n {
		n = len(ub)
	}
	for i := 0; i < n; i++ {
		if ua[i] != ub[i] {
			return ua[i] < ub[i]
		}
	}
	return len(ua) < len(ub)
}

// toUTF16Units converts a UTF-8 string to a slice of UTF-16 code units.
func toUTF16Units(s string) []uint16 {
	var units []uint16
	for _, r := range s {
		if r < 0x10000 {
			units = append(units, uint16(r))
		} else {
			// Encode as surrogate pair.
			r -= 0x10000
			units = append(units, uint16(0xD800+(r>>10)), uint16(0xDC00+(r&0x3FF)))
		}
	}
	return units
}

// sha256Hex returns the SHA-256 digest of data as a lowercase hex string.
func sha256Hex(data []byte) string {
	h := sha256.Sum256(data)
	return hex.EncodeToString(h[:])
}

// ─── §6 Canonical Path ────────────────────────────────────────────────────────

// CanonicalPath implements the §6 canonical path pipeline.
// Input is a string (already decoded from UTF-8 or provided as text).
// Returns the canonical path as UTF-8 bytes (as a hex string per §11.1),
// or an error whose message contains the specified substring.
//
// Note: the caller in §11.1 wants the result hex-encoded; this function
// returns the raw canonical path bytes. Use CanonicalPathHex for §11.1.
func CanonicalPath(raw string) ([]byte, error) {
	// Step 1: UTF-8 validate.
	// raw is a Go string. Go strings may contain arbitrary bytes but strings
	// coming from JSON unmarshaling are valid UTF-8. We check for invalid UTF-8
	// sequences and for unpaired surrogates (which Go represents as replacement
	// characters from invalid UTF-8 sequences — but since we get them via JSON,
	// which would have already handled this, we check for U+FFFD and explicit
	// surrogate codepoints).
	if !utf8.ValidString(raw) {
		return nil, fmt.Errorf("canonical_path: invalid UTF-8 sequence")
	}
	// Check for unpaired UTF-16 surrogates (U+D800–U+DFFF).
	for _, r := range raw {
		if r >= 0xD800 && r <= 0xDFFF {
			return nil, fmt.Errorf("canonical_path: unpaired UTF-16 surrogate")
		}
	}

	// Step 2: NFC normalize.
	s := norm.NFC.String(raw)

	// Step 3: Separator normalize — replace every '\' with '/'.
	s = strings.ReplaceAll(s, `\`, "/")

	// Step 4: Reject absolute / drive-qualified input.
	if strings.HasPrefix(s, "/") {
		return nil, fmt.Errorf("canonical_path: absolute path")
	}
	// Check if the first segment (up to first '/') contains ':'.
	firstSlash := strings.Index(s, "/")
	firstSeg := s
	if firstSlash >= 0 {
		firstSeg = s[:firstSlash]
	}
	if strings.Contains(firstSeg, ":") {
		return nil, fmt.Errorf("canonical_path: drive-qualified path")
	}

	// Step 5: Dot-segment collapse.
	parts := strings.Split(s, "/")
	var stack []string
	for _, seg := range parts {
		switch seg {
		case "", ".":
			// contributes nothing
		case "..":
			if len(stack) == 0 {
				return nil, fmt.Errorf("canonical_path: escapes repo root via '..'")
			}
			stack = stack[:len(stack)-1]
		default:
			stack = append(stack, seg)
		}
	}

	// Step 6: Emit — join with '/' and encode as UTF-8 bytes.
	result := strings.Join(stack, "/")
	return []byte(result), nil
}

// CanonicalPathHex returns the canonical path as hex-encoded bytes (for §11.1).
func CanonicalPathHex(raw string) (string, error) {
	b, err := CanonicalPath(raw)
	if err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

// ─── §5 Glob Match ────────────────────────────────────────────────────────────

// GlobMatch implements §5 glob matching.
// pattern is matched against path as a full-string anchored match,
// codepoint-for-codepoint, case-sensitive.
// Returns an error if the pattern contains forbidden characters: [ ] { } !
func GlobMatch(pattern, path string) (bool, error) {
	// Reject patterns containing forbidden characters.
	for _, r := range pattern {
		switch r {
		case '[', ']', '{', '}', '!':
			return false, fmt.Errorf("glob_match: pattern contains forbidden character: %c", r)
		}
	}
	return globMatchFull(pattern, path), nil
}

// globMatchFull performs anchored full-string glob match.
func globMatchFull(pattern, path string) bool {
	return globMatch(pattern, path)
}

// globMatch matches pattern against the entirety of s.
// This is a recursive implementation that handles *, ?, and **.
func globMatch(pattern, s string) bool {
	// Base cases.
	if pattern == "" {
		return s == ""
	}

	// Split pattern into segments for ** handling.
	// We process the pattern segment by segment when ** is involved.
	patSegs := strings.Split(pattern, "/")
	sSegs := strings.Split(s, "/")

	// Use a recursive segment-level approach for ** handling.
	return matchSegments(patSegs, sSegs)
}

// matchSegments matches pattern segments against string segments.
func matchSegments(patSegs, sSegs []string) bool {
	for len(patSegs) > 0 {
		pSeg := patSegs[0]

		if pSeg == "**" {
			// ** matches zero or more complete path segments.
			patRest := patSegs[1:]

			// Try matching the remaining pattern against every possible suffix of sSegs.
			// Zero segments: skip no sSegs.
			for i := 0; i <= len(sSegs); i++ {
				if matchSegments(patRest, sSegs[i:]) {
					return true
				}
			}
			return false
		}

		// Non-** segment: must match the first segment of sSegs.
		if len(sSegs) == 0 {
			return false
		}
		if !matchSingleSegment(pSeg, sSegs[0]) {
			return false
		}
		patSegs = patSegs[1:]
		sSegs = sSegs[1:]
	}

	// Pattern exhausted; string must also be exhausted.
	return len(sSegs) == 0
}

// matchSingleSegment matches a single pattern segment (no /) against a single
// path segment (no /). Handles * and ?.
func matchSingleSegment(pat, seg string) bool {
	// Convert to rune slices for codepoint-level matching.
	patRunes := []rune(pat)
	segRunes := []rune(seg)
	return matchRunes(patRunes, segRunes)
}

// matchRunes matches pattern runes against string runes (recursive).
func matchRunes(pat, s []rune) bool {
	for len(pat) > 0 {
		p := pat[0]
		switch p {
		case '*':
			// * matches zero or more non-'/' characters; since we are working
			// within a single segment (no '/'), * matches zero or more of anything.
			// Try matching the rest of the pattern against every suffix of s.
			for i := 0; i <= len(s); i++ {
				if matchRunes(pat[1:], s[i:]) {
					return true
				}
			}
			return false
		case '?':
			// ? matches exactly one character (not '/', but we're in a segment).
			if len(s) == 0 {
				return false
			}
			pat = pat[1:]
			s = s[1:]
		default:
			if len(s) == 0 || s[0] != p {
				return false
			}
			pat = pat[1:]
			s = s[1:]
		}
	}
	return len(s) == 0
}

// ─── §7 URL Canonicalization ──────────────────────────────────────────────────

// CanonicalizeURL implements §7 URL canonicalization.
func CanonicalizeURL(rawURL string) (string, error) {
	// Parse the URL according to the generic URI grammar described in §7.
	scheme, authority, hasAuthority, path, query, err := parseGenericURL(rawURL)
	if err != nil {
		return "", fmt.Errorf("canonicalize_url: %w", err)
	}

	// scheme: lowercase.
	scheme = strings.ToLower(scheme)

	// Parse authority into userinfo, host, port.
	var userinfo, host, port string
	if hasAuthority {
		userinfo, host, port, err = parseAuthority(authority)
		if err != nil {
			return "", fmt.Errorf("canonicalize_url: %w", err)
		}
		// host: lowercase.
		host = strings.ToLower(host)

		// port: drop if equal to scheme's default.
		if isDefaultPort(scheme, port) {
			port = ""
		}
	}

	// path: apply §7.1 dot-segment normalization.
	path = urlPathNormalize(path)

	// percent-encoding: uppercase hex digits in %XX sequences.
	path = uppercasePercentEncoding(path)
	query = uppercasePercentEncoding(query)

	// fragment: dropped entirely (already not parsed/stored).

	// Reassemble.
	return reassembleURL(scheme, userinfo, host, port, hasAuthority, path, query), nil
}

// parseGenericURL splits a URL into its components per the generic URI grammar.
// It does NOT decode percent-encoding.
func parseGenericURL(rawURL string) (scheme, authority string, hasAuthority bool, path, query string, err error) {
	// Find scheme: everything up to the first ':'.
	colonIdx := strings.Index(rawURL, ":")
	if colonIdx < 0 {
		return "", "", false, "", "", fmt.Errorf("no scheme found in URL: %q", rawURL)
	}
	scheme = rawURL[:colonIdx]
	rest := rawURL[colonIdx+1:]

	// Check for authority (starts with "//").
	if strings.HasPrefix(rest, "//") {
		hasAuthority = true
		rest = rest[2:]
		// Authority runs up to the next '/', '?', or '#'.
		end := len(rest)
		for i, c := range rest {
			if c == '/' || c == '?' || c == '#' {
				end = i
				break
			}
		}
		authority = rest[:end]
		rest = rest[end:]
	}

	// Find fragment and drop it.
	if fIdx := strings.Index(rest, "#"); fIdx >= 0 {
		rest = rest[:fIdx]
	}

	// Find query.
	if qIdx := strings.Index(rest, "?"); qIdx >= 0 {
		query = rest[qIdx+1:]
		rest = rest[:qIdx]
	}

	path = rest
	return scheme, authority, hasAuthority, path, query, nil
}

// parseAuthority splits authority into userinfo, host, port.
func parseAuthority(authority string) (userinfo, host, port string, err error) {
	// userinfo is everything before '@'.
	if atIdx := strings.LastIndex(authority, "@"); atIdx >= 0 {
		userinfo = authority[:atIdx]
		authority = authority[atIdx+1:]
	}

	// port is everything after the last ':' that is not inside '[' ']' (IPv6).
	// For IPv6 addresses like [::1]:8080, the '[' signals an IP-literal.
	if strings.HasPrefix(authority, "[") {
		// IP-literal: find the closing ']'.
		closeBracket := strings.Index(authority, "]")
		if closeBracket < 0 {
			return "", "", "", fmt.Errorf("unclosed '[' in authority: %q", authority)
		}
		host = authority[:closeBracket+1]
		rest := authority[closeBracket+1:]
		if strings.HasPrefix(rest, ":") {
			port = rest[1:]
		}
	} else {
		colonIdx := strings.LastIndex(authority, ":")
		if colonIdx >= 0 {
			host = authority[:colonIdx]
			port = authority[colonIdx+1:]
		} else {
			host = authority
		}
	}
	return userinfo, host, port, nil
}

// isDefaultPort reports whether port is the default port for scheme.
func isDefaultPort(scheme, port string) bool {
	if port == "" {
		return false
	}
	switch scheme {
	case "http":
		return port == "80"
	case "https":
		return port == "443"
	}
	return false
}

// uppercasePercentEncoding uppercases the two hex digits of each %XX sequence.
func uppercasePercentEncoding(s string) string {
	if !strings.Contains(s, "%") {
		return s
	}
	var b strings.Builder
	for i := 0; i < len(s); {
		if s[i] == '%' && i+2 < len(s) {
			b.WriteByte('%')
			b.WriteByte(upperHexDigit(s[i+1]))
			b.WriteByte(upperHexDigit(s[i+2]))
			i += 3
		} else {
			b.WriteByte(s[i])
			i++
		}
	}
	return b.String()
}

func upperHexDigit(c byte) byte {
	if c >= 'a' && c <= 'f' {
		return c - 32
	}
	return c
}

// reassembleURL reconstructs the canonical URL.
func reassembleURL(scheme, userinfo, host, port string, hasAuthority bool, path, query string) string {
	var b strings.Builder
	b.WriteString(scheme)
	b.WriteByte(':')

	if hasAuthority {
		b.WriteString("//")
		if userinfo != "" {
			b.WriteString(userinfo)
			b.WriteByte('@')
		}
		b.WriteString(host)
		if port != "" {
			b.WriteByte(':')
			b.WriteString(port)
		}
	}

	b.WriteString(path)

	if query != "" {
		b.WriteByte('?')
		b.WriteString(query)
	}

	return b.String()
}

// ─── §7.1 URL Path Dot-Segment Normalization ─────────────────────────────────

// urlPathNormalize applies §7.1 dot-segment normalization to a URL path.
func urlPathNormalize(path string) string {
	if path == "" {
		return path
	}

	leadingSlash := strings.HasPrefix(path, "/")
	segments := strings.Split(path, "/")

	var stack []string
	// If there's a leading slash, the first element from split is "".
	// Per §7.1, this empty segment is pushed like any other segment.
	for _, seg := range segments {
		switch seg {
		case ".":
			// contributes nothing
		case "..":
			if len(stack) > 0 && stack[len(stack)-1] != ".." {
				// Pop the stack (cancels the previous segment, even if it's "").
				stack = stack[:len(stack)-1]
			} else {
				// Stack is empty or top is "..": push ".." literally.
				stack = append(stack, "..")
			}
		default:
			stack = append(stack, seg)
		}
	}

	result := strings.Join(stack, "/")

	// If leading slash was present and result doesn't already start with "/", prepend it.
	if leadingSlash && !strings.HasPrefix(result, "/") {
		result = "/" + result
	}

	return result
}

// ─── §8 Hash Domain ───────────────────────────────────────────────────────────

// ComputeEdgeID implements §8 edge_id computation.
// edge_id = sha256(canon_json({"from": from, "to": to, "type": type})), hex-encoded.
func ComputeEdgeID(from_, type_, to string) (string, error) {
	obj := map[string]interface{}{
		"from": from_,
		"to":   to,
		"type": type_,
	}
	enc, err := canonJSONValue(obj)
	if err != nil {
		return "", fmt.Errorf("compute_edge_id: %w", err)
	}
	return sha256Hex(enc), nil
}

// ComputeSetHash implements §8 set_hash.
// Sort edge_ids lexicographically, feed each one's ASCII bytes into a single
// SHA-256 hash with no separator between them.
func ComputeSetHash(edgeIDs []string) string {
	sorted := make([]string, len(edgeIDs))
	copy(sorted, edgeIDs)
	sort.Strings(sorted)

	h := sha256.New()
	for _, id := range sorted {
		h.Write([]byte(id))
	}
	return hex.EncodeToString(h.Sum(nil))
}

// ComputeWitnessHash implements §8 witness_hash.
// Same as set_hash but uses the edge_ids in the order given, without sorting.
func ComputeWitnessHash(edgeIDs []string) string {
	h := sha256.New()
	for _, id := range edgeIDs {
		h.Write([]byte(id))
	}
	return hex.EncodeToString(h.Sum(nil))
}

// CheckNoUnknownEdges implements §8 UNKNOWN edge check.
// Returns true if every edge with type "UNKNOWN" has its edge_id in waivedEdgeIDs.
func CheckNoUnknownEdges(edges []Edge, waivedEdgeIDs []string) (bool, error) {
	waived := make(map[string]bool, len(waivedEdgeIDs))
	for _, id := range waivedEdgeIDs {
		waived[id] = true
	}

	for _, e := range edges {
		if e.Type == "UNKNOWN" {
			id, err := ComputeEdgeID(e.From, e.Type, e.To)
			if err != nil {
				return false, fmt.Errorf("check_no_unknown_edges: %w", err)
			}
			if !waived[id] {
				return false, nil
			}
		}
	}
	return true, nil
}

// Edge represents a directed edge with from, type, and to fields.
type Edge struct {
	From string
	Type string
	To   string
}

// ─── §9 ProofV1 Schema ────────────────────────────────────────────────────────

// VerifyProofSchema implements §9.1 verification.
// Returns true if obj is a valid ProofV1 instance.
func VerifyProofSchema(obj interface{}) bool {
	m, ok := obj.(map[string]interface{})
	if !ok {
		return false
	}

	// Exactly 7 keys required.
	required := map[string]struct{}{
		"spec_version":      {},
		"hash_alg_id":       {},
		"snapshot_mode":     {},
		"snapshot_id":       {},
		"extractor_version": {},
		"result":            {},
		"proof_payload":     {},
	}

	if len(m) != 7 {
		return false
	}
	for k := range m {
		if _, ok := required[k]; !ok {
			return false
		}
	}

	// spec_version must equal "nic.proof.v1"
	if sv, ok := m["spec_version"].(string); !ok || sv != "nic.proof.v1" {
		return false
	}

	// hash_alg_id must equal "sha256"
	if ha, ok := m["hash_alg_id"].(string); !ok || ha != "sha256" {
		return false
	}

	// snapshot_mode: one of "git_tree", "manifest"
	sm, ok := m["snapshot_mode"].(string)
	if !ok || (sm != "git_tree" && sm != "manifest") {
		return false
	}

	// snapshot_id: string, non-empty
	si, ok := m["snapshot_id"].(string)
	if !ok || si == "" {
		return false
	}

	// extractor_version: string, non-empty
	ev, ok := m["extractor_version"].(string)
	if !ok || ev == "" {
		return false
	}

	// result: one of "PASS", "FAIL"
	r, ok := m["result"].(string)
	if !ok || (r != "PASS" && r != "FAIL") {
		return false
	}

	// proof_payload: any well-formed JSON object
	_, ok = m["proof_payload"].(map[string]interface{})
	if !ok {
		return false
	}

	return true
}

// ProofSchemaHash computes proof_schema_hash per §9.2.
func ProofSchemaHash() (string, error) {
	descriptor := map[string]interface{}{
		"spec_version": "nic.proof.v1",
		"hash_alg_id":  "sha256",
		"required_fields": []interface{}{
			"extractor_version",
			"hash_alg_id",
			"proof_payload",
			"result",
			"snapshot_id",
			"snapshot_mode",
			"spec_version",
		},
		"snapshot_modes": []interface{}{"git_tree", "manifest"},
		"results":        []interface{}{"FAIL", "PASS"},
	}

	enc, err := canonJSONValue(descriptor)
	if err != nil {
		return "", fmt.Errorf("proof_schema_hash: %w", err)
	}
	return sha256Hex(enc), nil
}

// ─── §10 Registry Hash ────────────────────────────────────────────────────────

// RegistryHash computes registry_hash per §10.
// registryDoc must be the JSON-parsed representation of the registry document
// (as returned by json.Unmarshal into interface{}).
func RegistryHash(registryDoc interface{}) (string, error) {
	enc, err := canonJSONValue(registryDoc)
	if err != nil {
		return "", fmt.Errorf("registry_hash: %w", err)
	}
	return sha256Hex(enc), nil
}
