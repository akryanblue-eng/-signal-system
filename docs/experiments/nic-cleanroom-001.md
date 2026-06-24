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

TBD — to be filled in when the implementation is declared frozen, before
the corpus is revealed.

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

(Further rows are appended as the new clean-room agent raises questions.)
