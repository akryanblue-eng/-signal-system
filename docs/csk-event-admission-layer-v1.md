# CSK Event Admission Layer + Witness Contract Pipeline (v1)

**Status:** Implemented (`csk_admission/`)

**Purpose:** Define the ingestion boundary for events entering the CSK ledger
under adversarial or ambiguous input, with deterministic replay guarantees.

---

## Core invariant

> At any point, `replay(events)` must produce a deterministic state
> independent of ingestion order, assuming identical admitted events.

Admission guarantees no malformed events, no ambiguous topic keys, and no
illegal state transitions enter the ledger. The witness layer guarantees
contradictions are made explicit rather than hidden.

---

## Pipeline

```
RAW INPUT
  -> 1. Event Admission Gate     (csk_admission/admission_gate.py)
  -> 2. Witness Contract Evaluation (csk_admission/witness_contracts.py)
  -> 3. Ledger Commit or Quarantine (csk_admission/ledger.py)
```

### Stage 1 — Event Admission Gate

Rejects malformed or non-replayable events before they can affect state.

- Structural validation: `EventEnvelope {v, id, type, ts, payload}` — all
  fields required, `v == 1`, `id` unique, `ts` ISO 8601 UTC, `payload` an
  object.
- Type registry validation against `csk_admission/registry.py`. Unknown
  types are rejected, never silently accepted — this is what prevents
  semantic drift injection.
- Topic extraction + normalization (`csk_admission/topics.py`). Topic
  resolution must be deterministic, non-null, and unambiguous; multi-topic
  payloads (`payload["topics"]`) are rejected in v1.

### Stage 2 — Witness Contract Evaluation

Witnesses do not judge truth. They answer: "does this event coexist with
existing reconstructed truth?" against the replayable `LedgerState`.

| Event type | VALID | CONTRADICTION | INSUFFICIENT_CONTEXT |
|---|---|---|---|
| `decision.made` | first decision for topic, or explicit `supersedes` of the active decision | a different active decision already exists for the topic | — |
| `decision.superseded` | `supersedes` references an active decision on the same topic | target is inactive, or topic mismatch | `supersedes` missing or references an unknown decision |
| `loop.opened` | loop not currently open | loop already open | `loop_id` missing |
| `loop.closed` | loop currently open | loop not open | `loop_id` missing |

`AMBIGUOUS` is part of the result type for defense-in-depth but is
unreachable in v1's pipeline: Stage 1 already rejects events whose topic
cannot be resolved unambiguously before they reach a witness contract.

### Stage 3 — Ledger Commit Strategy

| Witness result | Action |
|---|---|
| `VALID` | commit, apply state mutation |
| `CONTRADICTION` | commit (materialize the conflict in history), no mutation, emit `drift.detected` |
| `AMBIGUOUS` | quarantine |
| `INSUFFICIENT_CONTEXT` | quarantine |

CSK never hides contradictions — it commits them to the ledger and emits an
explicit `DriftEvent` rather than silently overwriting canonical state.
Quarantined events are stored separately and never affect replay state.

`EventAdmissionPipeline.persist()` writes the two stores to disk:

```
/ledger/events.jsonl
/quarantine/events.jsonl
```

---

## Witness chain

Every ingest result carries a `witness_chain`, e.g.:

```
["admission_gate:v1", "witness_contract:decision.made:v1", "ledger_commit:v1"]
```

This allows any committed or quarantined event to be audited backward to the
exact validation logic that processed it, not just the resulting data.

---

## Replay determinism

`csk_admission.ledger.replay(events)` rebuilds `LedgerState` from a set of
committed events by sorting them into canonical `(ts, id)` order before
re-running witness evaluation. This guarantees that two callers who ingest
the same events in different orders converge on the same final state once
they replay — see `csk_admission/tests/test_replay_determinism.py`.
