# Simulation OS Kernel Reference v0.5

**Status:** Draft Canonical Reference

**Purpose:** Consolidate terminology from CTT-304 and REPLAY-Φ into a single vocabulary reference without introducing new semantics.

---

## Core Terms

### RI-0 (Replay Instance Zero)

RI-0 is the canonical replay execution context.

**Responsibilities:**

- Accept an Input Trace.
- Execute deterministic replay.
- Produce a Replay Result.
- Emit replay metadata required for verification.

RI-0 does not issue verdicts. RI-0 is responsible only for replay execution.

---

### CT-0 (Certification Tier Zero)

CT-0 is the canonical verdict authority.

**Responsibilities:**

- Consume Replay Results from RI-0.
- Evaluate replay outcomes against defined criteria.
- Produce a Verdict.
- Produce a Certificate.

CT-0 does not modify replay state. CT-0 evaluates replay outputs.

---

## Evidence Chain

Every verification flow SHALL follow:

```
Input Trace
→ Replay (RI-0)
→ Verdict (CT-0)
→ Certificate
```

Outputs from each stage SHALL be preserved as evidence artifacts.

---

## Bit-Perfect Federation

Bit-Perfect Federation is the requirement that equivalent inputs produce equivalent outputs across participating federation members.

A federation is bit-perfect when:

- Input traces are identical.
- Replay execution is deterministic.
- Replay outputs are identical.
- Verdicts are identical.
- Certificates are identical.

Any divergence constitutes federation failure.

---

## Fail-Closed Behavior

The system SHALL fail closed.

If replay validity cannot be established:

- No certificate SHALL be issued.
- No successful verdict SHALL be issued.

Missing evidence SHALL be treated as insufficient proof.

---

## Canonical Reference Test

A document passes the Canonical Reference Test when:

- RI-0 terminology is used consistently.
- CT-0 terminology is used consistently.
- Replay terminology is consistent.
- No conflicting vocabulary exists.

---

## Evidence Gate

The minimum operational proof artifact consists of:

1. Input Trace Identifier
2. RI-0 Replay Result
3. CT-0 Verdict
4. Certificate Identifier or Hash

The Evidence Gate is considered satisfied only when all four artifacts exist and can be traced through the evidence chain.

---

## Sources

- CTT-304
- REPLAY-Φ
