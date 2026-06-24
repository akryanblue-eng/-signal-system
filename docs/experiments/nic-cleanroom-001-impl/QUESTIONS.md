# QUESTIONS.md — Ambiguity Log

This file records every point where the NIC v1.1 spec
(`docs/nic-v1.1-spec.md`) was ambiguous, underspecified, or required a
judgment call during clean-room implementation. Each entry records the
question, the exact spec text that fails to resolve it, the assumption
made, and the reasoning. Entries are numbered in the order encountered.

---

## Q1. Does "integer" in canon_json (§3) include negative numbers, and if so, how is the sign formatted?

**Spec text (§3):** "integer → its base-10 ASCII digits, no leading
zeros, no decimal point. (Non-integer or non-finite numbers never appear
in any value this specification hashes, and are not defined.)"

**Ambiguity:** The spec says "no leading zeros" but never explicitly
states whether negative integers are in-domain at all, nor (if they are)
whether the minus sign counts as a "leading" character that the
no-leading-zeros rule would apply to (e.g. is `-0` a "leading zero"
violation? is `-007` rejected only for the zeros after the sign, or does
the sign itself count?). Scanning every place §3 is invoked
(`registry_hash`, `proof_schema_hash`, `edge_id`, `case_count` in
§12-style manifests, etc.), the only integer that actually appears
anywhere in the spec's worked examples is `case_count` (§12), which is
described as a non-negative count ("equal to the number of entries").
No negative integer use case is ever named.

**Assumption chosen:** Implement standard two's-complement signed
integer formatting: a leading `-` for negative values, followed by
base-10 digits with no leading zeros (i.e. `-7`, not `-07`); `0` itself
prints as the single digit `0` (not `-0`, not empty). This matches Rust's
native `i64::to_string()` behavior, which I rely on directly rather than
hand-rolling digit formatting, since it already satisfies "no leading
zeros, no decimal point" for every value including zero and negatives.

**Reasoning:** Since no negative integer ever actually appears in any
op this spec defines (all hashed integers are counts or absent), this
choice is very unlikely to be exercised in practice. But the `Value::Int`
variant in my JSON value model is typed as `i64` for generality, so it
needed *some* defined behavior for negative inputs to avoid the type
being a trap with undefined formatting. Standard signed-decimal
formatting is the least surprising choice and is what virtually every
"canonical JSON" convention in the wild does. I did not add a separate
"reject negative integers" rule because the spec never says negative
integers are disallowed — it only says non-integers/non-finite numbers
are out of scope, which is a different restriction.

---

## Q2. Is "ordinary string comparison (UTF-16 code-unit order)" actually different from UTF-8 byte order, and if so, which one governs object key sorting (§3)?

**Spec text (§3):** "object → keys sorted by ordinary string comparison
(UTF-16 code-unit order)..."

**Ambiguity:** For the vast majority of strings (anything in the BMP,
i.e. codepoints below U+10000, including all of ASCII and Latin-1 and
most "ordinary" identifiers), UTF-16 code-unit order, UTF-8 byte order,
and raw Unicode scalar-value order all agree. They diverge only for
supplementary-plane codepoints (U+10000 and above), which UTF-16 encodes
as a surrogate pair (high surrogate in 0xD800-0xDBFF, low surrogate in
0xDC00-0xDFFF). Because 0xD800 < 0xE000, a supplementary-plane codepoint
like U+10000 sorts *before* a BMP codepoint like U+E000 under UTF-16
code-unit order, even though U+10000 is numerically the larger Unicode
scalar value (and would sort *after* U+E000 under naive UTF-8 byte or
codepoint order). The spec explicitly calls out "UTF-16 code-unit order"
by name, which reads as a deliberate, specific choice (most likely
mirroring how JavaScript's default `<`/`Array.sort()` string comparison
works, since UTF-16 is JS's native string encoding) rather than a casual
synonym for "byte order."

**Assumption chosen:** Implemented key comparison by encoding each key
to a `Vec<u16>` (via Rust's `str::encode_utf16()`) and comparing those
sequences lexicographically, rather than comparing the raw UTF-8 bytes
or `char` (codepoint) sequences directly. See
`canon_json::encode`'s object-key sort and the
`utf16_key_ordering_surrogate_vs_bmp` unit test, which specifically
constructs a key pair that would sort in opposite relative order under
UTF-16-code-unit-order vs. naive-codepoint-order, to pin down which rule
is implemented.

**Reasoning:** The spec names "UTF-16 code-unit order" explicitly and
parenthetically, which is strong signal it means literally that (as
opposed to just "the usual way to compare strings"), especially since it
goes out of its way to disambiguate from "ordinary string comparison" —
implying ordinary string comparison alone was considered ambiguous
enough to need the parenthetical. I chose the literal reading over the
"probably they just mean byte order" reading.

---

## Q3. What does "text" input and its "unpaired UTF-16 surrogate" check (§6 step 1) mean in a language, like Rust, whose native string type cannot contain unpaired surrogates?

**Spec text (§6, step 1):** "UTF-8 validate. If the input is bytes,
decode strictly as UTF-8 — any invalid byte sequence is rejected. If the
input is already text, reject if it contains an unpaired UTF-16
surrogate (the in-memory equivalent of 'not valid UTF-8')."

**Ambiguity:** This rule is clearly written with languages like
JavaScript, Java, or Python (in some internal representations) in mind,
where "text" (a native string type) is stored as UTF-16 or can otherwise
encode lone surrogates (e.g. via `String.fromCharCode(0xD800)` in JS) —
i.e. "text" there is a weaker guarantee than "valid Unicode." Rust's
`String`/`str` types are different: the language guarantees at the type
level that any `&str`/`String` is well-formed UTF-8 (and therefore can
never contain an unpaired surrogate; constructing one requires `unsafe`
and is undefined behavior if done incorrectly). So the "text" input path
of step 1 can never actually observe a violation in idiomatic Rust — the
check is unconditionally vacuous.

**Assumption chosen:** I modeled the two input kinds as
`RawPath::Bytes(&[u8])` (which goes through `std::str::from_utf8`,
genuinely exercising the "decode strictly as UTF-8, reject invalid byte
sequences" rule) and `RawPath::Text(&str)` (which performs no additional
check, since none is possible/meaningful on a `&str`). The corpus op
table (§11.1) defines `canonical_path`'s args as `{"raw": <string>}` —
already a JSON *string*, i.e. "text" in the spec's own vocabulary — so
the op-level entry point (`canonical_path_hex`) always uses the `Text`
variant. The `Bytes` variant and its UTF-8-validation error path exist in
the API for completeness/fidelity to step 1's bytes case, and are
unit-tested directly, but are not reachable through the `cases.json`
op-table surface since JSON has no raw-bytes type.

**Reasoning:** This is a case where the spec's rule is sound in its
original target environment but partially inapplicable to Rust's type
system. Rather than fabricate a way to smuggle an invalid surrogate into
a Rust `&str` (which would require `unsafe` and arguably violate Rust's
own soundness contract just to exercise a spec clause), I treated the
guarantee Rust's type system already provides as satisfying the spec's
intent ("reject if it contains an unpaired UTF-16 surrogate" — true
vacuously, there are zero such strings representable). I judged this
safer than, say, silently skipping the bytes-input code path entirely;
keeping `RawPath::Bytes` ensures the "decode strictly as UTF-8" half of
step 1 is still genuinely implemented and tested for the case where raw
bytes are the input.

---

## Q4. Order of step 4's two checks (absolute-path vs. drive-qualified) when both could apply, and exact scope of "first /-delimited segment"

**Spec text (§6, step 4):** "If the text (post step 3) starts with `/`,
reject ('absolute path'). If the first `/`-delimited segment contains a
`:`, reject ('drive-qualified path')."

**Ambiguity:** Minor wording question: for an input like `/C:/x` (both
absolute *and* drive-qualified-looking), which rejection reason fires?
Also: is "the first /-delimited segment" computed on the full string
(potentially including a leading empty segment before the first `/` if
the string starts with `/`), or only relevant once we know the string is
not absolute?

**Assumption chosen:** Implemented as two sequential, independent
checks in the order written: first check "starts with `/`" (rejecting
with "absolute path" if true, short-circuiting before the drive check
ever runs); only if that check passes do we compute the first segment
(text before the first `/`, or the whole string if there's no `/`) and
check it for `:`. Since the absolute-path check already consumed and
rejected anything starting with `/`, by the time the drive check runs
the first segment can never itself be empty due to a leading slash.

**Reasoning:** The spec lists the two checks as separate sentences in a
fixed order within step 4, which I read as prescribing sequential
evaluation in that order — consistent with the rest of §6's framing
("The step order below is frozen"). An input that is both absolute and
drive-qualified-looking (e.g. `/C:/x`) will therefore always be rejected
as "absolute path" (the first check fires and the function returns
before the second check is reached), never as "drive-qualified path".
This seemed like the most natural reading of two sequentially-stated
sentences and avoids needing to invent a tie-breaking rule the spec
never states.

---

## Q5. Does the "disallowed syntax" fail-closed rejection (§5) ever apply to the path argument, or only to the pattern?

**Spec text (§5):** "A pattern containing any of `[` `]` `{` `}` `!` is
rejected outright — fail-closed; it is never treated as a literal
character or partially honored."

**Ambiguity:** The rejection rule is stated only in terms of "a
pattern". The `glob_match` op (§11.1) takes both a `pattern` and a
`path` argument. Nothing in §5 says the path itself is restricted in
character set, and a literal path could legitimately contain a `!`,
`[`, etc. as an ordinary filename character (these are all valid in
e.g. POSIX/most filesystem paths) — there's no normalization step in §6
that would strip or reject such characters from a canonical path. So
should `glob_match` validate/reject based on characters appearing in
`path` too, or strictly only `pattern`?

**Assumption chosen:** Only the `pattern` argument is checked against
the disallowed-character set; `path` is matched literally,
codepoint-for-codepoint, with no syntax restrictions of its own (any
Unicode scalar value is allowed in `path`, including `[`, `]`, `{`,
`}`, `!`, since those are not glob metacharacters when they appear in
the *path* being matched against — they're just literal characters
there).

**Reasoning:** §5's rejection rule explicitly and only says "a pattern
containing...", and the whole point of glob syntax restrictions is to
constrain what the *pattern* (which is parsed for operators) is allowed
to contain — not the path, which is just literal data being matched,
never parsed for operators. There is no operator-vs-literal ambiguity on
the `path` side because the path is never interpreted as a pattern.

---

## Q6. Does a literal "**" appearing inside a `path` (not the pattern) get special treatment?

**Spec text (§5):** All of §5's `**` rules are phrased in terms of the
*pattern* ("if `**` is the first segment of a multi-segment **pattern**
...", etc.) — there is no provision anywhere for the *path* argument
containing `**` as a literal segment name.

**Ambiguity:** A path segment that is literally the two characters `**`
(e.g. a real, if unusual, file actually named `**` checked into a
repo) is permitted by §6 path canonicalization (nothing in §6 disallows
`*` characters in a segment) — so it is a representable path. If the
pattern being matched against it is, say, the literal pattern `\*\*`...
but wait, glob patterns have no escape mechanism defined anywhere in §5
either. So is there any way to match a path segment that is literally
`**` against a pattern, given that any pattern segment of exactly `**`
is *always* interpreted as the directory-crossing wildcard, never as a
literal two-asterisk segment name?

**Assumption chosen:** A path segment whose literal name is `**` can
never be matched by a literal (non-wildcard) pattern segment of `**`,
because per §5 a pattern segment that is exactly `**` is unconditionally
the directory-crossing wildcard — there is no way to write a pattern
that means "match the literal two-character segment `**`." It can,
however, still be matched incidentally by the directory-crossing
wildcard itself (since `**` viewed as a wildcard matches zero or more
*arbitrary* segments, including a segment that happens to be spelled
`**`), or by an ordinary pattern segment using `?`/`*` wildcards that
happens to produce the string `**` (e.g. pattern `*` matches path
segment `**` as an ordinary single non-`**`-whole-segment match, since
the *pattern* segment `*` is not itself exactly `**`). I implemented
this literally: `path` is never special-cased for `**` at all; only
`pattern` segments equal to the literal string `"**"` get
directory-crossing treatment (see `match_segments`'s
`Some(&"**") => ...` arm, which inspects only `pat_segs`, never
`path_segs`).

**Reasoning:** This is a direct, faithful reading of the spec, which
defines `**`'s special meaning purely as a property of pattern syntax.
I flag it here because it produces a slightly surprising edge case
(some real paths are unmatchable by exact-literal patterns) but the
spec gives no escape syntax to work around it, and inventing one would
be adding behavior the spec doesn't define.

---

## Q7. Does §7.1's dot-segment algorithm special-case the empty segment produced by a leading `/`, the way §6 step 5 does? (It does not — and this has a surprising consequence for leading `..`.)

**Spec text (§7.1):** "Split the path on `/`, noting whether it
originally started with `/` (the 'leading slash' flag). Process segments
left to right against a stack: A segment equal to `.` contributes
nothing. A segment equal to `..`: if the stack is non-empty and its top
is not itself `..`, pop the stack... Otherwise..., push `..` literally...
Any other segment is pushed."

**Ambiguity / non-obvious consequence:** Unlike §6 step 5, which
explicitly states "An empty segment (from `//` or a trailing `/`) ...
contributes nothing," §7.1 has no such clause — its three bullets cover
only `.`, `..`, and "any other segment," and an empty string `""` (which
is exactly what `path.split('/')` yields for the first element whenever
the path starts with `/`) is not `.` or `..`, so per the literal "any
other segment is pushed" rule it gets pushed onto the stack like a
normal segment. The spec instead handles leading slashes via a separate
"leading slash flag" that's reattached at the very end, suggesting the
empty first segment is *meant* to be transient/structural rather than a
real pushed segment — but the algorithm as literally written does push
it, and a subsequent `..` will then pop it (since the empty string is
not itself `..`). The result: for a path like `/../a`, the leading `..`
gets silently absorbed by canceling against the synthetic empty segment,
producing `/a` — NOT `/../a` as a naive reading of "a leading ... `..`
is preserved" (§7.1's own prose, paraphrasing the rule's *purpose*)
might suggest. This is a real, easy-to-get-wrong divergence between what
the rule's prose seems to promise and what its literal step-by-step
algorithm produces.

**Assumption chosen:** Implemented the algorithm exactly as literally
written — split on `/`, push the empty string like any other segment
when present, let `..` interact with it via the ordinary pop-or-push
rule, and only reattach the leading slash at the join step. I verified
this by hand-tracing multiple cases (`/../a` -> `/a`; `/../../a` ->
`/../a`; `/a/../../b` -> `/b`) against the stack algorithm step by step
before fixing my unit tests, which originally encoded the *wrong*
(prose-intuition) expectation and failed against my own implementation
— a useful signal that the literal-algorithm reading and the
prose-paraphrase reading genuinely diverge here.

**Reasoning:** The spec's own framing principle, stated repeatedly
throughout (§6: "no recovery or best-effort cleanup," step order
"frozen"; §3's exhaustive case-by-case definition), favors mechanical,
literal execution of the stated algorithm over interpretive
"common-sense" patching — especially because §7.1 evidently *was*
written with care to differ from §6 on purpose (it explicitly flags
"unlike §6, a leading or repeated `..` is preserved rather than
rejected" as the point of departure). Rather than silently special-case
the empty segment to make the outcome match my own intuitive
expectation of "leading `..` preserved literally" (which would be
importing behavior the algorithm doesn't state), I implemented exactly
what's written and let the leading-slash absorption fall out as a
consequence. I flag this because a second implementer who patches in an
"empty segment contributes nothing" rule by analogy with §6 (a very
natural mistake) would silently produce different output than this
implementation for any path with both a leading `/` and a leading `..`.

---

## Q8. Authority parsing details not addressed by §7's prose: multiple `@` in authority, IPv6 bracketed hosts, non-numeric/malformed ports, missing scheme, malformed percent-encoding (`%` not followed by 2 hex digits)

**Spec text (§7):** "Split the URL into scheme, authority
(userinfo/host/port), path, query, and fragment per the generic URI
grammar... **userinfo**: preserved verbatim (not case-folded) if
present, in `user[:password]@` form." No further detail is given on how
to locate the userinfo/host/port boundary characters when the input is
ambiguous or malformed.

**Ambiguities and assumptions, bundled together since they're all "parse
the authority/handle malformed input" judgment calls:**

1. **Multiple `@` in authority** (e.g. a password containing a literal
   `@`, which the generic URI grammar would normally require to be
   percent-encoded, but the input might not have done so). *Assumption:*
   split on the **last** `@` in the authority (`rfind`), treating
   everything before it as userinfo and after it as host[:port]. This
   matches common URL-parser convention (host/port can't contain `@`,
   but a not-strictly-conformant userinfo password might).
2. **IPv6 bracketed host** (`[::1]:8080`). The spec's grammar sketch
   (`scheme://[userinfo@]host[:port]...`) doesn't call out IPv6 brackets
   at all. *Assumption:* detect a `[...]` bracketed token and treat it
   as an opaque host (not lowercased internally beyond the whole-token
   `.to_lowercase()` call, which is a no-op for hex digits and colons
   anyway), with the port parsed from whatever follows the closing `]:`.
   I chose to still lowercase the bracketed host text for consistency
   with "host: lowercase it," even though IPv6 literals are case
   sensitive only in their (already-lowercase-rendered-by-convention)
   hex digits — lowercasing is harmless and consistent with the literal
   instruction.
3. **Non-numeric or otherwise malformed port** (e.g.
   `http://example.com:abc/`). *Assumption:* if the port text fails to
   parse as an unsigned integer, treat it as "not equal to the default
   port" and keep it verbatim, rather than erroring. The spec doesn't
   define a rejection rule for malformed ports, and §7 is about
   canonicalization, not validation, so fail-open (keep it) rather than
   fail-closed (reject) seemed more consistent with §7's overall
   "preserve what we don't have a specific rule for" character (e.g.
   userinfo preserved verbatim, non-default ports preserved verbatim).
4. **Missing scheme / no `:` at all** (e.g. just `example.com/a`).
   *Assumption:* this is a genuine parse error — `canonicalize_url`
   returns `Err(UrlError(...))`. The spec's grammar requires
   `scheme:` unconditionally, so there's no canonical form for input
   that doesn't even have a scheme.
5. **Malformed percent-encoding** (`%` followed by zero, one, or two
   non-hex-digit characters, e.g. a bare trailing `%` or `%2` or `%zz`).
   *Assumption:* pass such a `%` through completely unchanged (don't
   uppercase anything, don't error) — only a `%` that is followed by
   exactly two valid hex digits is recognized as a percent-encoded octet
   and has its hex digits uppercased. The spec says percent-encoding is
   "NEVER decoded and NEVER re-encoded" and only describes
   normalization for the `%XX` case; it gives no rejection rule for
   malformed percent sequences, so I chose the most conservative
   "leave it exactly as-is" behavior over either erroring or guessing at
   a repair.

**Reasoning (common to all five):** None of these are addressed by the
spec's prose, which focuses entirely on the well-formed case. In each
case I chose the most conservative behavior consistent with §7's
stated philosophy ("preserve verbatim" / "never decoded or re-encoded"
/ canonicalization rather than validation), and avoided inventing a new
rejection rule the spec doesn't state, except for the one case (missing
scheme/colon) where the grammar is unconditional and a parse failure is
unavoidable.

---

## Q9. `proof_payload`'s "any well-formed JSON object; not further constrained" (§9 table) — does this require recursively validating its contents (e.g. rejecting NaN/Infinity numbers, non-string keys, duplicate keys) at the `verify_proof_schema` layer?

**Spec text (§9 table):** "`proof_payload` | object | any well-formed
JSON object; not further constrained here". §9.1 additionally requires
the *candidate* overall to be "a JSON object (not an array, not a
primitive)" but doesn't add anything proof_payload-specific beyond the
table's "any well-formed JSON object."

**Ambiguity:** "Well-formed JSON object" could be read as (a) merely
"its declared type is `object`, full stop — its contents are explicitly
out of scope ('not further constrained')," or (b) "object, AND every
value transitively inside it must itself be well-formed JSON" (e.g. no
NaN/Infinity float values if the candidate came from a JSON parser that
permits such extensions, no duplicate keys, etc.).

**Assumption chosen:** Interpretation (a). I check only that
`proof_payload`'s JSON type is `object` (`serde_json::Value::is_object()`)
and impose no further recursive validation on its contents. Since the
candidate is always supplied as an already-parsed `serde_json::Value`
(see §11.1's `{"obj": <any JSON value>}` argument, which is JSON data,
not a raw string requiring a second parse pass with a possibly-lenient
parser), and `serde_json`'s own parser already guarantees the result is
well-formed JSON (it has no NaN/Infinity literals in standard JSON, and
its object representation cannot have duplicate keys survive parsing —
last-key-wins is `serde_json`'s documented behavior for input with
duplicates), there is no way for a `serde_json::Value` of kind `Object`
to be anything other than "well-formed" by construction in the relevant
senses. So "not further constrained" is read literally: the schema
layer's job stops at checking the type is `object`.

**Reasoning:** The spec's own words ("not further constrained here")
read as an explicit instruction not to add validation beyond
type-checking — this is the strongest and most direct textual signal
of intent in the whole §9 table, and over-validating would contradict
it. Practically, since the op-table's `obj` argument is always JSON data
rather than a raw byte/string blob that itself needs re-validating for
"well-formedness," the question is largely moot for any caller using
this implementation's actual entry point (`verify_proof_schema(&JsonValue)`),
but the type-only check is documented here as the deliberate, minimal
reading.

---

## Q10. What should happen if a loaded registry document (§10) contains a non-integer or non-finite number, given that §3 says such numbers' canon_json encoding "is not defined"?

**Spec text (§3):** "(Non-integer or non-finite numbers never appear in
any value this specification hashes, and are not defined.)" §10 says
`registry_hash` hashes "the entire registry document, exactly as
loaded" — implying whatever is actually in the file, not a
schema-filtered subset, even though §10's own shape sketch only shows
string-valued fields.

**Ambiguity:** The spec asserts non-integer/non-finite numbers "never
appear" in any hashed value — presented as a fact about well-formed
inputs, not a rule to enforce. It doesn't say what an implementation
should do if it's handed a registry document that violates this
assumption (e.g. a hand-edited registry file with a stray `1.5` or a
`NaN`-shaped value some non-conforming JSON producer emitted). Since
§3 explicitly declines to define the encoding, an implementation can't
"do the right thing" — there is no right thing defined.

**Assumption chosen:** `json_to_canon` (the bridge from a generically-
parsed `serde_json::Value` to our `canon_json::Value` model) returns an
explicit `Err(RegistryError(...))` for any JSON number that is not
representable as an `i64` via `serde_json::Number::as_i64()` — this
covers genuine floats (e.g. `1.5`), integers too large for `i64`, and
(per `serde_json`'s own parsing rules) JSON numbers written with a
decimal point or exponent even when integer-valued (e.g. `1.0`, which
`serde_json` represents internally in a way that `as_i64()` does NOT
accept — confirmed directly via the
`decimal_point_literal_rejected_even_when_integer_valued` test in
`src/registry.rs`). I.e., fail loudly rather than attempt a lossy
"round to nearest integer" or silently-undefined-behavior encoding.

**Reasoning:** Given §3 explicitly states this case "is not defined," a
conforming implementation has no normative encoding to fall back on; an
implementation that picked one anyway (round, truncate, stringify with
a decimal point despite the no-decimal-point rule, etc.) would be
inventing behavior, not following the spec, and worse, doing so
*silently* would produce a `registry_hash` value that has no normative
meaning at all and that a second conforming implementation might
silently disagree with (since each would have invented a different
fallback). Failing loudly is the only option that doesn't manufacture
an undefined value and pass it off as if it meant something.

---

(No further entries — see FREEZE.md for additional residual-uncertainty
notes that did not rise to the level of a logged ambiguity here because
a reasonably confident reading of the spec text was available.)
