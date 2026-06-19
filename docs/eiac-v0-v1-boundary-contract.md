# EIAC v0 -> v1 Boundary Contract (Locked)

Status: normative for scope only. This document does not introduce new
shapes, new fields, or new behavior. It draws one line: what is already
implemented as `Extract(v0)` (`eiac/extract.py`), versus what any future
semantic admissibility layer (`v1`) would have to add. Crossing this line
is a deliberate, separately authorized step, not an incremental patch to
`Extract`.

This is a companion to `docs/eiac-schema-v1.0.md` (the frozen shapes,
including the §7 `Extract` contract this document refines) and
`docs/eiac-stratified-admissibility-v0.1.md` (the spec that defines
`A(env)` as `∃ Proof(env, p)`, which is the formula `v1` would eventually
have to make computable). Both remain authoritative for their own
concerns; this document only fixes where one ends and the other begins.

## 1. Why this line needs to be explicit

`Extract(v0)` exists and is implemented. It answers one question:

> Is `(env, p, proof)` a well-formed, internally consistent triple?

It does not, and was never specified to, answer the actual admissibility
question from the spec:

> Does `proof` *establish* that `p` is admissible under `env`?

Those are different predicates. Schema §7 already hints at the gap
("Any additional acceptance logic is adapter-local ... or K-validation
... The schema itself adds no execution meaning beyond these structural
checks") without naming it as a layer boundary. This document names it.

## 2. v0 scope (frozen, implemented in `eiac/extract.py`)

`Extract(v0)` is a deterministic structural verifier. Every check it
performs is one of:

- **Identity binding** — `proof.env_hash == H(env)`, `proof.bundle_hash ==
  H(p)`, and each object's `schema_tag` matches its expected per-object
  constant (fail-closed per schema §1.4.3).
- **Partition integrity** — `glue.adapters` equals the set of
  `local[].adapter` values; `op_partition` covers every bundle `op_id`
  exactly once with no duplicates; each `op_partition` entry's claimed
  adapter matches the real `Op.adapter` of every `op_id` it lists.
- **Local-proof well-formedness** — no duplicate adapters in `local`,
  correct `schema_tag`, `payload` is actually `bytes`.
- **Witness well-typedness** — each `CouplingWitness.schema_tag` is one
  of the four known `K` tags, and the witness is canon-decodable.

None of this evaluates whether any claim made by a witness or a local
proof is *true*. `Extract(v0)` cannot reject a `BudgetWitness` for
claiming a budget was exceeded, because it never reads `env.budgets` to
compare against `observed`. It cannot reject a `ZoneWitness` claiming
`"allowed"` for an op that a `ZoneRule` actually forbids, because it
never evaluates `ZoneSelector` against `Op`. This is not a gap to be
patched — it is the v0/v1 line itself.

## 3. v1 scope (not implemented, not designed beyond this list)

Everything below requires reading the *content* of `env` or `p` against
the *content* of a witness or local proof, which is exactly the
boundary v0 does not cross:

- **K-witness validity**: `validate(witness, env, p) -> bool` for each
  witness kind — e.g. does a `BudgetWitness.observed` actually respect
  `env.budgets`'s limit; does a `ZoneWitness.claim` actually follow from
  evaluating `env.zones`'s `ZoneSelector`s against the referenced ops;
  does a `GovEdgeWitness.edge` correspond to a real declared dependency.
- **Adapter-local admissibility** `A_a(π_a(env))`: actually interpreting
  `LocalProof.payload` against an adapter-specific predicate, instead of
  treating it as opaque bytes.
- **Cross-adapter closure**: the `⋂ₐ lift_a(A_a(...))` intersection and
  the `X(env)` term from `A(env)`'s defining formula in the spec — i.e.
  whether per-adapter admissibility actually composes.
- Anything that would make `Extract` return a different verdict for two
  inputs that are structurally identical but semantically different
  (e.g. same shapes, different `observed` value).

`v1` is not designed here. This section is a boundary fence, not a spec.

## 4. The resulting statement of `A(env)`

With this line drawn, the spec's `A(env) ≡ ∃ Proof(env, p)` decomposes
as:

```
Extract(v0)-ACCEPT(env, p, proof)   -- necessary, implemented today
  AND
v1-semantic-evaluation(env, p, proof) -- necessary, NOT implemented
  =>
admissible
```

`Extract(v0)` passing is necessary but not sufficient for admissibility.
No code in this repo currently computes the second conjunct, and no code
should claim to until `v1` is itself frozen the way `v0` was.

## 5. Constraint on any future meta-tool (e.g. a failure minimizer)

Any tool built on top of `Extract` — including, but not limited to, a
future failure-minimization or analysis layer — MUST treat `extract()`
as an opaque black-box predicate over `(env, p, proof)` and MAY only
reason about the `REASON_*` constants `Extract(v0)` defines today. Such
a tool MUST NOT assume:

- that a reduced/minimized input is "meaning-preserving" with respect to
  `v1` semantics, since `v1` does not exist yet to preserve meaning
  against;
- that any `ACCEPT` from `Extract(v0)` implies admissibility (see §4);
- that it may extend `Extract` itself to close the v0/v1 gap as a side
  effect of being built.

If `v1` is later frozen, every such tool built against `v0` alone MUST be
re-validated against the new predicate, not silently treated as already
compatible with it.

## 6. Non-Goals

- This document does not specify `v1`'s schema, algorithms, or witness
  validation rules. It only fences where `v0` stops.
- It does not specify vPNF or χ(k) — both remain out of scope per
  `docs/eiac-schema-v1.0.md` §8 and `docs/eiac-stratified-admissibility-v0.1.md`
  §7.
- It does not authorize starting `v1` implementation. That remains a
  separate, explicit decision.
