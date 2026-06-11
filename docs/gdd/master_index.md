# GDD Master Index
*(Drill RAQ – Chiraq Sandbox)*

**Document Status:** Draft v0.1  
**Scope:** v1 Core Systems (9 sections)  
**Purpose:** Dependency DAG, canonical data contracts, implementation order, determinism hooks

This document is the single source of truth for system relationships. Any new GDD section, engine file, or data schema must reference this index to establish where it sits in the dependency graph before implementation begins.

---

## 1. Dependency Map

The graph flows from foundational data (topology, simulation rules) upward through consumers. A system listed under "Upstream Inputs" must be stable before its downstream consumers can be implemented.

| System | Upstream Inputs | Downstream Consumers |
|--------|----------------|---------------------|
| **World Map Block Layout** | *(none — root node)* | Territorial Influence, AI Behavior, Economy, Heat, Missions, Combat |
| **Territorial Influence** | World Map Block Layout | AI Behavior, Economy, Heat, Missions, Player Progression |
| **Heat & Surveillance** | World Map, Territorial Influence, Weapons, AI Behavior | Economy, Missions, Combat, Player Progression |
| **AI Behavior** | World Map, Territorial Influence, Heat | Missions, Combat, Player Progression |
| **Economy** | World Map, Territorial Influence, Heat, AI Behavior | Missions, Player Progression |
| **Weapons** | *(combat physics only — low coupling)* | Combat, AI Behavior, Heat, Missions |
| **Combat** | Weapons, AI Behavior, Heat, World Map | Player Progression, Missions |
| **Mission System** | All systems above | Player Progression |
| **Player Progression** | All systems above | *(terminal node — no downstream system consumers)* |

### 1.1 Dependency DAG (Text Representation)

```
World Map Block Layout
│
├──► Territorial Influence
│         │
│         ├──► AI Behavior ──────────────────────┐
│         │         │                             │
│         ├──► Economy ──────────────────────────┤
│         │         │                             │
│         └──► Heat & Surveillance ◄─── Weapons  │
│                   │                             │
│                   └──────────────────────────── ┤
│                                                  │
│                                    Combat ◄──────┘
│                                       │
└──────────────────────────────────────►│
                                        │
                                 Mission System
                                        │
                                        ▼
                              Player Progression
                              (terminal consumer)
```

---

## 2. Canonical Data Contracts

Each system exposes a defined state object and a set of events. No system reads another system's internal state directly — all cross-system communication goes through these contracts.

### 2.1 Block (World Map)

```
BlockId         string
worldBounds     Bounds
neighbours      string[]
subZones        SubZone[]
claimableNodes  ClaimableNode[]
navLayers       enum[]          // Street | Alley | Gangway
heatZoneConfig  HeatZoneConfig
```

**Events emitted:** none (static data)  
**Events consumed:** none

---

### 2.2 BlockInfluenceState (Territorial Influence)

```
blockId             string
influence           Map<FactionId, float>   // [0, 100]
owner               FactionId | null
contested           bool
heatLevel           float                   // [0, 1]
lastEventTimestamp  float
```

**Events emitted:**
- `OwnerChanged(blockId, previousOwner, newOwner)`
- `BlockContested(blockId, factionA, factionB)`
- `InfluenceThresholdCrossed(blockId, factionId, direction)`

**Events consumed:**
- `EventLogged` (from any system that logs a block event)

---

### 2.3 HeatState (Heat & Surveillance)

```
blockId         string
heatLevel       float           // [0, 1]
heatTier        enum            // Calm | Alert | Active | Lockdown | CitywidePress
cameraNodes     CameraNode[]
witnessQueue    WitnessCall[]
policePresence  float           // [0, 1]
decayRate       float
```

**Events emitted:**
- `HeatTierChanged(blockId, previousTier, newTier)`
- `WitnessCallGenerated(blockId, witnessId)`
- `PoliceDispatched(blockId, responseType)`
- `CameraDetection(blockId, playerId)`

**Events consumed:**
- `WeaponFired(blockId, weaponClass, modded)`
- `CrimeCommitted(blockId, crimeType, severity)`
- `PlayerEntered(blockId)`

---

### 2.4 AIAgentState (AI Behavior)

```
agentId         string
factionId       string
blockId         string
currentState    enum    // Idle | Patrol | Observe | Confront | Flee | Backup | Combat | Search | Recover
targetId        string | null
patrolRoute     Waypoint[]
aggressionLevel float   // [0, 1]
weaponState     WeaponState
```

**Events emitted:**
- `AIStateChanged(agentId, previousState, newState)`
- `BackupCalled(agentId, blockId, factionId)`
- `CrimeWitnessed(agentId, blockId, crimeType)`
- `AIKilled(agentId, blockId, factionId)`

**Events consumed:**
- `HeatTierChanged` → adjusts aggression
- `BlockContested` → increases patrol density
- `OwnerChanged` → reroutes patrol assignments
- `RetaliationTriggered` → spawns retaliation units

---

### 2.5 EconomyState (Economy)

```
blockId             string
cornerRevenue       float
stashNodes          StashNode[]
storefrontStatus    Map<NodeId, CoopLevel>
launderingCapacity  float
taxRate             float
upkeepCost          float
```

**Events emitted:**
- `RevenueCollected(blockId, amount)`
- `StashRaided(blockId, nodeId)`
- `StorefrontShutdown(blockId, nodeId)`
- `LaunderingCompleted(amount, cleanAmount)`

**Events consumed:**
- `HeatTierChanged` → applies revenue penalty
- `OwnerChanged` → recalculates tax flow
- `PoliceDispatched` → triggers stash risk check
- `AIKilled` → affects crew upkeep

---

### 2.6 WeaponState (Weapons)

```
weaponId        string
class           enum        // Handgun | CompactSMG | FullSMG | Shotgun | Rifle
condition       enum        // Pristine | Used | Worn | BeatUp
mods            Mod[]
reliability     float       // [0, 1]
recoilProfile   RecoilCurve
jamState        JamType | null
ammo            int
```

**Events emitted:**
- `WeaponFired(blockId, weaponClass, modded, suppressorFitted)`
- `JamOccurred(weaponId, jamType)`
- `WeaponDrawn(blockId, weaponClass)`

**Events consumed:** none (weapons are owned by agents and players — no system-level consumption)

---

### 2.7 MissionState (Mission System)

```
missionId       string
category        enum    // Territory | Economy | HeatSurveillance | Retaliation | Music
blockId         string
primaryObjective    Objective
secondaryObjectives Objective[]
difficulty          float
flowState           enum    // Initializing | Active | Resolving | Cooldown
failureConditions   FailureCondition[]
rewardProfile       RewardProfile
```

**Events emitted:**
- `MissionGenerated(missionId, category, blockId)`
- `MissionCompleted(missionId, outcome)`
- `MissionFailed(missionId, failureReason)`
- `ObjectiveUpdated(missionId, objectiveId, progress)`

**Events consumed:**
- `HeatTierChanged` → rescales difficulty mid-mission
- `InfluenceThresholdCrossed` → triggers territory missions
- `StashRaided` → triggers stash recovery missions
- `RetaliationTriggered` → triggers retaliation missions

---

### 2.8 CombatState (Combat)

```
playerId        string
combatPhase     enum    // Idle | Ready | Aim | Fire | Reload | JamClear | Sprint
accuracy        float
recoilVector    Vector2
coverNode       CoverNode | null
lastHitZone     BodyZone | null
```

**Events emitted:**
- `PlayerFired(blockId, weaponClass, hitZone)`
- `PlayerTookCover(blockId, coverNodeId)`
- `PlayerKilled(blockId)`
- `PlayerEnteredCombat(blockId)`

**Events consumed:**
- `AIStateChanged` → updates threat assessment
- `HeatTierChanged` → adjusts police response timing
- `JamOccurred` → triggers jam-clear state

---

### 2.9 PlayerProgressionState (Player Progression)

```
playerId            string
streetRep           float
civicRep            float
policeRep           float
musicRep            float
crewRoster          CrewMember[]
unlockedSkills      SkillId[]
economicTier        enum    // Early | Mid | Late
territoryMilestones MilestoneId[]
```

**Events emitted:**
- `ReputationChanged(category, delta, newValue)`
- `SkillUnlocked(skillId, treeId)`
- `CrewMemberLost(crewMemberId)`
- `MilestoneReached(milestoneId)`

**Events consumed:** (all terminal — progression reads from all systems, emits nothing upstream)
- `MissionCompleted/Failed` → updates reputation + crew morale
- `OwnerChanged` → updates territory milestones
- `RevenueCollected` → updates economic tier
- `AIKilled` → checks crew roster

---

## 3. Implementation Order

Sequenced by the dependency DAG. Each layer must reach a stable, testable state before the next layer begins.

### Layer 0 — Data Substrate
1. `Block` struct + block graph JSON file (5 named blocks, neighbour references, sub-zones, claimable nodes)
2. `Faction` struct (3–5 factions with aggression profiles)
3. Static map scene in Unity with block bounds assigned

### Layer 1 — Simulation Core
4. `BlockInfluenceState` + `TerritoryManager` update loop (decay, event application, ownership logic, neighbour spread)
5. `HeatState` + `HeatManager` update loop (tier transitions, decay, camera/witness nodes)

### Layer 2 — Agent Systems
6. `WeaponState` + weapon classes, reliability system, recoil curves
7. `AIAgentState` + base state machine (Idle → Patrol → Observe → Confront → Combat → Flee)
8. AI patrol generation from influence values
9. AI backup and retaliation spawning

### Layer 3 — Player Systems
10. `CombatState` + player combat states, accuracy formula, cover system
11. Jam clear animations, recoil feedback, hit feedback

### Layer 4 — Economy Loop
12. `EconomyState` + corner revenue tick, stash nodes, heat penalty formula
13. Legitimate front businesses + laundering mechanics
14. Block tax flow + upkeep costs

### Layer 5 — Mission Layer
15. `MissionState` + trigger event pipeline
16. Mission selector weighted by world state
17. Objective builder using block graph + claimable nodes
18. Failure condition evaluation + cooldown

### Layer 6 — Progression Layer
19. `PlayerProgressionState` + reputation categories + delta formulas
20. Crew system + morale
21. Skill trees + unlock thresholds
22. Territory milestones

### Layer 7 — UI Layer
23. Minimap tint by faction color, contested pulse
24. HUD block label + heat indicator
25. Retaliation warning + crew status

---

## 4. Determinism & Replay Hooks

Every subsystem must satisfy two requirements:

1. **Determinism:** Given identical input state and identical event sequence, output is always identical.
2. **Observability:** Every state transition is logged with a tick-index key so any frame can be reconstructed.

| System | Determinism Requirement | Replay Hook |
|--------|------------------------|-------------|
| Territorial Influence | Fixed tick rate; event window is a deterministic queue | Log `OwnerChanged`, `BlockContested` with `tickIndex` |
| Heat & Surveillance | Decay formula uses fixed `Δt`; no random witness timing | Log `HeatTierChanged`, `WitnessCallGenerated` with `tickIndex` |
| AI Behavior | State transitions use fixed threshold comparisons | Log `AIStateChanged`, `BackupCalled` with `tickIndex` and `agentId` |
| Economy | Revenue formula is pure function of block state | Log `RevenueCollected`, `StashRaided` with `tickIndex` |
| Weapons | Jam uses seeded RNG per weapon instance | Log `JamOccurred`, `WeaponFired` with `tickIndex` and `weaponId` |
| Combat | Accuracy/recoil formulas are pure functions | Log `PlayerFired`, `PlayerTookCover` with `tickIndex` |
| Mission System | Selection algorithm uses deterministic weighted sort | Log `MissionGenerated`, `MissionCompleted` with `tickIndex` |
| Player Progression | Reputation deltas follow fixed formulas | Log `ReputationChanged`, `SkillUnlocked` with `tickIndex` |

### 4.1 Replay Protocol

To reconstruct world state at any tick `T`:

1. Load initial world state (block graph + faction config)
2. Replay the event log sequentially from tick `0` to tick `T`
3. All system states are derived — no stored snapshots required

This enables deterministic debugging, automated regression testing, and session replay.

---

## 5. Section File Index

| Section | File | Status |
|---------|------|--------|
| Territorial Influence & Retaliation | `docs/gdd/territorial_influence.md` | Complete |
| World Map Block Layout | `docs/gdd/world_map_block_layout.md` | Complete |
| AI Behavior | `docs/gdd/ai_behavior.md` | Complete |
| Economy System | `docs/gdd/economy_system.md` | Complete |
| Weapons System | `docs/gdd/weapons_system.md` | Complete |
| Heat & Surveillance | `docs/gdd/heat_surveillance_system.md` | Complete |
| Mission System | `docs/gdd/mission_system.md` | Complete |
| Combat System | `docs/gdd/combat_system.md` | Complete |
| Player Progression | `docs/gdd/player_progression_system.md` | Complete |
| **GDD Master Index** | `docs/gdd/master_index.md` | **This document** |

---

*End of Document*
