# Director Loop V2 — Closure Certificate

**Status:** SEALED  
**Effective Date:** 2026-06-09  
**Branch:** `claude/director-loop-audit-86owb0`  
**Final commit:** `0e7b9ef`

---

## 1. Scope

This certificate records the exact state of the V2 adjudication protocol at the point of closure. It is a faithful description of the code that was compiled, tested, and pushed — not a design aspiration. Any claim here that cannot be verified by reading `src/verifier_v2.rs` and `src/director_loop_v2.rs` is an error.

**Closure is conditional.** V2 defines a deterministic evaluator over a fixed artifact space, conditional on a pinned toolchain and dependency graph, with no runtime-dependent semantic branching. The formal statement is:

```
E_V2(x; T, D) → PASS | FAIL(g_i, c_i, p_i)
```

Where `x` is the artifact, `T` is the pinned Rust toolchain (see Section 9), and `D` is the locked dependency graph (`Cargo.lock`). No semantic branching exists outside these parameters. The evaluation substrate is explicit and legible, not assumed.

Future protocol evolution is treated as a V3 branch with an explicit struct-diff against this certificate.

---

## 2. Core Principles

- **Fail-fast:** Gates are evaluated sequentially. The first failing gate returns immediately; all downstream gates are marked `NotEvaluated`. There is no error accumulation.
- **Typed failure taxonomy:** Every failure surface is a variant of `FailureCodeV2`. No free-text codes, no string D-codes. Tests and CI assert on enum variants.
- **No repair:** The verifier is a pure adjudicator. It never mutates, normalizes, or repairs the artifact.
- **Typed boundary:** `serde_json::Value` exists only at the schema gate ingress. All gates after Gate 1 operate on `DirectorLoopRunV2` and its nested typed structs.
- **No non-deterministic structures:** Correction anchor checks use a sorted `Vec` + `binary_search`. No `HashMap`, no `HashSet`, no iteration order dependence.

---

## 3. The Five Gates (pipeline order — immutable)

### Gate 1 — Schema
- **Entry point:** `verify_bytes_v2(bytes: &[u8])`
- **Mechanism:** `serde_json::from_slice::<DirectorLoopRunV2>` with `#[serde(deny_unknown_fields)]` on all domain structs.
- **Failure code:** `FailureCodeV2::SchemaViolation`
- **On failure:** All downstream gates → `NotEvaluated`.

### Gate 2 — Structural
- **Entry point:** `gate_structural(run: &DirectorLoopRunV2)`
- **Checks (in order, first failure returns):**
  1. `execution.timeline` non-empty → `TimelineEmpty`
  2. `timeline[i].step == i` for all `i` → `TimelineNonMonotonic`
  3. `timeline.last().state == execution.status` → `TimelineStatusMismatch`
  4. Every `corrections[i].beat_id` is present in `transitions ∪ regen_events` (sorted `Vec` + `binary_search`) → `CorrectionsOrphanedBeatId`
  5. `audit.notes` non-decreasing → `AuditNotesOutOfOrder`
  6. `audit.warnings` non-decreasing → `AuditWarningsOutOfOrder`
- **On failure:** State, input_hash, output_hash → `NotEvaluated`.

### Gate 3 — State
- **Entry point:** `gate_state(run: &DirectorLoopRunV2)`
- **Checks (in order, first failure returns):**
  1. `status == PASSED → final_coherence >= threshold` → `PassedBelowThreshold`
  2. `status == PASSED → final_coherence >= initial_coherence` → `PassedCoherenceRegressed`
  3. `status == REGENERATED → regen_events non-empty` → `RegenWithoutEvents` (path: `execution.regen_events`)
  4. `regen_events non-empty → REGENERATED appears in timeline` → `RegenWithoutEvents` (path: `execution.timeline`)
- **On failure:** input_hash, output_hash → `NotEvaluated`.

### Gate 4 — Input Hash
- **Preimage struct:** `InputHashPreimageV2` — fields in definition order: `v2_version`, `run_id`, `parent_run_id`, `protocol_sha`, `inputs`
- **Algorithm:** `SHA-256(serde_json::to_vec(preimage))`
- **Canonicalization:** Rust `serde_json::to_vec()` struct-definition-field order. No JCS. No NFC. No external normalization.
- **Failure code:** `FailureCodeV2::InputHashDrift`
- **On failure:** output_hash → `NotEvaluated`.

### Gate 5 — Output Hash
- **Preimage struct:** `OutputHashPreimageV2` — fields in definition order: `v2_version`, `run_id`, `parent_run_id`, `execution`, `audit`, `input_hash`
- **Algorithm:** `SHA-256(serde_json::to_vec(preimage))`
- **Canonicalization:** same as Gate 4.
- **Failure code:** `FailureCodeV2::OutputHashDrift`

---

## 4. Failure Code Taxonomy

All codes are variants of `FailureCodeV2` in `src/verifier_v2.rs`.

| Variant | Gate | Meaning |
|---|---|---|
| `SchemaViolation` | Schema | Parse failure or unknown field |
| `TimelineEmpty` | Structural | `execution.timeline` is empty |
| `TimelineNonMonotonic` | Structural | `timeline[i].step != i` |
| `TimelineStatusMismatch` | Structural | Terminal timeline state ≠ `execution.status` |
| `CorrectionsOrphanedBeatId` | Structural | `corrections[i].beat_id` not in `transitions ∪ regen_events` |
| `AuditNotesOutOfOrder` | Structural | `audit.notes` not non-decreasing |
| `AuditWarningsOutOfOrder` | Structural | `audit.warnings` not non-decreasing |
| `PassedBelowThreshold` | State | `PASSED` with `final_coherence < threshold` |
| `PassedCoherenceRegressed` | State | `PASSED` with `final_coherence < initial_coherence` |
| `RegenWithoutEvents` | State | `REGENERATED` ↔ `regen_events` coupling violated |
| `InputHashDrift` | Input Hash | Recomputed input hash ≠ artifact's `input_hash` |
| `OutputHashDrift` | Output Hash | Recomputed output hash ≠ artifact's `output_hash` |

---

## 5. Hash Determinism Contract

The determinism guarantee is: **identical struct field values → identical `serde_json::to_vec` bytes → identical SHA-256 digest**.

This guarantee is provided by Rust's type system and serde's deterministic struct serialization. It does not claim compliance with any external canonicalization standard (RFC 8785 JCS, Unicode NFC, etc.). Callers who need cross-language hash verification must implement the same field-order-preserving compact JSON serialization independently.

Preimage field order is frozen at struct definition. Reordering either preimage struct is a breaking change requiring a new protocol version.

---

## 6. Lineage

`parent_run_id` is `Option<String>`. Its presence is recorded in the input hash preimage but the verifier performs no external resolution — there is no parent store, no recursive check, no transitive validation. Cross-artifact lineage verification is out of scope for the single-artifact verifier and belongs to a higher-level orchestration layer.

---

## 7. Test Coverage

`tests/drift_suite_v2.rs` — 17 tests at seal time:

- `baseline_v2_passes` — golden fixture clears all 5 gates
- `v2_d01` through `v2_d13` — one test per `FailureCodeV2` variant (excluding `SchemaViolation` variants that duplicate `d03`)
- `v2_structural_fires_before_state` — ordering proof
- `v2_state_fires_before_hash` — ordering proof
- `v2_correction_anchored_by_regen_event_passes` — positive anchor round-trip

All tests assert on typed enum variants, not strings or exit codes.

---

## 8. Golden Fixture

`fixtures/v2/temporal_collapse_001/director_loop_run_v2.json`

```
input_hash:  0f182749e591646913a6f87c851bb9d63d32a2fded7f50b2163046c4363a3256
output_hash: e9695aa823852954b8737637731a47446de60113378b640b07938a7b7617704c
```

These values are recomputed and verified on every CI run by the `verifier calibration v2` step. Hash drift in the committed fixture is a hard CI break (exit 1).

---

## 9. Toolchain Pin

The determinism guarantee in Section 5 — "identical struct → identical bytes → identical hash" — holds exactly under a pinned execution substrate, not unconditionally. The substrate is:

| Component | Pinned version |
|---|---|
| Rust | `1.94.1` (see `rust-toolchain.toml`) |
| serde | `1.0.228` (see `Cargo.lock`) |
| serde_json | `1.0.150` (see `Cargo.lock`) |
| sha2 | `0.10.9` (see `Cargo.lock`) |

`Cargo.lock` is committed and `rust-toolchain.toml` pins the compiler. CI reads both. Upgrading any of these is a V3 event if it changes serialized output — in practice any serde_json minor version that alters `to_vec` output for a typed struct would be a hash-breaking change.

---

## 10. What V3 Must Provide

Any protocol evolution that changes gate logic, preimage field sets, or `FailureCodeV2` variants is a V3 change. V3 must:

1. Define a new top-level version field (e.g., `v3_version`)
2. Document the struct-diff against this certificate
3. Provide its own golden fixture with independently computed hashes
4. Keep V2 types untouched — V2 and V3 are separate namespaces

---

## 11. V2 → V3 Version Boundary (Normative)

A change is a **V3 transition event** — not a V2 patch — if and only if it satisfies any of the following conditions.

### 11.1 Preimage Structure Mutation

Any modification to either preimage struct:

- `InputHashPreimageV2` — fields: `v2_version`, `run_id`, `parent_run_id`, `protocol_sha`, `inputs`
- `OutputHashPreimageV2` — fields: `v2_version`, `run_id`, `parent_run_id`, `execution`, `audit`, `input_hash`

Covered mutations: adding a field, removing a field, renaming a field, reordering fields.

**Effect:** invalidates all previously computed `input_hash` / `output_hash` values under V2 semantics.

### 11.2 Failure Algebra Mutation

Any change to `FailureCodeV2`: adding variants, removing variants, or reordering variants.

**Effect:** breaks exhaustiveness assumptions at all `match` sites; invalidates all test oracle mappings that assert on specific variants.

### 11.3 Gate Order Mutation

Any modification to the evaluation sequence `schema → structural → state → input_hash → output_hash`, including reordering, insertion of intermediate gates, or removal of gates.

**Effect:** changes first-failure resolution semantics; invalidates drift-suite ordering-proof tests.

### 11.4 Wire Format Mutation

Any change to serialized identity-critical enums — `RunStatus` or `TimelineEvent` — including renaming variants or changing their `#[serde(rename = "...")]` tags.

**Effect:** breaks artifact replay compatibility; invalidates historical fixture decoding.

### 11.5 Non-V3 Mutations (Explicit Exclusion Set)

The following are V2-compatible extensions and do not require a version increment:

- adding helper functions or internal modules
- expanding audit logging (append-only)
- adding new tests or fixtures
- optimizing hash implementation without changing preimage content
- CI changes that do not alter runtime semantics
- documentation updates

### 11.6 Version Boundary Invariant

A V2 system is any system in which all valid artifacts remain mutually hash-compatible under the same `E_V2(x; T, D)` evaluator.

A V3 system is any system where that property is no longer true.

---

*V2 is sealed.*
