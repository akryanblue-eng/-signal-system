# NIC v1.1 — Normative Import Closure: Frozen Specification

## 1. Scope

This document specifies the **deterministic core** of NIC v1.1: the
canonicalization and hashing primitives that any conforming implementation,
in any language, must reproduce bit-for-bit given the same inputs.

Out of scope: recognizer/extraction logic (which recognizer matches which
source construct and how), the NBC boundary-enforcement layer, and snapshot
acquisition (e.g. walking a git tree to discover files). Only the pure
functions below are specified here.

## 2. Conformance

An implementation conforms if, for every case in the language-agnostic
golden corpus (`cases.json`, format in §11), it produces the case's
`expect` value exactly, or raises an error whose message contains
`expect_error` as a substring — and if it independently recomputes
`proof_schema_hash` and `registry_hash` (§9.2, §10) to match the values in
the committed `manifest.json` (§12).

## 3. Canonical JSON Encoding

Used wherever a hash is computed "over `canon_json(X)`". `canon_json(value)`
is defined recursively:

- `null` → the 4 bytes `null`
- boolean → `true` or `false`
- integer → its base-10 ASCII digits, no leading zeros, no decimal point.
  (Non-integer or non-finite numbers never appear in any value this
  specification hashes, and are not defined.)
- string → a JSON string literal: double-quoted, with `\`, `"`, and control
  characters (U+0000–U+001F) escaped per the JSON grammar. Characters above
  U+007F (non-ASCII) are emitted literally as their UTF-8 bytes — they are
  **not** escaped as `\uXXXX`.
- array → `[` + comma-joined `canon_json` of each element (no spaces) + `]`
- object → keys sorted by ordinary string comparison (UTF-16 code-unit
  order), then `{` + comma-joined `"key":value` pairs (no space after `:`
  or `,`) + `}`

The final byte sequence is `canon_json(value)` encoded as UTF-8.

## 4. Hash Algorithm Registry

- `hash_alg` = `"sha256"` (SHA-256, 256-bit / 32-byte digest).
- Every digest in this specification is SHA-256, rendered as lowercase
  hexadecimal (64 characters).
- This is fixed for all of NIC v1.1 and is not configurable per call. Hash
  algorithm identity travels with the `ProofV1` object itself (§9), never as
  out-of-band configuration — a proof plus a verifier must be sufficient
  for validation.

## 5. Glob Language

Grammar: exactly three operators — `*`, `?`, `**`. No other special syntax
(`[...]`, `{...}`, `!`) is permitted.

- `?` matches exactly one character that is not `/`.
- `*` matches zero or more characters, none of which is `/` — it does not
  cross a path-segment boundary.
- `**`, when it occupies an *entire* path segment (bounded by `/` or by the
  pattern's start/end on both sides), matches zero or more complete path
  segments, including across `/`:
  - If the whole pattern is exactly `**`, it matches any string (including
    the empty string).
  - If `**` is the first segment of a multi-segment pattern, it matches
    zero or more *leading* segments — `**/*.py` matches both `c.py` and
    `a/b/c.py`.
  - If `**` is the last segment, it matches zero or more *trailing*
    segments — `a/**` matches both `a` and `a/b/c`.
  - If `**` is a middle segment, it matches zero or more segments between
    its neighbors — `a/**/c` matches `a/c` and `a/x/y/c`.
  - A `*` that appears *within* a segment alongside other characters (e.g.
    `foo*bar`) is the ordinary single-segment operator; only a segment
    consisting of exactly `**` gets directory-crossing behavior.
- Matching is performed against the canonical path (§6) as a full-string
  (anchored) match, codepoint-for-codepoint, case-sensitive.
- A pattern containing any of `[` `]` `{` `}` `!` is rejected outright —
  fail-closed; it is never treated as a literal character or partially
  honored.

## 6. Canonical Path Pipeline

Input: a path, as raw bytes or text. Output: bytes (the canonical path), or
rejection. The step order below is frozen — every step is mandatory, none
may be skipped, and no recovery or best-effort cleanup is permitted on
failure:

1. **UTF-8 validate.** If the input is bytes, decode strictly as UTF-8 —
   any invalid byte sequence is rejected. If the input is already text,
   reject if it contains an unpaired UTF-16 surrogate (the in-memory
   equivalent of "not valid UTF-8").
2. **NFC normalize.** Apply Unicode Normalization Form C.
3. **Separator normalize.** Replace every backslash (`\`) with a forward
   slash (`/`).
4. **Reject absolute / drive-qualified input.** If the text (post step 3)
   starts with `/`, reject ("absolute path"). If the first `/`-delimited
   segment contains a `:`, reject ("drive-qualified path") — this catches
   Windows drive letters (`C:`) and similar constructs.
5. **Dot-segment collapse.** Split on `/`. Process segments left to right
   against a stack of kept segments:
   - An empty segment (from `//` or a trailing `/`) or a segment equal to
     `.` contributes nothing.
   - A segment equal to `..` pops the last kept segment. If the stack is
     empty when `..` is encountered, **reject** ("escapes repo root via
     '..'") — there is no clamping or silent ignoring.
   - Any other segment is pushed.
6. **Emit.** Join the remaining stack with `/` and encode as UTF-8 bytes.
   This is the canonical path. (No further repo-root check is needed: a
   path that survives step 5 cannot reference anything above where it
   started.)

## 7. ExternalResource URL Canonicalization

Input: a URL string in `scheme://[userinfo@]host[:port][/path][?query][#fragment]`
generic-URI form. Output: the canonical URL string.

- Split the URL into scheme, authority (userinfo/host/port), path, query,
  and fragment per the generic URI grammar: `scheme:`, then — if followed
  by `//` — an authority component running up to the next `/`, `?`, or `#`,
  then the path, then an optional `?query`, then an optional `#fragment`.
- **scheme**: lowercase it.
- **host**: lowercase it.
- **port**: if the URL specifies a port equal to the scheme's default port
  (`http` → 80, `https` → 443), drop it entirely. Any other explicit port
  is kept verbatim.
- **userinfo**: preserved verbatim (not case-folded) if present, in
  `user[:password]@` form.
- **path**: apply dot-segment normalization (§7.1). This is purely lexical
  and independent of §6's repo-relative rules — there is no "escapes root"
  rejection here; a leading `..` in a URL path is kept as a literal `..`
  segment, since URL paths have no repo root.
- **percent-encoding**: NEVER decoded and NEVER re-encoded. The only
  normalization applied to a percent-encoded octet (`%XX`) is uppercasing
  its two hex digits (e.g. `%2f` → `%2F`). `%2F` must never become a
  literal `/`, and a literal `/` must never become `%2F`. This rule applies
  identically to the path and to the query string.
- **fragment**: dropped entirely — the canonical form never includes a
  `#fragment`.
- **Reassembly**: omit the `?` entirely if the (post-normalization) query
  is empty. Omit the authority's `//` prefix only when there is no
  authority component to render.

### 7.1 Path dot-segment normalization (used by §7)

Split the path on `/`, noting whether it originally started with `/` (the
"leading slash" flag). Process segments left to right against a stack:

- A segment equal to `.` contributes nothing.
- A segment equal to `..`: if the stack is non-empty and its top is not
  itself `..`, pop the stack (cancelling the previous segment). Otherwise
  (stack empty, or top is `..`), push `..` literally — unlike §6, a leading
  or repeated `..` is preserved rather than rejected.
- Any other segment is pushed.

Join the remaining stack with `/`; if the leading-slash flag was set and
the result does not already start with `/`, prepend `/`.

## 8. Hash Domain

- **edge_id** for an edge `(from, type, to)` is
  `sha256(canon_json({"from": from, "to": to, "type": type}))`, hex-encoded.
  The object has exactly the three keys `from`, `to`, `type`; the hash
  operates on this value, never on the literal edge tuple or any other
  serialization.
- Every other hash in this section operates on edge_id strings only — never
  on serialized edges, never on arbitrary JSON blobs of edge content.
- **set_hash** of a collection of edge_ids: sort the edge_ids as plain
  strings (ordinary lexicographic order), then feed each one's ASCII bytes
  into a single SHA-256 hash, in sorted order, with **no separator**
  between them. Output is the hex digest.
- **witness_hash** of a sequence of edge_ids: identical to set_hash except
  the edge_ids are fed into the hash in exactly the order given by the
  caller — never sorted or otherwise reordered.
- **UNKNOWN edges and waivers**: an edge whose `type` is the literal string
  `UNKNOWN` represents a recognizer match that could not be resolved
  deterministically. A collection of edges contains no un-waived UNKNOWN
  edges if and only if, for every edge with type `UNKNOWN`, that edge's
  edge_id appears in the caller-supplied waived-edge-id set. (Edges that are
  not type `UNKNOWN` never require waiving.)

## 9. ProofV1 Schema

A `ProofV1` object is a JSON object with exactly these 7 keys, all
required, no others permitted:

| Field | Type | Constraint |
|---|---|---|
| `spec_version` | string | must equal the literal `"nic.proof.v1"` |
| `hash_alg_id` | string | must equal the literal `"sha256"` (§4) |
| `snapshot_mode` | string | one of: `"git_tree"`, `"manifest"` |
| `snapshot_id` | string | non-empty |
| `extractor_version` | string | non-empty |
| `result` | string | one of: `"PASS"`, `"FAIL"` (no third value at this layer — see §9.3) |
| `proof_payload` | object | any well-formed JSON object; not further constrained here |

### 9.1 Verifier semantics (fail-closed)

A candidate value is a valid `ProofV1` instance if and only if **all** of
the following hold:

- it is a JSON object (not an array, not a primitive)
- its key set is exactly the 7 keys above — no key missing, no extra or
  unknown key present
- every field satisfies the type/value constraint in the table above

Any violation — missing required field, unknown extra field, wrong type,
or a value outside a field's closed vocabulary — fails verification. There
is no partial credit and no "ignore unknown fields" leniency: allowing
unknown fields would let `proof + verifier + an undeclared assumption` pass
where `proof + verifier` alone should not.

### 9.2 Schema descriptor and `proof_schema_hash`

To let a manifest attest "corpus C was validated against proof schema S"
without embedding source code:

```
schema_descriptor = {
  "spec_version": "nic.proof.v1",
  "hash_alg_id": "sha256",
  "required_fields": <the 7 field names above, sorted as strings>,
  "snapshot_modes": <["git_tree", "manifest"], sorted>,
  "results": <["FAIL", "PASS"], sorted>
}
proof_schema_hash = sha256(canon_json(schema_descriptor)), hex-encoded
```

### 9.3 Relationship to NBC (out of scope)

A separate, out-of-scope layer (NBC) gates whether a proof is produced at
all: it evaluates a boundary check first and only proceeds to a
PASS/FAIL `ProofV1` if that boundary check passes; if the boundary check
fails, NBC emits a `DIAGNOSTIC` trace instead of a `ProofV1` object.
`DIAGNOSTIC` is therefore never a value of the `result` field — it is a
status at a layer above this schema. NBC's boundary-check semantics are not
defined by this document.

## 10. EdgeExtractor.v1 Registry and `registry_hash`

The recognizer registry is a single frozen JSON document of the shape:

```
{
  "version": "edge_extractor.v1",
  "recognizers": {
    "<RECOGNIZER_ID>": {
      "input_domain": "<string>",
      "match_rule": "<string>",
      "edge_type": "<string>"
    },
    ...
  }
}
```

`registry_hash` (equivalently, `extractor_version`) is:

```
registry_hash = sha256(canon_json(<the entire registry document, exactly as loaded>)), hex-encoded
```

`registry_hash` is therefore a pure function of the registry file's
content — there is no separately hand-maintained version string. Any
change to a recognizer's fields, or to the recognizer set itself, changes
`registry_hash` automatically. (What a `match_rule` actually does against
source text is recognizer/extractor logic and is out of scope here; only
the registry's hash is specified.)

## 11. Golden Corpus Format

`cases.json` has the shape:

```
{
  "version": "golden_corpus.v1",
  "description": "<string, informational only>",
  "cases": [ <case>, ... ]
}
```

Each `<case>` is an object with:

- `id` (string, unique across the corpus)
- `category` (one of `"canonical"`, `"boundary"`, `"adversarial"`,
  `"equivalence"`) — informational; does not affect evaluation
- `op` (string) — selects the operation to invoke (§11.1)
- `args` (object) — named arguments for that op
- exactly one of:
  - `expect` — the exact value the op must return (same type, same value;
    for hex/digest strings this means exact string equality)
  - `expect_error` — a substring the raised error's message must contain
    (the op must raise/throw; the specific error type is unconstrained,
    only that an error occurs and its message contains this substring)

### 11.1 Op → operation mapping

| op | args | behavior |
|---|---|---|
| `canonical_path` | `{"raw": <string>}` | §6; result is the canonical path bytes, hex-encoded |
| `glob_match` | `{"pattern": <string>, "path": <string>}` | §5; result is a boolean |
| `canonicalize_url` | `{"raw_url": <string>}` | §7; result is the canonical URL string |
| `compute_edge_id` | `{"from_": <string>, "type": <string>, "to": <string>}` | §8; result is the hex edge_id |
| `compute_set_hash` | `{"edge_ids": [<string>, ...]}` | §8 set_hash; result is the hex digest |
| `compute_witness_hash` | `{"edge_ids": [<string>, ...]}` | §8 witness_hash; result is the hex digest |
| `check_no_unknown_edges` | `{"edges": [{"from_": <string>, "type": <string>, "to": <string>}, ...], "waived_edge_ids": [<string>, ...]}` | §8 UNKNOWN check; result is a boolean |
| `verify_proof_schema` | `{"obj": <any JSON value>}` | §9.1; result is a boolean |

A conforming implementation must reproduce `expect`/`expect_error` exactly
for every case in the corpus.

## 12. Manifest Format

`manifest.json` is a flat JSON object with exactly these 4 keys:

```
{
  "proof_schema_hash": "<§9.2, hex>",
  "registry_hash": "<§10, hex>",
  "hash_alg": "sha256",
  "case_count": <integer, equal to the number of entries in cases.json's "cases" array>
}
```

A conforming implementation should independently recompute
`proof_schema_hash` (§9.2) and `registry_hash` (§10) from the same registry
document and confirm they match the committed manifest exactly — this is
the single strongest check that a second implementation's canonical-JSON
encoding (§3) agrees with the reference implementation's.
