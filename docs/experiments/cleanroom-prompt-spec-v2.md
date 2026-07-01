# Clean-Room Prompt Specification v2

Protocol for future clean-room conformance experiments. Version 2 differs
from the first run's (ad-hoc) prompt by injecting the Q-log schema upfront
so classification is emitted at the point of resolution, not retrofitted
afterward.

## Environment setup (orchestrator responsibilities, done before launching)

- Create a standalone `git init` repository at a fresh path (NOT a
  `git worktree` of the main repo — worktrees share object databases and
  leak history via `git show`). Confirm with `git log --all --oneline`
  that the repo contains exactly one commit and no remote.
- Copy `docs/nic-v1.1-spec.md` from the main repo into the clean-room
  repo's `docs/` directory and commit it. This is the only file the
  agent is allowed to see.
- Do NOT copy `cases.json`, `manifest.json`, `edge_extractor_v1.json`,
  or any source file. These are revealed only after freeze.
- Record experiment metadata per `docs/experiments/qlog-schema.v1.json`
  before the agent launches (available artifacts, unavailable artifacts,
  agent/model, spec commit hash).

## Task text (copy verbatim into the Agent prompt)

---

You are doing clean-room implementation work for a specification-sufficiency
experiment. Read this entire prompt before doing anything.

**Working directory:** `[PATH]` — a standalone git repository (git init,
one commit) containing exactly one file: `docs/nic-v1.1-spec.md`. Read
that file first. It is a complete, standalone normative specification.
Implement it in [LANGUAGE] as a library, covering every operation named
in the spec's §11.1 table: `canonical_path`, `glob_match`,
`canonicalize_url`, `compute_edge_id`, `compute_set_hash`,
`compute_witness_hash`, `check_no_unknown_edges`, `verify_proof_schema` —
plus `proof_schema_hash` (§9.2) and `registry_hash` (§10). Write your
own unit tests based on your own reading of the spec; you have no fixtures.

### Hard isolation rules

1. Do not read, list, or inspect anything outside `[PATH]`.
2. Do not web-search "NIC", "Normative Import Closure", "edge_extractor",
   or similar project-specific terms.
3. Generic, publicly-known infrastructure is fine (SHA-256 crate/library,
   JSON parser, Unicode NFC normalization) — these encode no
   information about this spec.
4. Keep a `QUESTIONS.md` file (prose log) **and** a `QUESTIONS.json` file
   (machine-readable log) as described below.

### Q-log protocol (this is a primary deliverable, not incidental)

Every time you reach a decision point where the spec does not fully determine
the behavior — or where you need to verify that it does — pause and record
the entry **before continuing implementation**. Do not accumulate entries
and write them all at the end; emit each one when you resolve it.

**QUESTIONS.md** (prose): full human-readable explanation for each entry,
as in the first clean-room run. Number entries Q1, Q2, etc.

**QUESTIONS.json** (machine-readable): an array of objects, one per entry,
conforming to this schema. Write a new entry to this array whenever you
write a prose entry:

```json
{
  "id": "Q1",
  "section": "<spec section anchoring the question, e.g. §3>",
  "type": "<WELL_SPECIFIED_CONFIRMED | UNDERSPECIFIED | SPEC_DEFECT>",
  "subtype": "<EXPLICIT_SPECIFIED | STRUCTURALLY_DETERMINED | null>",
  "cause": ["<one or more from the vocabulary below>"],
  "claim_summary": "<one sentence: the question as you'd phrase it>",
  "resolution_summary": "<one sentence: what you decided and why>",
  "corpus_exercises_this": null
}
```

**Classification rules** — answer these three questions in order, the first
match wins:

1. **Do two parts of the spec disagree with each other** (prose contradicts
   algorithm, two sections conflict)? → `SPEC_DEFECT`
2. **Did you need to introduce logic or a constraint not present in the spec
   text** (the spec is silent, ambiguous, or only covers well-formed inputs)?
   → `UNDERSPECIFIED`
3. **Did spec text or language/grammar structure fully determine the
   behavior without inference**? → `WELL_SPECIFIED_CONFIRMED`

For `WELL_SPECIFIED_CONFIRMED`, also set `subtype`:
- `EXPLICIT_SPECIFIED`: a spec sentence directly states the rule
- `STRUCTURALLY_DETERMINED`: the language's type system or the spec's
  grammar makes the case unreachable or trivially satisfied

**Cause vocabulary** (use one or more per entry):

| Token | Meaning |
|---|---|
| `direct_spec_text` | a spec sentence directly resolves this |
| `frozen_step_order` | the spec's frozen-step framing determines evaluation order |
| `grammar_impossibility` | the spec grammar makes this case structurally unreachable |
| `type_system_guarantee` | the implementation language's type system enforces this by construction |
| `explicit_exclusion` | spec text explicitly says "not further constrained," "never appears," etc. |
| `logical_consequence` | follows by combining multiple explicit spec rules; no single sentence suffices |
| `language_conditioned` | this classification would differ for another implementation language |

**The goal of the Q-log** is to produce a map of where the spec is fully
determined vs. where inference was required. An entry that resolves to
`WELL_SPECIFIED_CONFIRMED` is as important as one that resolves to
`UNDERSPECIFIED` — it proves the spec covers that region. Zero entries is
a valid (and notable) outcome.

### When you're done

When you consider your implementation complete per your own reading of the
spec: write `FREEZE.md` (summary of what's implemented, residual
uncertainty, highest-risk divergence points). Commit everything. Do not
seek test fixtures, do not ask whether you're right. End your turn and
report back with:

1. Explicit confirmation you never accessed anything outside `[PATH]`
   and never web-searched project-specific terms
2. List of files created
3. Full contents of `QUESTIONS.json` verbatim
4. Full contents of `FREEZE.md`
5. Build and test commands

---

## Post-freeze orchestrator actions

After the agent's turn ends:

1. Record `Completion timestamp` in the experiment file.
2. Copy `cases.json`, `manifest.json`, `edge_extractor_v1.json` into the
   clean-room repo.
3. Write an evaluation harness (language-appropriate integration test)
   that drives the frozen implementation's public API against each corpus
   case, mapping op names from §11.1 to functions. Do not modify `src/`.
4. Run the evaluation harness. Record: N/M corpus pass, manifest hash
   parity (proof_schema_hash, registry_hash match/mismatch).
5. Set `corpus_exercises_this` on each QUESTIONS.json entry.
6. Determine verdict: Pass / Partial-pass / Fail per the criteria in
   the experiment record.
7. Merge QUESTIONS.json entries into the experiment's Q-log JSON file
   (`nic-cleanroom-XXX-qlog.json`) and compute updated coverage stats.
8. Commit everything to the main repo under
   `docs/experiments/nic-cleanroom-XXX-impl/` before the container is
   reclaimed.

## What run #2 should measure (empirical targets)

The first run established a 60/30/10 baseline (WELL_SPECIFIED /
UNDERSPECIFIED / SPEC_DEFECT) from 10 Q-entries. Run #2 tests whether:

- The 30% underspecified cluster is **stable**: do Q1 (negative integers),
  Q8 (authority edge cases), Q10 (non-integer registry numbers) appear in
  a second implementer's Q-log, with the same classification?
- The 60% confirmed cluster is **reproducible**: does a different
  implementer also confirm Q2, Q4, Q5, Q9 without hesitation?
- The Q7 fix **holds**: do the three new bound-007/008/009 corpus cases
  pass, and does the §7.1 worked example in the spec prevent the
  prose-misreading the first implementer caught?
- **New questions surface**: does a different language or implementer
  expose gaps the first run missed?

Stability of the underspecified cluster is the primary signal. If Q1/Q8/Q10
appear in run #2 with the same classification, those entries are genuine
spec gaps and candidates for the next spec revision. If they don't appear,
either the spec was clarified in ways that resolved them, or the new
implementer made a different but equally defensible choice — both of which
are information.
