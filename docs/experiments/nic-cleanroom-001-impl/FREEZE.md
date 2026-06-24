# FREEZE.md

I consider this implementation complete per my own reading of
`docs/nic-v1.1-spec.md`. This is the freeze point: no further features
will be added, and no test fixtures were requested or used.

## What was implemented

A Rust library crate (`nic_core`) implementing every operation named in
the spec's §11.1 table, plus the §9.2 and §10 hash computations:

- **`src/canon_json.rs`** — §3 Canonical JSON Encoding. Hand-rolled
  `Value` enum (null/bool/int/string/array/object, no float variant) and
  a recursive encoder implementing every formatting rule literally:
  no-leading-zero integers, JSON string escaping with literal (non-
  `\uXXXX`) UTF-8 for non-ASCII, no-space array/object separators, and
  object key sorting by **UTF-16 code-unit order** (not UTF-8 byte
  order — these differ for supplementary-plane codepoints; see
  QUESTIONS.md Q2).
- **`src/path.rs`** — §6 Canonical Path Pipeline. All six steps in
  order: UTF-8 validate, NFC normalize (via the `unicode-normalization`
  crate), backslash-to-slash, absolute/drive-qualified rejection,
  dot-segment collapse with fail-closed `..`-past-root rejection, and
  byte emission. Exposes both a raw-bytes entry point and a
  `canonical_path_hex` wrapper matching the §11.1 op signature.
- **`src/glob.rs`** — §5 Glob Language. `?`/`*`/`**` semantics
  implemented via per-segment matching: ordinary segments matched with
  a small `*`/`?` dynamic-programming matcher; a segment that is
  *exactly* `**` gets directory-crossing (zero-or-more-segments)
  treatment via recursive segment-count enumeration. Disallowed syntax
  (`[`, `]`, `{`, `}`, `!`) in the *pattern* is rejected fail-closed.
- **`src/url.rs`** — §7 ExternalResource URL Canonicalization. Hand-
  rolled generic-URI splitter (scheme/authority/path/query/fragment),
  scheme/host lowercasing, default-port dropping (http:80, https:443),
  verbatim userinfo, §7.1's dot-segment path normalization (a distinct,
  non-rejecting algorithm from §6's — see QUESTIONS.md Q7 for a
  significant divergence I found between the algorithm's literal
  behavior and its own prose paraphrase), and percent-encoding hex-digit
  uppercasing without decode/re-encode.
- **`src/hashdomain.rs`** — §8 Hash Domain. `compute_edge_id` (SHA-256
  over canon_json of the 3-key edge object), `compute_set_hash` (sorted,
  no-separator concatenation), `compute_witness_hash` (caller-order, no
  -separator concatenation), and `check_no_unknown_edges` (the
  UNKNOWN/waiver predicate).
- **`src/proof.rs`** — §9 ProofV1 Schema. `verify_proof_schema`
  implements all of §9.1's fail-closed rules by hand (exact key set,
  per-field type/closed-vocabulary checks) against a `serde_json::Value`
  candidate. `proof_schema_hash` builds the exact §9.2 descriptor
  (with all three field-name/mode/result lists independently sorted)
  and hashes its canon_json encoding.
- **`src/registry.rs`** — §10 registry and `registry_hash`. Loads an
  arbitrary registry document as a generic `serde_json::Value` (parser
  only, never used as the canonicalizer) and transcribes it losslessly
  into our own `canon_json::Value` model before hashing, preserving
  "exactly as loaded" fidelity. Non-integer/non-finite numbers (for
  which §3 declines to define an encoding) cause an explicit error
  rather than a silent, spec-undefined fallback.
- **`src/manifest.rs`** — §12 manifest format. A small `Manifest`
  struct/builder/comparator for the "independently recompute and
  compare to the committed manifest" cross-check §12 describes. Not
  itself a new computation — composes `proof_schema_hash` and
  `registry_hash`.

All eight §11.1 op names have a corresponding function:
`canonical_path`/`canonical_path_hex`, `glob_match`, `canonicalize_url`,
`compute_edge_id`, `compute_set_hash`, `compute_witness_hash`,
`check_no_unknown_edges`, `verify_proof_schema` — plus `proof_schema_hash`
(§9.2) and `registry_hash` (§10).

**Dependencies** (all generic, publicly-known infrastructure, never a
"the spec" implementation): `sha2` (SHA-256 primitive only — the
hash-domain logic of §8 is hand-rolled around it), `unicode-normalization`
(NFC primitive only — used in exactly one place, §6 step 2), and
`serde_json` (used strictly as a generic JSON *parser*/value
representation for arbitrary input in `verify_proof_schema` and
`registry_hash_from_str`; `serde_json`'s own *serializer* is never
called — all canonical-JSON byte production goes through my own
hand-rolled `canon_json` encoder).

**Tests:** 116 unit tests across all 7 modules, all passing. Many tests
cross-check the implementation against an independently hand-built
expected string (e.g. `proof_schema_hash`, `registry_hash`, and
`edge_id`/`set_hash`/`witness_hash` tests each construct the expected
canonical-JSON or concatenation string by hand and feed it through a
separate `Sha256::digest` call, rather than just calling the function
twice) — this is the closest I could get to an independent fixture
given that none were provided. `cargo clippy --all-targets` and `cargo
fmt --check` are both clean.

## Residual uncertainty

Ten ambiguities were identified and logged in `QUESTIONS.md` with
chosen assumptions and reasoning (see that file for full detail). The
two I consider most likely to cause a genuine divergence from a
different conforming implementation, if such an implementation made a
different but equally defensible choice, are:

1. **Q7** — §7.1's URL path dot-segment algorithm, taken completely
   literally (no empty-segment special case, unlike §6), causes a
   single leading `..` in a URL path with a leading `/` to be silently
   absorbed (`/../a` → `/a`) rather than preserved as `/../a`. This
   contradicts what §7.1's own prose ("a leading or repeated `..` is
   preserved") seems to promise at first read, and a different
   implementer might "fix" this by adding an empty-segment-is-dropped
   rule by analogy with §6 — producing a different `canonicalize_url`
   result for any URL path that is both rooted and starts with `..`.
   I chose the literal-algorithm reading over the prose-paraphrase
   reading; I believe this is right, but flag it as the single highest
   -risk divergence point in the whole implementation.
2. **Q2** — object-key sort order in canon_json uses UTF-16 code-unit
   order (not UTF-8 byte order), which only matters for keys containing
   supplementary-plane Unicode codepoints (U+10000+). Extremely unlikely
   to be exercised by any realistic registry/proof document, but if a
   golden corpus does test it, this is the rule that determines the
   answer.

All other entries (Q1, Q3-Q6, Q8-Q10) are lower-stakes type-system
translation issues, malformed-input handling choices, or out-of-band
edge cases (negative integers, Rust's inability to construct unpaired
surrogates, multiple `@` in a URL authority, IPv6 host brackets,
malformed ports/percent-encoding, non-integer numbers in a registry
document) where I'm fairly confident the chosen behavior is reasonable
even if a different choice was technically also defensible.

I am not aware of any place where I knowingly implemented something
that contradicts the spec's literal text — every deliberate choice is
logged in QUESTIONS.md. I have not seen any test fixtures, golden
corpus, or reference implementation for this spec, and have not
searched for one.
