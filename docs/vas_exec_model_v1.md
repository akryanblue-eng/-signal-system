# VAS Execution Model v1

**identifier:** vas-exec-model-v1  
**domain:** DSVM-0 (Deterministic Spatial Virtual Machine, Tier Zero)  
**status:** FROZEN — any edit produces a new version, not an amendment

---

## 1. Scope

This document specifies the canonical byte encoding for:
- RI-0 replay commits (WitnessPacket304)
- CT-0 certificate computation
- Signal deduplication and ordering

Implementations in any language that produce identical byte sequences for identical
inputs are considered conformant. The SHA256 digest of this file is embedded in every
`GoldenRoot` computation to make spec drift detectable at the CI boundary.

---

## 2. WitnessPacket304 Structure

A WitnessPacket304 has exactly these fields, in this order:

| # | Field               | Type                   |
|---|---------------------|------------------------|
| 1 | run_id              | UTF-8 string           |
| 2 | prev_state_bytes    | arbitrary bytes        |
| 3 | frozen_batch_bytes  | arbitrary bytes        |
| 4 | bundle_hash         | fixed 32 bytes         |
| 5 | bundle_version      | unsigned 32-bit int    |
| 6 | validator_pubkey    | fixed 32 bytes         |
| 7 | signals             | sequence of (key, i64) |

---

## 3. RI-0 Canonical Encoding

The RI-0 commit is `SHA256(canonical_bytes(packet))` where `canonical_bytes` is the
concatenation of the field encodings below, in field order, with no separators.

### 3.1 Field Encodings

**run_id**  
`uint16-BE(byte_length(run_id)) || utf8_bytes(run_id)`

**prev_state_bytes**  
`uint32-BE(byte_length(prev_state_bytes)) || prev_state_bytes`

**frozen_batch_bytes**  
`uint32-BE(byte_length(frozen_batch_bytes)) || frozen_batch_bytes`

**bundle_hash**  
`bundle_hash` (exactly 32 bytes, no length prefix)

**bundle_version**  
`uint32-BE(bundle_version)` (4 bytes, big-endian)

**validator_pubkey**  
`validator_pubkey` (exactly 32 bytes, no length prefix)

**signals**  
`uint32-BE(byte_length(encode_signals(signals))) || encode_signals(signals)`

### 3.2 Signal Encoding (`encode_signals`)

Input: a sequence of `(key: UTF-8 string, value: signed 64-bit integer)` pairs.

Steps:

1. **Deduplication** — insert all pairs into a key-indexed map; for duplicate keys,
   the last occurrence wins (preserves insertion order, last value overrides earlier).

2. **Lexicographic sort** — sort deduplicated entries by key bytes ascending (UTF-8
   byte comparison, no locale, no unicode normalization).

3. **Concatenation** — for each `(key, value)` in sorted order:
   `uint16-BE(byte_length(key)) || utf8_bytes(key) || int64-BE(value)`

No outer length prefix or separator between signal encodings. The result is the signal
payload. The uint32-BE prefix in section 3.1 wraps the entire payload.

---

## 4. CT-0 Evaluation

### 4.1 Verdict

Given an `auth_commit` and a `replay_commit` (each 32 bytes):

```
if auth_commit == replay_commit:
    status = "OK"
else:
    status = "FAIL"
```

### 4.2 Certificate

The certificate hash is:
```
SHA256(auth_commit || replay_commit || utf8_bytes(status) || utf8_bytes(run_id))
```

No length prefixes. No separators. Field order is exact.

---

## 5. Domain Separators

All multi-purpose SHA256 computations use a domain prefix terminated by a null byte.
No two computations share a prefix.

| Computation             | Prefix                      |
|-------------------------|-----------------------------|
| Schema Lock combined    | `SCHEMA_LOCK_V1\x00`        |
| Per-vector golden root  | `GOLDEN_VECTOR_V1\x00`      |
| Global golden root      | `GOLDEN_LOCK_V1\x00`        |
| State canonical commit  | `DSVM0:STATE:v1\x00`        |
| Sequence commit         | `DSVM0:SEQ:v1\x00`          |

---

## 6. GoldenRoot Composition

```
per_vector_root(id, commit) =
    SHA256("GOLDEN_VECTOR_V1\x00" || utf8_bytes(id) || commit)

global_root(spec_hash, per_roots_sorted_by_id) =
    SHA256("GOLDEN_LOCK_V1\x00" || spec_hash || per_root[0] || per_root[1] || ...)
```

`spec_hash` is `SHA256(raw_bytes_of_this_file)` — computed over the exact stored bytes
with no line-ending normalization, no trailing whitespace removal, no BOM stripping.

---

## 7. Conformance Requirements

A conformant implementation MUST:

1. Use the field order specified in section 2 exactly.
2. Use big-endian byte order for all integer encodings.
3. Apply signal deduplication before sorting (last-value-wins).
4. Sort signals by UTF-8 byte value (not Unicode codepoint order — identical for ASCII).
5. Compute SHA256 over the concatenated canonical bytes, not over any intermediate
   representation.
6. Produce the same RI-0 commit as all other conformant implementations given identical
   inputs.

A conformant implementation MUST NOT:

- Normalize line endings in any input field.
- Reorder struct fields.
- Omit zero-length fields (a zero-length prev_state_bytes produces `\x00\x00\x00\x00`).
- Use a JSON or text serialization layer in the hash computation path.

---

*This document is hashed at compile time and its digest is included in every GoldenRoot.*
*Amending this document without updating the baseline constitutes a CI violation.*
