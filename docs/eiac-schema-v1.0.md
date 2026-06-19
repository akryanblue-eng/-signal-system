# EIAC Schema v1.0 (Locked, Non-Executable Contract)

Status: structural / non-normative for behavior. This document freezes
**artifact shapes and canonical encoding rules only**. It does not define
execution semantics, compilation, planning, or normalization behavior.

This is a companion to `docs/eiac-stratified-admissibility-v0.1.md` (the
authoritative spec) and `docs/eiac-system-boundary-map.md` (the
visualization). Those documents describe `Env`, `P`, `Proof`, and the K-witness
system in prose; this document gives them concrete, hashable shapes so that a
future verifier (`Extract`) can be implemented against something fixed rather
than something still floating.

No code in this repo implements or depends on this schema yet. It exists so
that *if* an executable verifier is built later, it has a frozen contract to
build against instead of re-deriving shapes ad hoc.

## 0. Design Constraints (non-negotiable)

- Deterministic, content-addressed artifacts.
- No implicit global state — all validation input is explicit in
  `(env, p, proof)`.
- Canonical encoding is specified so hashing and equality are stable across
  implementations.
- vPNF is not required for v1.0. If introduced later it must operate over
  these shapes without changing them.

## 1. Canonical Primitives

### 1.1 IDs and hashes

- `Hash256` — a 32-byte value.
- `Id` — a UTF-8 string matching `[a-zA-Z0-9._/-]+` (no whitespace). Used only
  as a human label; never a semantic authority unless explicitly referenced
  by a witness.

### 1.2 Canonical encoding

A single canonical byte-encoding function is assumed:

```
canon(x) -> bytes
```

Rules:

- Canonical binary encoding (CBOR canonical form preferred).
- Maps/objects MUST be sorted by key, lexicographically.
- Integers MUST be minimally encoded.
- No floating point in canonical encodings.
- Byte arrays are literal bytes, not base64, at the canonical layer.
- Strings are UTF-8.
- Every top-level artifact includes a `schema_tag` string.

### 1.3 Content address

For any canon-encoded object:

```
H(x) = SHA256(canon(x))
```

## 2. Environment Schema (`Env`)

`Env` is a concrete, hashable object — the only place global governance
context lives.

```
Env := {
  schema_tag: "EIAC/ENV/v1",
  env_id: string,        // human label only
  caps: CapSet,          // allowed capability edges
  budgets: BudgetSet,    // bounded resources
  zones: ZoneSet         // forbidden regions / no-compile zones
}
```

### 2.1 Capabilities (`CapSet`)

```
CapEdge := {
  from: PrincipalId,
  to: PrincipalId,
  cap: CapName           // e.g. "read", "write", "call", "net", "fs"
}

CapSet := {
  schema_tag: "EIAC/CAPS/v1",
  edges: [CapEdge...]    // canon-sorted by (from, to, cap)
}
```

### 2.2 Budgets (`BudgetSet`)

```
Budget := { name: BudgetName, limit: u64 }

BudgetSet := {
  schema_tag: "EIAC/BUDGETS/v1",
  items: [Budget...]     // canon-sorted by name
}
```

### 2.3 Zones (`ZoneSet`)

```
ZoneRule := {
  zone: ZoneName,             // e.g. "no-network", "no-write-prod"
  selector: ZoneSelector      // declarative match over execution bundles
}

ZoneSelector := {
  type: "match_adapter" | "match_resource" | "match_tag",
  value: string
}

ZoneSet := {
  schema_tag: "EIAC/ZONES/v1",
  rules: [ZoneRule...]   // canon-sorted
}
```

## 3. Execution Bundle Schema (`P`)

`P` is the compiled possibility-space element (an execution candidate). It is
a structured description of intended external ops, not a plan runner.

```
ExecutionBundle := {
  schema_tag: "EIAC/P/v1",
  bundle_id: string,     // human label only
  ops: [Op...]           // canon-sorted by op_id
}
```

### 3.1 Ops

```
Op := {
  op_id: Id,                  // stable within bundle
  adapter: AdapterId,
  principal: PrincipalId,     // who is asserting / executing
  action: ActionName,         // adapter-defined verb string
  resources: [ResourceRef...],// canon-sorted
  params: CanonValue,         // adapter-defined, canon-encoded
  tags: [string...]           // optional, canon-sorted
}

ResourceRef := {
  resource_ns: string,   // namespace, e.g. "db/table", "fs/path"
  resource_id: string    // canonical ID string (not human)
}
```

`CanonValue` is any canon-encodable value: `null | bool | u64 | string |
bytes | array | map`.

## 4. Adapter Projection Spine (`π_a`) and Local Admissibility (`A_a`)

Type-level only in v1.0 — no semantics beyond "there exists a local checker."

```
AdapterId := string
```

Each adapter MUST define:

- an `Env_a` projection view (a function, not a stored object) derived
  deterministically from `Env`
- a local proof object type and verifier for
  `LocalCheck(a, env, p) -> ok | ⊥`

Local evidence is represented as opaque, typed bytes so the global system
stays adapter-agnostic:

```
LocalProof := {
  schema_tag: "EIAC/LOCAL_PROOF/v1",
  adapter: AdapterId,
  payload_tag: string,   // e.g. "S3/LOCAL/v1"
  payload: bytes         // adapter-defined canonical bytes
}
```

## 5. Coupling Witness Universe (`K`)

Matches the locked closure `K = Budgets ⊎ ResourceLocks ⊎ Zones ⊎ GovEdges`.

```
CouplingWitness :=
  | BudgetWitness
  | ResourceLockWitness
  | ZoneWitness
  | GovEdgeWitness
```

### 5.1 Budget witness

```
BudgetWitness := {
  schema_tag: "EIAC/K/BUDGET/v1",
  budget: BudgetName,
  observed: u64,         // claimed usage for this bundle
  op_ids: [Id...]        // optional: accounted ops, canon-sorted
}
```

### 5.2 Resource lock witness

```
ResourceLockWitness := {
  schema_tag: "EIAC/K/LOCK/v1",
  lock_ns: string,
  lock_id: string,
  op_ids: [Id...]        // ops that require this lock
}
```

### 5.3 Zone witness

```
ZoneWitness := {
  schema_tag: "EIAC/K/ZONE/v1",
  zone: ZoneName,
  claim: "allowed" | "not_applicable",
  op_ids: [Id...]
}
```

### 5.4 Governance edge witness

```
GovEdgeWitness := {
  schema_tag: "EIAC/K/EDGE/v1",
  from_adapter: AdapterId,
  to_adapter: AdapterId,
  edge: string,           // e.g. "depends_on", "writes_then_reads"
  op_ids: [Id...]
}
```

## 6. Proof Object Schema (`Proof(env, p; π)`)

A proof is the only admissibility currency, structured as the triple already
locked in the spec doc.

```
Proof := {
  schema_tag: "EIAC/PROOF/v1",
  env_hash: Hash256,             // H(Env)
  bundle_hash: Hash256,          // H(ExecutionBundle)
  local: [LocalProof...],        // one per adapter involved, canon-sorted by adapter
  coupling: [CouplingWitness...],// canon-sorted by (schema_tag, stable fields)
  glue: GlueTrace
}
```

### 6.1 Glue trace (EIAC recomposition witness)

Structural alignment only:

```
GlueTrace := {
  schema_tag: "EIAC/GLUE/v1",
  adapters: [AdapterId...],      // adapters asserted in local proofs, canon-sorted
  op_partition: [
    { adapter: AdapterId, op_ids: [Id...] }
  ],
  notes: string | null           // optional, non-semantic
}
```

Hard rules:

- `glue.adapters` MUST equal the set of `local[].adapter` values.
- `op_partition` MUST cover every `op_id` in the bundle exactly once.

## 7. Extract Verifier Contract (shape only, not an implementation)

This schema implies the shape of a verifier without defining any planning or
synthesis behavior:

```
Extract(env, p, proof) -> ok | ⊥
```

Minimum required checks, all structural rather than semantic:

- `proof.env_hash == H(env)`
- `proof.bundle_hash == H(p)`
- `glue` partitions ops correctly (see §6.1 hard rules)
- each `LocalProof` is well-formed and adapter-tagged
- each `CouplingWitness` is well-typed (matches one of the §5 tags) and
  canon-decodable

Any additional acceptance logic is adapter-local (inside local proof
verifiers) or K-validation (budget/zone/lock/edge checks per §5). The schema
itself adds no execution meaning beyond these structural checks.

## 8. Non-Goals

- No execution engine, compiler, or planner is defined here.
- No normalization (vPNF) behavior is defined here — only that, if it
  exists, it operates over these shapes.
- No criticality (χ(k)) computation is defined here.
- This document does not imply that `Extract` is implemented anywhere in
  this repository. It is a frozen contract for a future implementation to
  build against, not the implementation itself.
