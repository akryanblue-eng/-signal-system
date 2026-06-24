# Experiment NIC-CLEANROOM-001: Specification Sufficiency Test

## Purpose

Test whether `docs/nic-v1.1-spec.md` is sufficient, on its own, for an
independent implementer to reconstruct NIC v1.1's deterministic core —
without access to any reference implementation, the golden corpus, or the
manifest — such that the resulting implementation reproduces the corpus
after the fact.

This is Level C in the evidentiary framework established for this work:

| Level | Question | Status |
|---|---|---|
| A — internal consistency | Does one implementation's own test suite pass? | Proven |
| B — cross-runtime reproducibility | Do two independent-language implementations converge given the same fixtures? | Proven (Python `src/`, TypeScript `conformance/typescript/`) |
| C — specification sufficiency | Does an implementation built from prose alone, with no fixtures and no reference code, converge on the same fixtures it never saw? | Under test (this experiment) |

## Metadata

- **Experiment ID:** NIC-CLEANROOM-001
- **Date started:** 2026-06-24
- **Spec version under test:** `docs/nic-v1.1-spec.md` as committed at `d9ddd51` on
  `claude/normalizer-v1-authority-0ieer4` (content-identical copy committed
  standalone at `04430db` in the isolated clean-room repo, see below)
- **Implementation language:** Rust (chosen by the orchestrating agent;
  not specified by the user)
- **Agent/model:** clean-room implementer is a fresh `general-purpose` subagent
  launched via the `Agent` tool; inherits the session model
  (`claude-sonnet-4-6`) unless noted otherwise at launch time
- **Isolation mechanism:** standalone git repository at `/home/user/nic-cleanroom`,
  created via `git init` (not `git worktree`) — deliberately not sharing the
  main repo's object database, so that `git log`/`git show` inside it cannot
  recover any history beyond its own single commit. (An earlier attempt used
  `git worktree`, which still shares `.git` objects with the main repo and
  would have let the agent retrieve deleted source files via `git show
  <main-repo-commit>:src/nic_v1.py`. That attempt was abandoned before any
  agent made use of it — see Question Log, Q0.)

### Available artifacts (Phase 1 — implementation)

- `docs/nic-v1.1-spec.md` (verbatim, the sole NIC-specific artifact)
- Standard Rust toolchain (`rustc`, `cargo`) and ordinary OS/build tooling
- Public, generic crates needed purely as build scaffolding (e.g. a SHA-256
  implementation, a JSON value type) if the agent chooses to use them —
  permitted because these encode no information about *this* specification,
  the same way stdlib `hashlib`/`crypto` would not
- Whatever standard knowledge of Rust, JSON, URIs, Unicode, and SHA-256 as a
  *public, generic algorithm* the model already has from training — this is
  unavoidable background knowledge, not project-specific leakage

### Unavailable artifacts (withheld until freeze)

- `src/` (Python reference implementation) — entire directory
- `conformance/` (TypeScript port) — entire directory
- `src/golden_corpus/cases.json`
- `src/golden_corpus/manifest.json`
- `src/edge_extractor_v1.json`
- Any reference implementation, in any language
- Commit history, commit messages, or diffs from the main repo
- Implementation notes, design discussion, or this experiment file itself

### Completion timestamp

`2026-06-24T01:24:27+00:00` — commit `86e3cfb` in the clean-room repo
(`Implement NIC v1.1 deterministic core as a Rust library crate`), the
commit at which `FREEZE.md` was written and the implementer declared the
work complete. The corpus was not copied into the clean-room environment
until after this commit.

## Success criteria (declared before corpus reveal)

- **Pass:** Implementation completed from `docs/nic-v1.1-spec.md` alone; no
  access to `src/` or `conformance/`; corpus revealed only after
  implementation freeze; corpus results match expected outputs.
- **Partial pass:** Minor discrepancies that can be traced to ambiguous
  spec language (i.e. the spec under-specified something, the implementer
  made a documented, reasonable interpretation, and the corpus picked the
  other reading).
- **Fail:** Multiple independent interpretation gaps, or the corpus reveals
  behavior that was not derivable from the spec at all (an outright spec
  omission, not just an ambiguity).

The interesting outcome is not necessarily 100% corpus success — a
Partial pass that cleanly localizes to one or two ambiguous clauses is
itself useful evidence about which parts of the spec need tightening.

## Question log

Every point at which the clean-room implementer would normally need
outside clarification is recorded here, with the implementer's own
documented resolution (no live clarification is provided during the
implementation phase — that is the point of the experiment). Each entry
answered entirely by re-reading the spec is evidence of completeness;
each entry that cannot be resolved from the spec text is a candidate
spec ambiguity.

| # | Raised by | Question | Resolved by spec? | Resolution / assumption made |
|---|---|---|---|---|
| Q0 | orchestrator setup, surfaced by agent `a5e680bee74095869` | "Where is the spec file? `find -iname '*nic*'` found nothing." | N/A — process error | Not a spec ambiguity: the orchestrator branched the clean-room worktree before committing `docs/nic-v1.1-spec.md` on the main branch, so the file genuinely did not exist in that worktree yet. The agent correctly detected the absence, declined to fabricate an implementation from memory or from the task prompt's prose, and made no commits. Fix: spec committed to main (`d9ddd51`), and the clean-room environment was rebuilt from scratch as an isolated standalone repo (see Isolation mechanism above) rather than resumed, both to supply the file and to close the shared-history leak discovered during the fix. |
| Q1 | implementer (agent `acbf187cd2e2dd06d`) | §3 says integers have "no leading zeros" but never says whether negatives are in-domain or how the sign interacts with that rule. | No | Implemented standard signed-decimal formatting (`-7`, not `-07`; `0` not `-0`), via Rust's native `i64::to_string()`. Reasoned: no negative integer ever actually appears in any op this spec defines, so this is unlikely to be exercised, but the JSON value model needed *some* defined behavior to avoid a formatting trap. |
| Q2 | implementer | §3 says object keys sort by "ordinary string comparison (UTF-16 code-unit order)" — is that literally UTF-16 code-unit order (which diverges from UTF-8 byte/codepoint order for supplementary-plane codepoints, U+10000+), or just a casual synonym for "the usual way"? | Yes (the parenthetical resolves it) | Implemented literal UTF-16 code-unit-order comparison (`str::encode_utf16()` then lexicographic `Vec<u16>` comparison), not UTF-8 byte order. Flagged in `FREEZE.md` as one of the two highest-risk divergence points, since the spec's explicit naming is the only thing settling it. |
| Q3 | implementer | §6 step 1's "if the input is already text, reject if it contains an unpaired UTF-16 surrogate" rule targets languages where "text" can hold ill-formed code units (JS, Java); Rust's `String`/`str` type cannot represent an unpaired surrogate at all — what does this rule even mean here? | Partially — the rule is sound, just vacuous in Rust | Modeled two input variants, `RawPath::Bytes`/`RawPath::Text`; the bytes path genuinely exercises "decode strictly as UTF-8, reject invalid sequences," the text path treats Rust's type-level guarantee as satisfying the surrogate check vacuously (true for all representable `&str` values), rather than fabricating an `unsafe` ill-formed string just to exercise the clause. |
| Q4 | implementer | §6 step 4 lists "reject absolute" then "reject drive-qualified" as separate sentences — for an input that's both (e.g. `/C:/x`), which fires, and is checking order significant? | Yes (sequential sentence order read as evaluation order) | Implemented as two sequential checks in the order written; the absolute-path check short-circuits, so `/C:/x` is always rejected as "absolute path," never reaches the drive check. |
| Q5 | implementer | §5's disallowed-syntax rejection (`[`,`]`,`{`,`}`,`!`) is stated only for "a pattern" — does it also restrict the `path` argument being matched against, even though those are all legal literal filename characters? | Yes (text says "pattern" only) | Only `pattern` is checked against the disallowed set; `path` is matched as literal data with no syntax restriction, since `path` is never parsed for operators. |
| Q6 | implementer | All of §5's `**` rules are phrased in terms of the pattern; can a real path segment that is literally the two characters `**` ever be matched by a literal (non-wildcard) pattern segment? | Yes, by exhaustive reading (it cannot) | Per §5, a pattern segment that is *exactly* `**` is unconditionally the directory-crossing wildcard, with no escape syntax defined anywhere — so a literal `**` path segment can only ever match incidentally (via the wildcard itself, or via `*`/`?`), never via an exact literal pattern token. Implemented literally; flagged as a faithful-but-surprising consequence, not a bug. |
| Q7 | implementer | §7.1 has no "empty segment contributes nothing" clause (unlike §6 step 5) — does the empty first segment from a leading `/` get pushed onto the dot-segment stack like an ordinary segment, and if so, does a leading `..` then silently cancel against it? | **No — this is a genuine spec defect, not a mere ambiguity** | Implemented the algorithm exactly as literally written: the empty segment is pushed and a leading `..` cancels it, so `/../a` → `/a`. This is the literal algorithm's output. **Orchestrator follow-up (post-freeze):** verified directly against the Python reference implementation (`_normalize_url_dot_segments`) — it produces exactly `/../a` → `/a`, confirming the implementer's literal-algorithm reading is correct and matches the reference. The defect is in the spec's own §7.1 prose ("a leading or repeated `..` is preserved"), which oversells what the stated algorithm actually does for this case. **Action: `docs/nic-v1.1-spec.md` §7.1 prose needs correction to match its own algorithm.** Also noted: no corpus case exercises a URL path with a leading `..`, so this divergence-risk would not have been caught by the corpus either — a gap in the corpus, not just the spec. |
| Q8 | implementer | §7's prose never addresses: multiple `@` in authority, IPv6-bracketed hosts, non-numeric/malformed ports, missing scheme, malformed percent-encoding (`%` not followed by 2 hex digits). | No (five bundled gaps) | Conservative choices throughout, consistent with §7's "preserve verbatim" character: split authority on the *last* `@`; treat bracketed `[...]` tokens as opaque hosts; keep an unparseable port verbatim rather than erroring; treat a missing scheme/colon as a genuine parse error (the grammar requires it unconditionally); pass malformed `%` sequences through unchanged rather than erroring or guessing. |
| Q9 | implementer | §9's table says `proof_payload` is "any well-formed JSON object; not further constrained" — does this require recursively validating its contents, or just checking its top-level type is `object`? | Yes ("not further constrained" reads as deliberate) | Implemented type-only checking (`is_object()`), no recursive validation — read "not further constrained" as an explicit instruction not to add validation beyond the type check. |
| Q10 | implementer | §3 says non-integer/non-finite numbers' canon_json encoding "is not defined" — what should `registry_hash` do if a loaded registry document actually contains one? | No (explicitly declared undefined, not a behavior to invent) | Chose to fail loudly (`Err(RegistryError)`) for any JSON number not representable as `i64`, rather than invent a silent fallback (round, truncate, decimal-point string) that would produce a `registry_hash` with no normative meaning and that a different implementation might compute differently. |

## Results (corpus revealed post-freeze)

The corpus (`cases.json`, `manifest.json`, `edge_extractor_v1.json`) was
copied into the clean-room environment only after the commit recorded as
the Completion timestamp above. No changes were made to `src/` after
reveal; a separate evaluation harness (`tests/golden_corpus.rs`) was added
by the orchestrator to drive the frozen implementation's existing public
API against every case.

- **Golden corpus (27 cases):** 27/27 passed.
- **Manifest hash parity:** `proof_schema_hash` and `registry_hash` both
  matched the committed `manifest.json` exactly.
- **Verdict: Pass.** All four Pass conditions hold: implementation
  completed from the spec alone; no access to `src/` or `conformance/`
  at any point; corpus revealed only after freeze; corpus results match
  expected outputs exactly, with zero discrepancies.

Despite the clean Pass, the experiment surfaced one genuine spec defect
(**Q7**) that the corpus itself does not exercise: `docs/nic-v1.1-spec.md`
§7.1's prose claims a leading `..` in a URL path is "preserved," but the
algorithm as literally specified silently cancels it against the empty
segment produced by a leading `/`. The implementer followed the literal
algorithm (correctly — it matches the Python reference exactly) and
flagged the prose/algorithm mismatch unprompted. This is exactly the kind
of finding the question-log mechanism was designed to surface: a
divergence invisible to corpus-based testing alone, caught only because
an independent reader had to reconcile the prose with the algorithm
without being able to fall back on fixtures. §7.1's prose should be
corrected to describe what the algorithm actually does.

A second, lower-stakes point (**Q2**, literal UTF-16 code-unit key
ordering) was correctly resolved entirely from the spec text and is
recorded as a completeness data point, not a defect.

The full implementation, `QUESTIONS.md`, and `FREEZE.md` are preserved at
`docs/experiments/nic-cleanroom-001-impl/`.
