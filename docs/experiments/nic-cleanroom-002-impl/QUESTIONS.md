# QUESTIONS.md — NIC v1.1 Clean-Room Implementation Decision Log

Each entry records a decision point encountered while reading the spec and implementing the library, classified per the schema in the experiment prompt. Entries are ordered as encountered during implementation.

---

## Q1

**Section:** §3  
**Claim:** Object key sorting uses "ordinary string comparison (UTF-16 code-unit order)". For ASCII-only keys, Go's default byte-level `sort.Strings` is equivalent to UTF-16 code-unit order.  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`, `logical_consequence`

The spec states exactly "keys sorted by ordinary string comparison (UTF-16 code-unit order)". For characters in the BMP (U+0000–U+FFFF), UTF-16 code-unit order equals Unicode codepoint order. For ASCII characters (U+0000–U+007F), codepoint order equals UTF-8 byte order, which is what Go's `sort.Strings` implements. All keys actually appearing in this spec's hashed objects (`from`, `to`, `type`, `spec_version`, `hash_alg_id`, `required_fields`, `snapshot_modes`, `results`) are ASCII-only. The implementation nevertheless uses a proper UTF-16 comparison (`toUTF16Units` + `utf16Less`) to be correct for any arbitrary key, but the spec's explicit statement is the controlling rule. Resolution: implement generic UTF-16 code-unit comparison for full correctness.

---

## Q2

**Section:** §3  
**Claim:** How should `\u` control-character escapes be cased — lowercase or uppercase hex digits?  
**Type:** UNDERSPECIFIED  
**Cause:** `direct_spec_text`, `logical_consequence`

The spec says control characters (U+0000–U+001F) "escaped per the JSON grammar" and separately says non-ASCII characters are emitted literally. The JSON grammar (RFC 8259) specifies `\uXXXX` with four hex digits but does not mandate case. Standard JSON practice uses lowercase; RFC 8259 examples use uppercase. The spec provides no explicit casing rule for the `\uXXXX` escape digits (only the `%XX` percent-encoding rule in §7 explicitly mandates uppercase). Resolution: use lowercase `\u%04x` (consistent with standard Go `fmt.Sprintf` and the most common JSON convention). This is a divergence risk if the reference implementation uses uppercase.

---

## Q3

**Section:** §3  
**Claim:** How should `float64` values (produced by `json.Unmarshal` for all JSON numbers) be handled in `canon_json`?  
**Type:** UNDERSPECIFIED  
**Cause:** `direct_spec_text`, `language_conditioned`

The spec says "Non-integer or non-finite numbers never appear in any value this specification hashes, and are not defined." Go's `json.Unmarshal` into `interface{}` always produces `float64` for JSON numbers, even integers like `42` → `float64(42)`. The implementation must convert exact-integer `float64` values to `int64` and reject non-exact-integer floats. This is a Go-specific concern that wouldn't arise in, e.g., Python where `json.loads` produces `int` for integer JSON values. Resolution: detect `float64`, convert to `int64` if it is an exact integer (`float64(int64(v)) == v`), else error.

---

## Q4

**Section:** §11.1  
**Claim:** The `canonical_path` op result is described as "the canonical path bytes, hex-encoded". What exactly are the "bytes"?  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`

§6 says "encode as UTF-8 bytes" at step 6, and §11.1 says the result is "hex-encoded". So the result is: take the canonical path string, encode it as UTF-8, then hex-encode those bytes. Resolution: `hex.EncodeToString([]byte(canonicalPathString))`.

---

## Q5

**Section:** §11.1 / §5  
**Claim:** Does `glob_match` require the `path` argument to have already been canonicalized (via §6) before matching, or does it accept any path string?  
**Type:** UNDERSPECIFIED  
**Cause:** `direct_spec_text`, `explicit_exclusion`

§5 says "Matching is performed against the canonical path (§6) as a full-string (anchored) match." This means the intent is to match against *a* canonical path. However, §11.1 calls the argument `path` (a string) without saying to re-run it through §6 first. If the test corpus passes pre-canonicalized paths, treating it as an already-canonical string is correct. Re-running §6 would double-canonicalize. Resolution: treat the `path` argument as a canonical path string already — apply no further canonicalization. The matching is codepoint-for-codepoint against the string as provided.

---

## Q6

**Section:** §8  
**Claim:** What is the `set_hash` of an empty collection of edge_ids?  
**Type:** WELL_SPECIFIED_CONFIRMED / STRUCTURALLY_DETERMINED  
**Cause:** `direct_spec_text`, `logical_consequence`

The spec says "feed each one's ASCII bytes into a single SHA-256 hash, in sorted order, with no separator between them." For an empty collection, no bytes are fed into the hash. SHA-256 of zero bytes is a fixed well-known value (`e3b0c44298fc1c149afb...`). Resolution: initialize `sha256.New()`, call `Sum(nil)` without writing anything. This is the natural consequence of the spec's algorithm applied to an empty sequence.

---

## Q7

**Section:** §8  
**Claim:** `check_no_unknown_edges` — does it need to compute edge_ids to compare against `waived_edge_ids`, or does it compare edge fields directly?  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`

§8 says "for every edge with type `UNKNOWN`, that edge's edge_id appears in the caller-supplied waived-edge-id set." The waived set contains edge_id strings (hex digests), not raw edge tuples. So the implementation must call `compute_edge_id(from, "UNKNOWN", to)` for each UNKNOWN edge and check that result against the waived set. Resolution: compute edge_id for each UNKNOWN edge, look it up in the waived set.

---

## Q8

**Section:** §9.1  
**Claim:** What type must `proof_payload` be? The spec says "any well-formed JSON object; not further constrained here."  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`

"Any well-formed JSON object" means `proof_payload` must be a JSON object (not a string, number, array, null, or boolean). In Go, after JSON unmarshaling, this is `map[string]interface{}`. Resolution: require `proof_payload` to be `map[string]interface{}`.

---

## Q9

**Section:** §9.2  
**Claim:** What is the sorted order of the 7 required field names and other array fields in the `schema_descriptor`?  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`

The spec says "the 7 field names above, sorted as strings." The 7 field names are: `spec_version`, `hash_alg_id`, `snapshot_mode`, `snapshot_id`, `extractor_version`, `result`, `proof_payload`. In lexicographic (ASCII byte) order: `extractor_version`, `hash_alg_id`, `proof_payload`, `result`, `snapshot_id`, `snapshot_mode`, `spec_version`. Similarly `snapshot_modes` sorted: `["git_tree", "manifest"]`; `results` sorted: `["FAIL", "PASS"]`. The `schema_descriptor` object keys themselves must also be sorted by §3's UTF-16 order: `hash_alg_id` < `required_fields` < `results` < `snapshot_modes` < `spec_version`. Resolution: hardcode the arrays in sorted order and let `canonJSONObject` sort the keys automatically.

---

## Q10

**Section:** §7  
**Claim:** What happens when the URL has no scheme (no `:`)? The spec does not address scheme-less inputs.  
**Type:** UNDERSPECIFIED  
**Cause:** `direct_spec_text`, `explicit_exclusion`

The spec's §7 grammar assumes the generic-URI form `scheme://...`. No scheme means the input does not conform to the specified grammar. Resolution: return an error ("no scheme found in URL"). This is fail-closed consistent with the spec's overall fail-closed orientation (§9.1 explicitly says "fail-closed").

---

## Q11

**Section:** §7  
**Claim:** When reassembling the URL, should the `//` prefix be emitted for `scheme:` with no authority?  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`

§7 reassembly rule: "Omit the authority's `//` prefix only when there is no authority component to render." So URLs without `//authority` (like `file:path`) must not gain a `//`. Resolution: only emit `//` when `hasAuthority` is true.

---

## Q12

**Section:** §7  
**Claim:** Should the `?` query separator be omitted when the query string is empty (present but empty, e.g. `url?`)?  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`

§7 says "omit the `?` entirely if the (post-normalization) query is empty." An input of `https://example.com/path?` produces an empty query string after parsing, so the `?` is omitted. Resolution: only emit `?query` if `query != ""`.

---

## Q13

**Section:** §7.1  
**Claim:** In URL path dot-segment normalization, does the leading-slash "flag + reattach" approach produce the correct result when the stack-join already starts with `/`?  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`, `logical_consequence`

The spec says: "if the leading-slash flag was set and the result does not already start with `/`, prepend `/`." This conditional prevents double-slashing. For example, if the stack contains `["", "a"]` (which can't happen given the algorithm — `..` would have consumed `""` — but for safety), joining gives `/a` which already starts with `/`, so no prepend. Resolution: the conditional `!strings.HasPrefix(result, "/")` is the correct guard.

---

## Q14

**Section:** §7.1  
**Claim:** The worked example says `/../a` normalizes to `/a` (the `..` cancels the empty segment), and `/../../a` normalizes to `/../a`. Does the implementation handle consecutive `..` after the initial empty segment correctly?  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`

The spec provides an explicit worked example. The algorithm: push empty string `""` from leading `/`; first `..` cancels `""` (stack becomes `[]`); second `..` finds empty stack, so pushes `..` literally (stack: `[".."]`); `a` pushes (stack `["..","a"]`); join: `"../a"`; leading-slash flag prepends `/` since `"../a"` doesn't start with `/`; result: `"/../a"`. This matches the spec verbatim. Resolution: implement literally with the `..` on empty stack pushes `..` rule.

---

## Q15

**Section:** §5  
**Claim:** How does `**` behave in a pattern like `a/**` when the path is exactly `a` (no trailing slash, no further segments)?  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`

The spec says "a/**` matches both `a` and `a/b/c`." This means `**` matches zero or more complete path segments. When split on `/`, `a/**` gives segments `["a", "**"]` and `a` gives segments `["a"]`. After matching `a` against `a`, the remaining pattern is `["**"]` and remaining path is `[]`. The `**` must match zero segments. Resolution: in `matchSegments`, when `pSeg == "**"`, try all suffixes of `sSegs` from index 0 to `len(sSegs)` inclusive, so matching the empty suffix `sSegs[len(sSegs):]` satisfies the zero-segments case.

---

## Q16

**Section:** §5  
**Claim:** What does `**` that is NOT an entire segment (e.g., `foo**bar`) do?  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`

§5 says: "A `*` that appears within a segment alongside other characters (e.g. `foo*bar`) is the ordinary single-segment operator; only a segment consisting of exactly `**` gets directory-crossing behavior." So `foo**bar` — where `**` appears within a segment — the two `*` are each ordinary single-segment wildcards, not the `**` glob. This is structurally handled by the implementation: the pattern is split on `/` into segments, and only a segment that equals exactly `"**"` triggers cross-directory matching. A segment like `"foo**bar"` is handled by `matchSingleSegment` which treats each `*` individually as a zero-or-more-in-segment wildcard.

---

## Q17

**Section:** §8  
**Claim:** `set_hash` says "sort the edge_ids as plain strings (ordinary lexicographic order)". Does this mean Go's `sort.Strings` (UTF-8 byte order)?  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`

Edge IDs are SHA-256 hex digests (64 lowercase hex characters, ASCII). For ASCII-only strings, "ordinary lexicographic order," UTF-8 byte order, and UTF-16 code-unit order are all identical. Go's `sort.Strings` implements byte-level comparison, which is correct here. Resolution: use `sort.Strings`.

---

## Q18

**Section:** §6  
**Claim:** Step 4 says to check if the first `/`-delimited segment contains `:`. Does this check happen before or after the separator-normalization step (step 3)?  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`, `frozen_step_order`

The spec explicitly says "The step order below is frozen — every step is mandatory, none may be skipped." Step 3 replaces backslashes with forward slashes. Step 4 then checks the post-step-3 text. So `C:\Users` becomes `C:/Users` after step 3, and then the first segment `C:` contains `:`, triggering rejection. Resolution: perform step 4 check after step 3 transformation, as the frozen step order requires.

---

## Q19

**Section:** §6  
**Claim:** What is the canonical path for a path that reduces to the empty string (e.g., the input `"."`, or `"./"`)?  
**Type:** UNDERSPECIFIED  
**Cause:** `direct_spec_text`, `logical_consequence`

The spec does not explicitly address whether the empty string is a valid canonical path. §6 step 5 says `.` "contributes nothing" and empty segments contribute nothing. A path of `"."` would split into `["."]`, produce an empty stack, and emit `""` as the result. This is structurally a valid output of the algorithm. The spec has no special rejection for it. Resolution: allow the empty string as a canonical path result, following the algorithm literally.

---

## Q20

**Section:** §10  
**Claim:** `registry_hash` is described as `sha256(canon_json(<the entire registry document, exactly as loaded>))`. Does "exactly as loaded" mean the raw JSON bytes, or the parsed-then-re-serialized form?  
**Type:** WELL_SPECIFIED_CONFIRMED / EXPLICIT_SPECIFIED  
**Cause:** `direct_spec_text`

The angle-bracket notation `<the entire registry document, exactly as loaded>` combined with `canon_json(...)` means: parse the registry JSON into the canonical JSON value representation, then apply `canon_json` to re-serialize it canonically. "Exactly as loaded" distinguishes this from some hand-maintained version string — meaning no fields are omitted or transformed before hashing. The hash is over the canonical JSON of the parsed document. Resolution: `json.Unmarshal` the registry into `interface{}`, then call `canonJSONValue` on it.
