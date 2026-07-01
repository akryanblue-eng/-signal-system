# FREEZE.md — NIC v1.1 Clean-Room Implementation Freeze Statement

## What Is Implemented

All eight operations named in §11.1, plus `proof_schema_hash` (§9.2) and `registry_hash` (§10), are implemented in `nic.go` as a single Go package (`package nic`) with no external dependencies beyond `golang.org/x/text/unicode/norm` (for NFC normalization) and the Go standard library.

### Operations

| Op | Function | Spec section |
|----|----------|-------------|
| `canonical_path` | `CanonicalPath(raw string) ([]byte, error)` + `CanonicalPathHex` | §6 |
| `glob_match` | `GlobMatch(pattern, path string) (bool, error)` | §5 |
| `canonicalize_url` | `CanonicalizeURL(rawURL string) (string, error)` | §7 + §7.1 |
| `compute_edge_id` | `ComputeEdgeID(from_, type_, to string) (string, error)` | §8 |
| `compute_set_hash` | `ComputeSetHash(edgeIDs []string) string` | §8 |
| `compute_witness_hash` | `ComputeWitnessHash(edgeIDs []string) string` | §8 |
| `check_no_unknown_edges` | `CheckNoUnknownEdges(edges []Edge, waivedEdgeIDs []string) (bool, error)` | §8 |
| `verify_proof_schema` | `VerifyProofSchema(obj interface{}) bool` | §9.1 |
| `proof_schema_hash` | `ProofSchemaHash() (string, error)` | §9.2 |
| `registry_hash` | `RegistryHash(registryDoc interface{}) (string, error)` | §10 |

### Supporting primitives

- `CanonJSON(v interface{}) ([]byte, error)` — §3 canonical JSON encoding
- `canonJSONString`, `canonJSONArray`, `canonJSONObject` — internal helpers
- `utf16Less`, `toUTF16Units` — UTF-16 code-unit key comparison for §3 object sorting
- `parseGenericURL`, `parseAuthority`, `urlPathNormalize`, `uppercasePercentEncoding`, `reassembleURL` — §7 URL helpers
- `matchSegments`, `matchSingleSegment`, `matchRunes` — §5 glob engine
- `sha256Hex` — §4 hash rendering

### Test coverage

87 unit tests in `nic_test.go`, all passing (`go test ./... -count=1`). Tests cover:

- canon_json for all value types (null, bool, int, string with escaping, array, object with key ordering)
- canonical_path: normal paths, dot-segment collapse, backslash normalization, NFC normalization, all rejection cases (absolute, drive-qualified, escapes-root)
- glob_match: literals, `?`, `*`, `**` in all positions (prefix, suffix, middle, standalone), forbidden-character rejection, case sensitivity, full-string anchoring
- canonicalize_url: scheme/host lowercasing, default port dropping, fragment dropping, empty query, percent-encoding normalization, path dot-segment normalization (including the §7.1 worked examples), userinfo preservation
- compute_edge_id: basic hash and UNKNOWN type
- compute_set_hash: empty list, ordering independence, concatenation
- compute_witness_hash: empty list, order dependence
- check_no_unknown_edges: no-UNKNOWN, waived, not-waived, non-UNKNOWN needs no waiver
- verify_proof_schema: valid instances, all rejection cases (missing field, extra field, wrong literals, wrong types, empty non-empty fields, wrong proof_payload type)
- proof_schema_hash: determinism, hex format, manual cross-check
- registry_hash: determinism, change sensitivity

---

## Residual Uncertainty

### 1. `\u` escape casing in canonical JSON strings (Q2) — HIGH RISK

The spec says control characters are escaped "per the JSON grammar" but does not specify whether the `\uXXXX` hex digits are lowercase or uppercase. This implementation uses lowercase (``). If the reference implementation uses uppercase (``), all hashes computed over strings containing control characters will differ. The spec's percent-encoding rule (§7) explicitly mandates uppercase `%XX`; no analogous explicit rule exists for `\uXXXX`. This is the single highest-risk divergence point.

### 2. `float64` handling in canon_json (Q3) — MEDIUM RISK (language-specific)

Go's `json.Unmarshal` produces `float64` for all JSON numbers. The implementation converts exact-integer `float64` to `int64` and serializes as decimal. If a future corpus case involves a large integer (> 2^53) where `float64` loses precision, the result would be incorrect. Using `json.Decoder` with `UseNumber()` would avoid this; the current implementation does not.

### 3. `glob_match` path argument canonicalization (Q5) — MEDIUM RISK

The `path` argument to `glob_match` is treated as a pre-canonicalized string and is not re-run through §6. If the corpus passes non-canonical paths (e.g. with dot segments) and expects them to be canonicalized first, results would differ.

### 4. Empty canonical path (Q19) — LOW RISK

An input that reduces to the empty string (e.g. `"."`) yields an empty canonical path. This is what the algorithm produces; the spec does not explicitly address this edge case. If the corpus expects an error for empty-result inputs, this implementation would diverge.

### 5. `registry_hash` over parsed vs. raw JSON (Q20) — CONFIRMED CORRECT

The implementation parses the registry JSON via `json.Unmarshal` then applies `canon_json`. This matches "sha256(canon_json(<the entire registry document, exactly as loaded>))". The risk is that `json.Unmarshal` into `interface{}` loses key ordering (maps are unordered in Go), but `canon_json` re-sorts keys, so the result is deterministic regardless of input key order. This is intended behavior under §3.

---

## Highest-Risk Divergence Points (Priority Order)

1. **`\uXXXX` escape casing** (Q2): lowercase vs. uppercase hex in control-character JSON escapes. Affects all hashes computed over strings with control characters.
2. **`float64` large integer precision** (Q3): integers above 2^53 in the registry or proof objects would lose precision through `float64` and round-trip incorrectly.
3. **`proof_payload` type strictness** (Q8): the implementation requires `proof_payload` to be a JSON object (`map[string]interface{}`). If the spec intended "any JSON value" (which the prose contradicts), valid proofs would be wrongly rejected.
4. **`required_fields` sort order** (Q9): the 7 field names are hardcoded in the sorted array. If the sort is wrong, `proof_schema_hash` will not match the manifest. (This was verified by a manual cross-check test that computes the canonical JSON string by hand and compares SHA-256 values.)
5. **`**` matching exactly zero segments at start/end** (Q15): verified by test, but the recursive structure has exponential worst-case complexity for pathological patterns with many adjacent `**` segments.

---

## Files Created

- `nic.go` — library implementation (~780 lines)
- `nic_test.go` — unit tests (~520 lines, 87 tests)
- `go.mod` — Go module file (module `github.com/nic-cleanroom-002/nic`, Go 1.21)
- `go.sum` — dependency checksum for `golang.org/x/text v0.14.0`
- `QUESTIONS.md` — prose Q-log (20 entries)
- `QUESTIONS.json` — machine-readable Q-log (20 entries)
- `FREEZE.md` — this file

## Build and Test Commands

```sh
# Build
go build ./...

# Test (verbose)
go test ./... -v

# Test (summary only)
go test ./... -count=1
```

All commands run from `/home/user/nic-cleanroom-002`.

## Isolation Confirmation

No files were read, listed, or inspected outside `/home/user/nic-cleanroom-002`. No web searches were performed for project-specific terms (NIC, Normative Import Closure, edge_extractor, or similar). Generic infrastructure (SHA-256, canonical JSON, NFC normalization, URL parsing) was implemented from public language/cryptographic standards.
