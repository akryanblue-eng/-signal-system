# Experiment NIC-CLEANROOM-002: Specification Sufficiency Test (Run 2)

## Purpose

Replicate NIC-CLEANROOM-001 with a different implementation language (Go
instead of Rust) to determine whether the Q-log's uncertainty geometry is
stable across independent implementations — i.e., whether the UNDERSPECIFIED
cluster (run #1: Q1, Q8, Q10) is a property of the spec or an artifact of
the Rust interpreter's type system.

Secondary goals:
- Validate the Q7 spec fix: verify that §7.1's updated prose (with worked
  examples) eliminates the prose/algorithm mismatch for a second implementer
- Confirm that corpus cases bound-007/008/009 (added to exercise the Q7 fix)
  pass under an independent implementation
- Surface any new underspecified regions that Rust's type system may have
  silently resolved

This is the second data point for Level C in the evidentiary framework:

| Level | Question | Status |
|---|---|---|
| A — internal consistency | Does one implementation's own test suite pass? | Proven |
| B — cross-runtime reproducibility | Do two independent-language implementations converge given the same fixtures? | Proven (Python `src/`, TypeScript `conformance/typescript/`) |
| C — specification sufficiency | Does an implementation built from prose alone converge on fixtures it never saw? | Proven (run #1 Rust, run #2 Go — both PASS) |

## Metadata

- **Experiment ID:** NIC-CLEANROOM-002
- **Date started:** 2026-07-01
- **Spec version under test:** `docs/nic-v1.1-spec.md` as committed on
  `claude/normalizer-v1-authority-0ieer4` (same spec as run #1, with the
  §7.1 defect fixed post-run-#1; corpus at corpus_release v1.1, 30 cases)
- **Implementation language:** Go 1.21 (chosen by the orchestrating agent;
  maximally distant from run #1's Rust in type-system behavior — Go uses
  `interface{}` / `map[string]interface{}` for parsed JSON rather than
  Rust's algebraic types)
- **Agent/model:** clean-room implementer is a fresh `general-purpose` subagent
  launched via the `Agent` tool; inherits the session model (`claude-sonnet-4-6`)
- **Isolation mechanism:** standalone git repository at `/home/user/nic-cleanroom-002`,
  created via `git init` (not `git worktree`) — same isolation mechanism as run #1

### Available artifacts (Phase 1 — implementation)

- `docs/nic-v1.1-spec.md` (verbatim, the sole NIC-specific artifact)
- Standard Go toolchain (`go build`, `go test`)
- `golang.org/x/text/unicode/norm` for NFC normalization (public, generic)
- Standard Go library: `crypto/sha256`, `encoding/hex`, `encoding/json`, `sort`, etc.
- Whatever standard knowledge of Go, JSON, URIs, Unicode, and SHA-256 the
  model already has from training

### Unavailable artifacts (withheld until freeze)

- `src/` (Python reference implementation)
- `conformance/` (TypeScript port)
- `src/golden_corpus/cases.json`
- `src/golden_corpus/manifest.json`
- `src/edge_extractor_v1.json`
- `docs/experiments/nic-cleanroom-001.md` and all run #1 artifacts
- Commit history, commit messages, or diffs from the main repo

### Completion timestamp

`2026-07-01` — commit `7f5051f` in the clean-room repo
(`Freeze: Go implementation + Q-log (NIC-CLEANROOM-002)`), the commit
at which `FREEZE.md` was written and the implementer declared the work
complete. The corpus was not copied into the clean-room environment until
after this commit.

### Orchestration notes

The agent suffered two "Connection closed mid-response" terminations during
this run:
- **First failure (INIT stage):** Repo was bootstrapped but agent invocation
  never completed; zero artifacts emitted. Classified as an orchestration-layer
  failure, not a spec or implementation issue. Clean rerun performed.
- **Second failure (EXECUTION stage):** Implementation files (`nic.go`,
  `nic_test.go`, `go.mod`, `go.sum`) were written and tests passed, but the
  agent was terminated before writing `QUESTIONS.md`, `QUESTIONS.json`, or
  `FREEZE.md`. The agent was resumed via `SendMessage` to complete only the
  documentation phase; no code changes were made on resume.

In both cases the cleanroom repo was verified uncontaminated before
proceeding (no partial state in case 1; no code changes in case 2).

## Success criteria (declared before corpus reveal, same as run #1)

- **Pass:** Implementation completed from `docs/nic-v1.1-spec.md` alone; no
  access to `src/` or `conformance/`; corpus revealed only after
  implementation freeze; corpus results match expected outputs.
- **Partial pass:** Minor discrepancies traceable to ambiguous spec language,
  with the implementer having documented their interpretation.
- **Fail:** Multiple independent interpretation gaps, or behavior not derivable
  from the spec at all.

## Question log summary

20 Q-entries; 87 unit tests; all tests passing before corpus reveal.

Full Q-log in `nic-cleanroom-002-qlog.json`.

| # | Section | Type | Subtype | Corpus? | Summary |
|---|---|---|---|---|---|
| Q1 | §3 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | yes | UTF-16 key sort is explicit in spec; implemented generically |
| Q2 | §3 | UNDERSPECIFIED | — | **no** | `\uXXXX` hex case not specified; chose lowercase |
| Q3 | §3 | UNDERSPECIFIED | — | **no** | float64→int64 conversion in Go JSON is language-specific |
| Q4 | §11.1 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | yes | canonical_path hex encoding is explicitly stated |
| Q5 | §11.1 | UNDERSPECIFIED | — | **no** | glob_match path pre-canonicalization not specified |
| Q6 | §8 | WELL_SPECIFIED_CONFIRMED | STRUCTURALLY_DETERMINED | **no** | set_hash of empty list = SHA-256 of zero bytes |
| Q7 | §8 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | yes | check_no_unknown_edges computes edge_id to compare |
| Q8 | §9.1 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | yes | proof_payload must be JSON object |
| Q9 | §9.2 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | **no** | schema_descriptor fields must be sorted |
| Q10 | §7 | UNDERSPECIFIED | — | **no** | schemeless URL not addressed by spec |
| Q11 | §7 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | yes | authority omission rule explicit |
| Q12 | §7 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | yes | `?` omission when query empty explicit |
| Q13 | §7.1 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | yes | leading-slash reattachment explicit; worked example confirms |
| Q14 | §7.1 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | yes | /../../a → /../a confirmed by worked example in spec |
| Q15 | §5 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | yes | `**` zero-segment match explicit |
| Q16 | §5 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | **no** | `**` within segment = ordinary wildcard |
| Q17 | §8 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | yes | edge_id sort order (ASCII hex = byte order) |
| Q18 | §6 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | yes | step 4 after step 3 (frozen step order) |
| Q19 | §6 | UNDERSPECIFIED | — | **no** | empty string output from `.` not addressed |
| Q20 | §10 | WELL_SPECIFIED_CONFIRMED | EXPLICIT_SPECIFIED | **no** | parse-then-canon_json is what spec says |

**Distribution:** 15 WELL_SPECIFIED_CONFIRMED (75%), 5 UNDERSPECIFIED (25%), 0 SPEC_DEFECT (0%)

## Results (corpus revealed post-freeze)

The corpus (`cases.json`, `manifest.json`, `edge_extractor_v1.json`) was
copied into the clean-room environment only after the commit recorded as
the Completion timestamp above. `golden_corpus_test.go` was added by the
orchestrator post-freeze to drive the frozen API against the corpus.

- **Golden corpus (30 cases):** 30/30 passed.
- **Manifest hash parity:** `proof_schema_hash` and `registry_hash` both
  matched the committed `manifest.json` exactly.
  - `proof_schema_hash`: `ac21795216cf87180131e335498ab19ae9553b25fe12050b04b31dd1f793255c`
  - `registry_hash`: `7a6d7d33819741a279d2cadbedd749211fc5d7c0e4d6813521d83f589d0f5b12`
- **Verdict: Pass.**

## Comparative analysis: run #1 vs run #2

### Q-log distribution

| Metric | Run #1 (Rust) | Run #2 (Go) |
|---|---|---|
| Total Q-entries | 10 | 20 |
| WELL_SPECIFIED_CONFIRMED | 6 (60%) | 15 (75%) |
| UNDERSPECIFIED | 3 (30%) | 5 (25%) |
| SPEC_DEFECT | 1 (10%) | 0 (0%) |

The defect count dropped to 0 because the Q7 §7.1 prose fix between
runs eliminated that finding. The Go implementer (Q13, Q14) confirmed
§7.1 as WELL_SPECIFIED_CONFIRMED, validating the fix.

### UNDERSPECIFIED cluster stability (the primary measurement)

**Run #1 Q1 (§3, negative integers) vs Run #2 Q3 (§3, float64→int64):**
Same section (§3), same classification (UNDERSPECIFIED), different surface.
Rust's type system handles negative integers naturally (`i64`), so run #1
asked "what about negatives?" explicitly. Go's JSON unmarshaler produces
`float64`, so run #2 asked "how do I convert float64?" instead. Both reached
UNDERSPECIFIED for the same underlying region (§3 number handling for
non-positive-integer inputs). **STABLE in classification; surface is
language-conditioned.**

**Run #1 Q8 (§7, authority edge cases) vs Run #2 Q10 (§7, schemeless URL):**
Same section (§7), same classification (UNDERSPECIFIED). Run #1 bundled five
§7 gaps (multiple @, IPv6, malformed port, missing scheme, malformed %) as
one entry; run #2 surfaced the missing-scheme case as its own entry. The Go
implementer Q10 is a strict subset of run #1's Q8 bundle. **STABLE in
classification; run #2 has sharper issue localization.**

**Run #1 Q10 (§10, non-integer in registry) vs Run #2 Q20 (§10, parse vs raw):**
DIVERGENCE: run #1 classified §10's registry_hash as UNDERSPECIFIED (what to
do with non-integer registry values?); run #2 classified it WELL_SPECIFIED_CONFIRMED
(the spec says `canon_json(registry)` clearly; the number-type concern is
already captured in Q3/§3). Run #2's classification is more precise: the
spec gap lives in §3 (number handling), not §10 (which merely delegates to
§3 via canon_json). **Partial stability: same underlying spec gap (§3 numbers),
different attribution (§10 vs §3).**

### New UNDERSPECIFIED entries in run #2 (not in run #1)

**Q2 (§3, `\uXXXX` escape casing) — HIGH RISK, dark spot:**
The spec says control characters are "escaped per the JSON grammar" but does
not specify whether `\uXXXX` hex digits are lowercase or uppercase. The Go
implementer chose lowercase; if the reference uses uppercase, all hashes over
strings with control characters would differ. No current corpus case exercises
this (corpus strings don't contain U+0000–U+001F). This is a genuine new
spec gap surfaced by the Go implementer; the Rust implementer apparently
resolved it via the same convention without flagging it.

**Q5 (§11.1, glob_match path pre-canonicalization) — medium risk, dark spot:**
The spec's §11.1 op table doesn't say whether the `path` argument to `glob_match`
must be passed through §6 first. Both runs treated it as pre-canonicalized
(no re-canonicalization), so corpus passes, but the question is genuinely
unresolved by the spec text.

**Q19 (§6, empty canonical path) — low risk, dark spot:**
The input `.` reduces to zero segments → empty string. The spec doesn't say
whether to accept or reject this. No corpus case exercises it.

### Q7 fix validation (bound-007/008/009)

All three new corpus cases pass (30/30 total). The Go implementer's Q13 and
Q14 both classify §7.1 behavior as WELL_SPECIFIED_CONFIRMED/EXPLICIT_SPECIFIED,
citing the worked examples in the updated spec text. The fix held.

### Interpretation

The primary empirical question — "is UNDERSPECIFIED a property of the spec
or a property of the interpreter?" — has a clear answer from these two runs:

**UNDERSPECIFIED is a property of the spec.** The §3 number handling region
and the §7 URL parsing region are both underspecified, and both runs converge
on UNDERSPECIFIED for those regions, even though the specific surface
(negative-integers vs float64 conversion; five-gap bundle vs single gap)
differs by language. The spec is genuinely dark in those regions.

**New finding:** The `\uXXXX` escape casing (Q2) is a genuine spec gap that
run #1 did not surface, suggesting the Rust implementer's convention
happened to match the reference silently. This dark spot should be addressed
in a spec patch.

## Implementation snapshot

The frozen Go implementation is preserved at
`docs/experiments/nic-cleanroom-002-impl/`. It is a verbatim copy of the
files in the standalone clean-room repo at freeze time.
