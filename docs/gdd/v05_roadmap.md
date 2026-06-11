# v0.5 Implementation Roadmap
*(Drill RAQ – Chiraq Sandbox)*

**Target:** Playable vertical slice — one micro-area, one mission chain, one escalation loop  
**Structure:** Phase 0 → Sprint 1 → Sprint 2 → Sprint 3  
**Sequencing authority:** `master_index.md` (dependency DAG)

---

## Phase 0: Pre-Alpha Architecture
**Timebox: 1–3 days**  
**Purpose:** Lock execution rules so every later system is deterministic, debuggable, and composable. Not schema-first — only the minimum to prevent Sprint 2/3 from forcing breaking changes.

### Deliverables

#### 0.1 Vertical Slice Contract (1 page)
A single written agreement on what "v0.5 done" means:

- The one gameplay loop that must work end-to-end
- Success criteria (observable, not subjective)
- Explicit out-of-scope list
- The single mission chain that proves the slice

This document gates Sprint 1. No sprint begins without it signed off.

#### 0.2 Tick + Event Model (spec + stub code)

**Time model:**
- `SimTick` — fixed cadence (default: 2s real-time equivalent), owns all simulation state updates (influence decay, heat decay, AI state transitions, economy ticks)
- `UnityUpdate` — per-frame, owns rendering, input, animation, UI only
- Rule: no simulation state may be written from `UnityUpdate`; reads are allowed

**Event ordering rule:**
- Events emitted during tick `T` are processed at the start of tick `T+1`
- No event is processed in the same tick it is emitted
- Event queue is a stable FIFO per tick — no priority reordering

**Stub interface:**
```csharp
public interface ISimSystem
{
    void OnSimTick(int tickIndex, float deltaTime);
}

public interface IEventListener
{
    void OnEvent(SimEvent evt);
}

public class SimEvent
{
    public int tickIndex;
    public string eventType;
    public string sourceId;
    public string targetId;
    public float value;
}
```

#### 0.3 Module Boundaries

Eight modules aligned to the dependency DAG. Each module owns its state. No module reads another module's internal state — communication is events only.

| Module | Owns | Emits | Consumes |
|--------|------|-------|----------|
| `WorldGraph` | Block topology, claimable nodes, nav layers | *(none — static)* | *(none)* |
| `Territory` | `BlockInfluenceState` per block | `OwnerChanged`, `BlockContested` | `EventLogged` |
| `Heat` | `HeatState` per block | `HeatTierChanged`, `PoliceDispatched` | `WeaponFired`, `CrimeCommitted` |
| `AI` | `AIAgentState` per agent | `AIStateChanged`, `BackupCalled` | `HeatTierChanged`, `OwnerChanged` |
| `Economy` | `EconomyState` per block | `RevenueCollected`, `StashRaided` | `HeatTierChanged`, `OwnerChanged` |
| `Combat` | `CombatState` (player) | `PlayerFired`, `PlayerKilled` | `AIStateChanged`, `HeatTierChanged` |
| `Missions` | `MissionState` per active mission | `MissionGenerated`, `MissionCompleted` | all systems |
| `Progression` | `PlayerProgressionState` | `ReputationChanged`, `SkillUnlocked` | all systems (terminal) |

#### 0.4 Telemetry / Ledger Hook Decision

**What is logged:**
- Every `SimEvent` with `tickIndex` as primary key
- Key state hashes at each tick: `influenceHash`, `heatHash`, `aiHash`
- Mission state transitions
- Player state deltas

**Where logs live (v0.5):**
- In-memory ring buffer (last 1000 ticks) during play
- Flushed to `StreamingAssets/logs/session_<timestamp>.json` on session end
- No database, no external service — local JSON only for v0.5

**Log entry schema:**
```json
{
  "tick": 42,
  "timestamp": 84.0,
  "eventType": "HeatTierChanged",
  "sourceId": "block_d",
  "value": 2.0,
  "stateHash": "a3f9..."
}
```

#### 0.5 Data Loading Policy

**Config files live in:** `Assets/StreamingAssets/data/`  
**Loaded by:** `WorldGraph` module at startup, before first `SimTick`  
**Files:**
- `blocks.json` — block definitions, neighbour refs, sub-zones, claimable nodes
- `factions.json` — faction definitions with aggression profiles
- `heatzone_config.json` — per-block camera node and witness density config

**ID validation rule:** Any reference to a `blockId` or `factionId` that does not exist in the loaded data causes an immediate `Debug.LogError` and halts initialization. No silent fallbacks.

**Missing reference behavior:** Hard fail at load time, not at runtime. This surfaces data errors in Phase 0, not during Sprint 3 playtesting.

### Phase 0 Exit Criterion

A blank Unity project can:
1. Load `blocks.json` and `factions.json` without errors
2. Run a `SimTick` loop for N ticks (default: 300) with no gameplay
3. Emit a `session_<timestamp>.json` log with one entry per tick
4. Produce identical logs on two runs with the same seed

**Gate:** Phase 0 is not complete until the seed-reproducibility test passes. Sprint 1 does not start until this gate is cleared.

---

## Sprint 1: Foundation — Engine Scaffolding
**Against Phase 0 contracts, not exploratory**

### Deliverables

1. **Unity project setup**
   - Folder structure matching module boundaries (`Scripts/Territory/`, `Scripts/Heat/`, etc.)
   - `SimTick` manager with configurable cadence
   - Event bus (`SimEventBus`) with FIFO queue and tick-deferred dispatch

2. **Data loading**
   - `WorldGraph` loader reads `blocks.json` and `factions.json`
   - ID validation on load (hard fail on missing refs)
   - Block graph accessible as `Dictionary<string, Block>`

3. **Territory module stub**
   - `BlockInfluenceState` initialized per block (all factions at 0)
   - Decay applied each `SimTick`
   - `OwnerChanged` event emitted when ownership crosses threshold

4. **Debug visualization**
   - Scene view: block bounds drawn as colored quads (faction color / grey / yellow for contested)
   - Inspector window showing `BlockInfluenceState` per selected block
   - Console log of each `SimEvent` with tick index

### Sprint 1 Exit Criterion

- Block graph loads from JSON, all 5 named blocks visible in scene
- `SimTick` loop runs at configurable rate
- Influence decays on each tick; `OwnerChanged` event fires and appears in console log
- Session log written to `StreamingAssets/logs/` on Play stop
- Seed-reproducibility holds: two runs with same seed produce identical logs

---

## Sprint 2: Core Loop — Escalation / Adaptation / Resolution

Implement the smallest playable loop: player action → heat spike → AI escalation → player adaptation → resolution.

### Deliverables

1. **Heat module**
   - `HeatState` per block, tier transitions (Calm → Alert → Active → Lockdown → Citywide)
   - Decay per tick; `HeatTierChanged` event
   - `WeaponFired` event raises heat; witness density affects raise rate

2. **AI module**
   - Base state machine: Idle → Patrol → Observe → Confront → Combat → Flee → Recover
   - Patrol generation from influence values (spawn AI in owned/high-influence blocks)
   - `HeatTierChanged` listener: raise aggression level on tier increase
   - `BackupCalled` event triggers reinforcement spawn

3. **Minimal combat resolution**
   - Player can fire weapon → emits `WeaponFired(blockId, weaponClass)`
   - AI enters Combat state on player proximity + heat threshold
   - Hit detection: body zone hit → `PlayerFired` event with zone
   - Death condition: `PlayerKilled` or `AIKilled` events
   - No animation polish — functional state transitions only

4. **Economy tick (minimal)**
   - Corner revenue tick per owned block
   - `HeatTierChanged` applies revenue penalty
   - Revenue logged to session log

### Sprint 2 Exit Criterion

- Player can walk into a block, fire a weapon, watch heat tier rise, see AI aggression increase
- AI calls backup; second AI spawns in block
- Player can kill AI; `AIKilled` event logged
- Corner revenue tick runs; penalty applies at Tier 2+
- Full session log captures the escalation chain from `WeaponFired` to `AIKilled` with tick indices

---

## Sprint 3: Vertical Slice — Environment + Proof

One Chicago micro-area, one mission chain, progression delta, telemetry proves the run.

### Deliverables

1. **Environment**
   - One playable micro-area: Block A (Stony Front) + Block B (The Cut) + Block D (Market Strip)
   - Art-blocked geometry (greybox): apartments, porches, gangways, alley, storefronts
   - Claimable nodes placed and linked to `WorldGraph`
   - NavMesh baked across street, alley, and gangway layers

2. **One mission chain**
   - Mission type: Territory (Hold the Block)
   - Trigger: Block A influence drops below contested threshold
   - Objectives: claim 2 porch nodes + survive for N ticks
   - Failure: Heat Tier 4 reached OR block ownership lost to rival
   - Reward: influence boost + reputation delta

3. **Progression delta**
   - `ReputationChanged` fires on mission complete/fail
   - Street Rep visible in HUD
   - One skill unlock threshold reachable in single session

4. **Telemetry proof**
   - Session log captures full mission lifecycle: `MissionGenerated` → objectives → `MissionCompleted` or `MissionFailed`
   - Log is replay-verifiable: second run with same seed + same input sequence produces identical outcome
   - One human-readable summary printed to console at session end: blocks owned, heat peaks, missions completed, reputation delta

### Sprint 3 Exit Criterion — "v0.5 Done"

The vertical slice contract from Phase 0 is satisfied:
- [ ] Player can enter a contested block, claim nodes, hold it, and complete a territory mission
- [ ] Heat escalates from player actions and affects AI behavior visibly
- [ ] Mission success/failure is deterministic given the same world state
- [ ] Session log is produced and replay-verifiable with same seed
- [ ] No system forces a breaking change to another system's data contract

---

## Summary

| Phase | Timebox | Gate |
|-------|---------|------|
| Phase 0: Pre-Alpha Architecture | 1–3 days | Seed-reproducible sim loop + session log |
| Sprint 1: Foundation | 1–2 weeks | Block graph loads, influence decays, events log |
| Sprint 2: Core Loop | 2–3 weeks | Full E/A/R chain: fire → heat → AI → combat |
| Sprint 3: Vertical Slice | 2–3 weeks | One mission, one area, telemetry proves the run |

---

*End of Document*
