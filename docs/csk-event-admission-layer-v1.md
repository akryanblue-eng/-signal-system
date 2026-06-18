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
existing reconstructed truth?" against the replayable `LedgerState` (plus
the quarantine store, read-only, for `event.disambiguated`).

Outcome lattice (v1.1 — non-overlapping):

| Result | Meaning |
|---|---|
| `VALID` | single coherent interpretation; no competing claims |
| `CONTRADICTION` | a committed truth is violated, deterministically and unambiguously (exactly one rule is broken) |
| `AMBIGUOUS` | the event is well-formed and single-topic, but history admits more than one valid candidate it could attach to, and no anchor disambiguates |
| `INSUFFICIENT_CONTEXT` | the event cannot be evaluated at all: a required anchor is missing/unresolvable and there is no history to fall back on |

`AMBIGUOUS` is *history-dependent* ambiguity (multiple valid predecessor/
target candidates already in the ledger), not schema incompleteness — that
distinction is what `INSUFFICIENT_CONTEXT` captures. Two events allow loops
or decisions to accumulate multiple live candidates on the same topic
(`loop.opened` is always `VALID`, even with other loops already open on that
topic; `decision.made` history retains every prior decision per topic, not
just the active one), which is exactly what makes the corresponding closing/
superseding event ambiguous when no anchor is given.

| Event type | VALID | CONTRADICTION | AMBIGUOUS | INSUFFICIENT_CONTEXT |
|---|---|---|---|---|
| `decision.made` | first decision for topic, or explicit `supersedes` of the active decision | a different active decision already exists for the topic | — | — |
| `decision.superseded` | explicit `supersedes` cleanly resolves an active decision, or exactly one historical candidate exists with no anchor | target is inactive, or topic mismatch, or the sole implicit candidate is inactive | 2+ historical decisions on the topic and no `supersedes` anchor | no decision history for the topic at all, or `supersedes` references an unknown decision |
| `loop.opened` | always | — | — | — |
| `loop.closed` | explicit `loop_id` cleanly closes an open loop, or exactly one open loop exists with no anchor | anchor loop wrong topic, already closed, or no open loops exist at all with no anchor | 2+ open loops on the topic and no `loop_id` anchor | `loop_id` references an unknown loop |
| `event.disambiguated` | named anchor resolves the target's witness contract to `VALID` | named anchor does not resolve the ambiguity, or topic mismatch | — | `target_event_id`/`chosen_anchor_id` missing, target not in quarantine, or target's event type has no `ANCHOR_FIELD` entry |

### `event.disambiguated` — the only sanctioned path out of AMBIGUOUS

CSK never infers a disambiguating anchor on its own. An `AMBIGUOUS` event is
quarantined exactly like `INSUFFICIENT_CONTEXT` — it cannot enter replay
truth implicitly. The only way out is an explicit event:

```json
{"v": 1, "id": "...", "type": "event.disambiguated", "ts": "...",
 "payload": {"topic": "...", "target_event_id": "<quarantined event id>",
             "chosen_anchor_id": "<the id it resolves to>"}}
```

`witness_event_disambiguated` synthesizes a copy of the quarantined target
with the chosen anchor baked into its `ANCHOR_FIELD` (`supersedes` for
`decision.superseded`, `loop_id` for `loop.closed`) and re-runs that event
type's own witness contract on the synthesized copy. If the inner result is
`VALID`, the disambiguation itself is `VALID`; any other inner result makes
the disambiguation a `CONTRADICTION` ("chosen anchor does not resolve
ambiguity") and the target remains quarantined.

On commit, `Ledger._promote_disambiguated` pulls the target out of
quarantine, applies the resolved copy's mutation, and appends *that resolved
copy* to the committed log alongside the `event.disambiguated` event itself
— both are auditable, but only the resolved copy carries the state change.

**Out of scope for v1.1:** forked-history ambiguity, where two *already
committed* decisions could each be read as the "active" interpretation of a
topic after an unresolved contradiction (e.g. two `decision.made` events
both claiming validity because the first contradiction was never
disambiguated). Handling that case would require relaxing the "exactly one
active decision per topic" invariant into "a set of live candidate
interpretations," which is a larger state-model change than this pass
makes. The current model only detects ambiguity prospectively (multiple
*open* loops, multiple *historical* decisions to supersede), not
retroactively from committed contradictions.

### Stage 3 — Ledger Commit Strategy

| Witness result | Action |
|---|---|
| `VALID` | commit, apply state mutation |
| `CONTRADICTION` | commit (materialize the conflict in history), no mutation, emit `drift.detected` |
| `AMBIGUOUS` | quarantine, held for resolution via `event.disambiguated` |
| `INSUFFICIENT_CONTEXT` | quarantine |

CSK never hides contradictions — it commits them to the ledger and emits an
explicit `DriftEvent` rather than silently overwriting canonical state.
CSK never resolves ambiguity implicitly either — an `AMBIGUOUS` event sits in
quarantine until an explicit `event.disambiguated` event names which
candidate it resolves to. Quarantined events are stored separately and never
affect replay state.

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

`event.disambiguated` entries are skipped during replay: they are
administrative audit trail, and their effect on state is already captured
by the resolved copy of the originally-quarantined event that
`Ledger._promote_disambiguated` appends to the committed log at the time
the disambiguation was processed.

---

## Witness DSL (`csk_admission/anchor_rules.py`)

`witness_loop_closed` and `witness_decision_superseded` — the only two
event types that can ever be quarantined as `AMBIGUOUS` — turned out to be
the same shape: resolve via an explicit anchor if one is given (anchor
unknown → `INSUFFICIENT_CONTEXT`; wrong topic or invalid target →
`CONTRADICTION`; else `VALID`), or fall back to history if and only if
exactly one viable candidate exists there (zero candidates → a
per-type-declared result; 2+ → `AMBIGUOUS`; exactly one → `VALID` unless
that candidate itself fails the validity check).

`AnchorRule` makes that shape a declared value instead of two
near-duplicate hand-written functions: `anchor_field`, how to look up a
candidate by id, how to list candidates for a topic, what makes a
candidate a *valid* repair target, and what zero candidates means for that
event type (`CONTRADICTION` for `loop.closed` — "no open loops" is itself a
violation; `INSUFFICIENT_CONTEXT` for `decision.superseded` — no history at
all is a schema-level gap, not a violation). `evaluate_anchor_rule` is the
one generic interpreter; `witness_loop_closed`/`witness_decision_superseded`
are now one-line calls into it, and `divergence.find_hotspots` reuses the
same rules for candidate enumeration instead of re-deriving "how to list
candidates for this event type" a second time.

This is deliberately *not* a textual/parsed grammar — there are exactly two
instances of this shape today, and a string format with no second consumer
would be speculative generality rather than a DSL doing real work. The
extraction changed zero behavior: `test_witness_contracts.py` and
`test_disambiguation.py` pass unmodified against it.

---

## Replay Divergence Engine (`csk_admission/divergence.py`)

A diagnostic, read-only static analysis over the quarantine store and
`LedgerState` — it is not part of admission, witness evaluation, commit, or
replay, and never mutates the ledger.

CSK never forks ledger state: an `AMBIGUOUS` event is held in quarantine,
never branched into multiple parallel interpretations (forked-history
ambiguity / Case C is explicitly out of scope — see above). So there is no
combinatorial set of possible ledger states to enumerate. The real
divergence surface in this model is per-event: `analyze(ledger)` re-evaluates
every quarantined event, keeps the ones currently classified `AMBIGUOUS`,
and for each one (an `AmbiguityHotspot`) enumerates the anchor candidates
already visible in history and classifies what witness result choosing each
one would actually produce — by reusing the same anchor-injection +
witness-contract mechanism `event.disambiguated` itself uses, not a new
resolution primitive. `hotspot.collapse_anchors` is the subset of candidates
that would resolve to `VALID`; `report.collapse_paths` maps each hotspot's
event id to that subset. A candidate that exists in history but would
itself resolve to `CONTRADICTION` (e.g. an inactive decision) is reported
but excluded from `collapse_anchors` — see
`csk_admission/tests/test_divergence.py`.
