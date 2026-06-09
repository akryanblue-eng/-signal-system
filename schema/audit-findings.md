# Audio Events Schema Audit

**Date:** 2026-06-09  
**Branch:** `claude/audio-events-schema-audit-g77957`  
**Source branches:**
- `claude/latent-manifold-coordinate-mapping-Ewzi2` — TypeScript engine + types
- `claude/deterministic-event-sourced-machine-b75go` — Rust event algebra
- `claude/vdce-contract-ci-freeze-fd54xr` — VDCE contract / golden trace

---

## 1. Event Type Inventory

| Type | Layer | File | Timing Fields |
|------|-------|------|---------------|
| `AudioFeatures` | Input | `src/engine/AudioInputEngine.ts` | **none** |
| `MIDIEvent` (union) | Input | `src/engine/MIDIInputEngine.ts` | **none** |
| `MIDIState` | Input snapshot | `src/engine/MIDIInputEngine.ts` | **none** |
| `ChaosEvent` | Field | `src/engine/ChaosEngine.ts` | `durationMs` |
| `ActiveChaosEvent` | Field | `src/engine/ChaosEngine.ts` | `elapsedMs`, `durationMs` |
| `FlowMapping` | Field | `src/engine/SignalToFlowMapper.ts` | **none** |
| `FieldState` | Field | `src/engine/SteeringFieldEngine.ts` | **none** |
| `FieldFeedbackSignal` | Field feedback | `src/engine/FieldFeedback.ts` | `timingOffset` (ms) |
| `PerformerFeedback` | Kernel feedback | `src/engine/BidirectionalBrainLoop.ts` | `timingBias` **(seconds)** |
| `ManifoldState` | Physics | `src/core/manifold/ManifoldRuntime.ts` | **none** |
| `ManifoldForce` | Physics | `src/core/manifold/ManifoldRuntime.ts` | **none** |
| `RuntimeSnapshot` | Trace | `src/core/manifold/RuntimeSnapshot.ts` | `timestamp` (ms), `timingOffset` (ms) |
| `KernelOutput` | Kernel | `src/core/kernel/PerformanceKernel.ts` | **none** |
| `BrainLoopOutput` | Orchestration | `src/engine/BidirectionalBrainLoop.ts` | **none** |
| `BrainRuntimeOutput` | Orchestration | `src/engine/BidirectionalBrainRuntime.ts` | via `snapshot` |
| `LatentVector` | Types | `src/types/latent.ts` | **none** |
| `Rust Event` (enum) | Event algebra | `src/event.rs` | **none** |
| `CompiledState` | Event algebra | `src/event.rs` | **none** |

---

## 2. Timing Fields — Full Inventory

| Field | Type | Unit | Source | Range | Status |
|-------|------|------|--------|-------|--------|
| `RuntimeSnapshot.timestamp` | `number` | ms | `performance.now()` | [0, ∞) | ✅ ok |
| `RuntimeSnapshot.timingOffset` | `number` | ms | `energy*12 − drift*20` | ~[-20, 12] | ⚠️ ad hoc, unclamped |
| `ChaosEvent.durationMs` | `number` | ms | set at `fire()` | (0, ∞) | ✅ ok |
| `ActiveChaosEvent.elapsedMs` | `number` | ms | accumulated via `tick(dtMs)` | [0, durationMs) | ✅ ok |
| `FieldFeedbackSignal.timingOffset` | `number` | ms | same formula as RuntimeSnapshot | ~[-20, 12] | ⚠️ duplicated derivation |
| `PerformerFeedback.timingBias` | `number` | **seconds** | `stability > 0.7 ? -0.02 : 0.03` | {-0.02, 0.03} | ❌ unit mismatch + binary output |
| `ManifoldRuntime dt` (param) | `number` | seconds | `(t − lastTime) / 1000` capped at 0.05 | (0, 0.05] | ✅ ok (physics convention) |
| Rust `Event` (all variants) | — | — | — | — | ❌ no timing at all |

---

## 3. Findings

### F-01 · `centroid` is a copy of `energy`  
**Severity: High**  
`AudioInputEngine.update()` sets `centroid: totalSum / (count * 255)` — identical to `energy`. True spectral centroid is `Σ(i · v[i]) / Σ(v[i])`, a frequency-weighted mean. The field name creates a false contract with any consumer expecting spectral centroid for timbral mapping.

**Fix:** Replace with `centroid: energyWeightedBin / (totalSum + 1e-6)` where `energyWeightedBin = Σ i · v[i]`. Rename to `brightness` if a true centroid isn't needed, so the name matches the implementation.

---

### F-02 · `timingBias` (seconds) vs `timingOffset` (ms)  
**Severity: High**  
`PerformerFeedback.timingBias` is documented as `[-0.1, 0.1] seconds` and emits `{-0.02, 0.03}`. `FieldFeedbackSignal.timingOffset` and `RuntimeSnapshot.timingOffset` are in ms. Both fields represent "ahead/behind groove center." Any consumer adding these together silently multiplies one side by 1000.

**Fix:** Standardize on ms everywhere. Convert `timingBias` to ms at source: `-0.02 s → -20 ms`, `0.03 s → 30 ms`. Update JSDoc.

---

### F-03 · No timestamps on input events  
**Severity: High**  
`MIDIEvent`, `AudioFeatures`, `FlowMapping`, `ManifoldState`, `FieldState`, and `KernelOutput` carry no timestamp. The Web MIDI API provides `MIDIMessageEvent.timeStamp` (ms since page load, same epoch as `performance.now()`). Without it, causal ordering between MIDI events and field state is unrecoverable from the snapshot buffer alone.

**Fix:** Add `timestamp_ms: number` to `MIDIEvent` and `AudioFeatures`. Stamp at the raw message handler (before any processing), not at the consumer.

---

### F-04 · Rust event algebra has no timing or sequence fields  
**Severity: High**  
`Event`, `EntityRecord`, and `CompiledState` carry no timestamp, sequence number, or monotonic counter. The `event_chain_hash` (blake3 rolling hash) provides content integrity but cannot detect out-of-order delivery. A deterministic state machine needs either a sequence number on each event or a lamport clock to guarantee ordering invariants during replay.

**Fix:** Add `seq: u64` to `Event` enum variants (or as an envelope wrapper). Validate monotone increment in `ingress.rs`.

---

### F-05 · `ManifoldState.coherence` is derived and redundant  
**Severity: Medium**  
`coherence` is always `1 − |drift|` (recomputed in every call to `step()`). Storing it in the struct allows `state.coherence` to be set to an inconsistent value by any code that constructs a `ManifoldState` literal without calling `step()`. Tests and golden-trace fixtures currently have to maintain this invariant manually.

**Fix:** Remove `coherence` from the struct. Derive it wherever needed: `const coherence = 1 - Math.abs(state.drift)`. Update `RuntimeSnapshot.stability` to compute it inline.

---

### F-06 · `timingOffset` formula is ad hoc and unclamped  
**Severity: Medium**  
`energy * 12 - drift * 20` produces values from −20 to +12 ms with no documented derivation or groove-quantization alignment. The same formula is duplicated in both `computeFieldFeedback` and referenced in `RuntimeSnapshot`. If BPM or subdivison changes, this formula produces wrong values with no signal.

**Fix:** Make `timingOffset` a function of `bpm` and a subdivision constant, or clamp to `[-50, 50]` ms and document the mapping. Remove the duplication by computing it in one place and passing it into `RuntimeSnapshot`.

---

### F-07 · Dual attractor type shapes  
**Severity: Medium**  
`src/types/attractor.ts` defines `Attractor` with `center: Vec2`, `influenceRadius`, `strength`. `MidiAttractorController.ts` defines `LiveAttractor` with `x`, `y`, `strength`, `radius`, `type`, `decay`. `SignalToFlowMapper` produces `LiveAttractor[]`; nothing consumes `Attractor` directly. The static type exists only for canvas rendering.

**Fix:** Collapse to one type with `center: Vec2 | { x: number; y: number }` or convert `LiveAttractor → Attractor` at the renderer boundary. The two shapes should share a base interface.

---

### F-08 · Two independent rAF loops  
**Severity: Medium**  
Both `ManifoldRuntime` and `BidirectionalBrainRuntime` own their own `requestAnimationFrame` loop. If both are started (which happens in `BidirectionalBrainRuntime.start()`), the `ManifoldRuntime.step()` function inside `BidirectionalBrainRuntime.tickStep()` uses its *own* `lastTime` which may not align with the outer loop's `dt`. The physics are stepped twice per outer frame when the inner loop fires at a different phase.

**Fix:** `ManifoldRuntime`'s loop should be optional (start/stop as standalone only). `BidirectionalBrainRuntime` should call `step()` as a pure function, not start a second loop.

---

### F-09 · No cross-boundary codec between TS and Rust  
**Severity: Medium**  
The TypeScript layer emits `ManifoldState` / `RuntimeSnapshot`; the Rust layer expects `Event` (Create/Update/Merge/…). No shared IDL, protobuf, JSON schema, or codec function bridges them. The branches are architecturally decoupled with no defined serialization contract.

**Fix:** Define a `SignalFrame` wrapper (JSON Schema or protobuf) that maps `ManifoldState` fields to Rust `Update` events: e.g., `field=0 → drift`, `field=1 → energy`. Document the mapping in `schema/codec_contract.md` (or the existing `codec.rs` field discriminants). Add a round-trip integration test.

---

### F-10 · `SnapshotRecorder` window is not flushed  
**Severity: Low**  
300 frames at 60 fps = 5 seconds of history. There is no flush-to-storage mechanism. If the replay layer (`src/replay/`) needs to reconstruct a session, it has no persistent event log — just the last 5 seconds of snapshots. For post-session analysis or deterministic replay, this is insufficient.

**Fix:** Add an optional `onEvict(snapshot: RuntimeSnapshot): void` callback to `SnapshotRecorder`. The caller can stream evicted frames to IndexedDB, a WebSocket, or the Rust ingress endpoint.

---

## 4. Normalization Recommendations

### Unified timing contract

```typescript
// Proposed: stamp every event at the source boundary
interface TimestampedEnvelope<T> {
  payload:      T;
  timestamp_ms: number;   // performance.now() at point of capture
  seq:          number;   // monotone per-source counter
}

type TimestampedAudioFeatures = TimestampedEnvelope<AudioFeatures>;
type TimestampedMIDIEvent     = TimestampedEnvelope<MIDIEvent>;
```

### `timingOffset` normalization

```typescript
// Replace ad hoc formula with explicit parameter
function computeTimingOffset(
  state:  ManifoldState,
  bpm:    number,
  subdiv: number = 4,   // 16th notes at subdiv=4
): number {
  const beatMs    = 60_000 / bpm;
  const subdivMs  = beatMs / subdiv;
  const raw       = state.energy * subdivMs * 0.12 - state.drift * subdivMs * 0.20;
  return Math.max(-subdivMs / 2, Math.min(subdivMs / 2, raw));
}
```

### Rust sequence envelope

```rust
// Proposed wrapper — does not change Event discriminants
pub struct EventEnvelope {
    pub seq:        u64,
    pub timestamp:  u64,   // unix ms at ingestion
    pub event:      Event,
}
```

---

## 5. Files Changed

| File | Action |
|------|--------|
| `schema/audio_events.json` | Created — canonical event type catalog with sample events and timing inventory |
| `schema/audit-findings.md` | Created — this document |
