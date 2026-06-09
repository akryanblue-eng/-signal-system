# Director Loop Hashing Protocol v1

Extends VDCE v1.1 canonicalization patterns to the Director Loop orchestration layer.

---

## Algorithm

**Hash function:** SHA-256 (matches VDCE v1.1 certificate layer)  
**Canonicalization:** Compact JSON via `serde_json::to_vec` — no pretty-printing, no whitespace  
**Field ordering:** Struct definition order (guaranteed by Rust serde derive)  
**Numeric representation:** Fixed-point integers only — no floats in any hash boundary  

BLAKE3 is reserved for internal streaming/DAG computation and must not appear in `input_hash` or `output_hash`.

---

## Coherence values

All coherence fields (`threshold`, `initial_coherence`, `final_coherence`) are **fixed-point millionths**:

```
0         → 0.000000
500_000   → 0.500000
950_000   → 0.950000
1_000_000 → 1.000000
```

This avoids float-to-string platform variance per VDCE v1.1 rules.

---

## input_hash preimage

Covers the fields that uniquely identify *what was run*. Serialized field order is frozen:

```
InputHashPreimage {
    director_loop_version,  // 1
    threshold,              // 2
    ruleset_version,        // 3
    fixture,                // 4 — full object; contains fixture_id; no top-level duplicate
    config,                 // 5 — full object
}
```

**Rule:** `fixture_id` lives inside `fixture`. It must not appear separately at the top level of the preimage (no duplicate identity anchors).

---

## output_hash preimage

Covers the fields that describe the *state transition*. Serialized field order is frozen:

```
OutputHashPreimage {
    status,             // 1
    initial_coherence,  // 2
    final_coherence,    // 3
    corrections,        // 4 — full nested array; no partial projection
    regen_events,       // 5 — full nested array; no partial projection
    audit_notes,        // 6
}
```

**Rule:** Nested objects (`corrections`, `regen_events`) are serialized in full. No field filtering, no derived summaries, no computed-only subsets.

---

## Hash format

Raw lowercase hex — 64 characters, no prefix:

```
^[a-f0-9]{64}$
```

The `sha256:` prefix is not used (matches `certify.rs` storage convention).

---

## Verification procedure

```rust
let expected_input  = compute_input_hash(&run);
let expected_output = compute_output_hash(&run);

assert_eq!(run.input_hash,  expected_input,  "input_hash mismatch");
assert_eq!(run.output_hash, expected_output, "output_hash mismatch");
```

Both must pass for a run artifact to be considered valid. A mismatch on either is a hard FAIL.

---

## Open items before temporal_collapse_001 freeze

1. **`Fixture` fields:** Only `fixture_id` is currently defined. Add all fixture-specific fields before the first hash is computed for this fixture set. Once hashed, field additions are breaking changes.

2. **`Config` fields:** Only `max_corrections` and `regen_budget` are defined. Same rule applies.

These structs use `additionalProperties: false` in the JSON Schema, enforcing the closed-world contract at validation time.
