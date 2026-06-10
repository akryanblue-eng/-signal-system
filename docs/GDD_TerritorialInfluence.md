# GDD: Territorial Influence & Retaliation System
### Drill RAQ / Chiraq Sandbox

**Document Status:** Draft v0.1  
**Last Updated:** 2026-06-10  
**System Owner:** Design Lead

---

## 1. Overview

The Territorial Influence & Retaliation System governs how factions claim, contest, and lose control of city blocks in real time. Influence is not a binary flag—it is a continuous, multi-faction float that decays, spreads, and compounds based on in-world events. The player operates inside this living power map and every action they take (or fail to take) shifts the balance.

The system has three visible outputs the player can always read:
- **Minimap tint** — block color matches controlling faction
- **HUD block label** — who owns the block the player is standing in
- **Retaliation warning** — radio/text alert when a faction is hunting the player

---

## 2. Design Goals

| Goal | How It's Met |
|------|-------------|
| Territory feels earned, not static | Influence decays continuously; unchallenged blocks revert to neutral |
| Player actions have visible consequences | Every shooting, tagging, or robbery shifts influence immediately |
| AI behaves territorially, not randomly | Patrol density and aggression are derived from influence values |
| Escalation feels organic | Retaliation score accumulates and triggers separately from individual events |
| System is legible to the player | Three always-visible UI outputs; no hidden numbers |

---

## 3. Core Data Model

### 3.1 Faction

```
id              string        unique identifier
name            string        display name
color           Color         minimap/UI tint
aggressionProfile  enum      Low | Medium | High
```

`aggressionProfile` scales how fast a faction's retaliation score builds. A High faction retaliates at 1.5× the rate of a Low faction for the same provocation.

### 3.2 Block

```
id              string        unique identifier
worldBounds     Bounds        axis-aligned bounding box in world space
neighbours      string[]      adjacent block IDs (used for influence spread)
```

Blocks are the atomic unit of territory. A block boundary is a street edge—typically one city block in the literal sense.

### 3.3 BlockInfluenceState

```
blockId         string
influence       Map<factionId, float>   0–100 per faction, decays over time
owner           factionId | null        set when one faction clears ownership thresholds
contested       bool                    true when two+ factions both exceed contestThreshold
heatLevel       float                   0–100, raised by shootings and drive-bys
lastEventTimestamp  float
```

`owner` and `contested` are mutually exclusive. A block is either owned, contested, or neutral.

### 3.4 EventLogEntry

```
blockId         string
factionId       string        the faction performing the action
eventType       enum          Shooting | Driveby | Tagging | Robbery | PoliceRaid
severity        float         0.0–1.0 scalar applied to influence deltas
timestamp       float
```

Events are retained for a rolling 30-second window. The update loop replays all events in that window on each tick, so a burst of activity compounds naturally.

### 3.5 ClaimableNode

Micro-influence hotspots within a block. Capturing a node grants a one-time influence burst.

```
id              string
blockId         string        parent block
type            enum          WallTag | Porch | Store | ParkBench
factionId       string | null current claimant
lastClaimTimestamp  float
```

Claim values:

| Node Type  | Influence Granted |
|------------|------------------|
| WallTag    | 15               |
| Porch      | 20               |
| Store      | 25               |
| ParkBench  | 10               |

---

## 4. Influence Update Loop

The loop fires on a fixed tick (default: every 2 seconds). Order of operations is strict.

```
1. Decay all influence values
2. Apply events from the 30-second rolling window
3. Clamp all values to [0, 100]
4. Determine owner / contested status per block
5. Soft-spread influence to neighbours
6. Update AI patrol assignments
7. Tick retaliation scores
```

### 4.1 Decay

Each tick, every influence value is multiplied by `(1 − decayRate × Δt)`. Default `decayRate = 0.1`. A block with no activity will drop from 100 to near-zero in roughly 20 seconds of real time.

A block whose highest influence value falls below `ownerThreshold × 0.5` loses its owner assignment and becomes neutral.

### 4.2 Event Application

For each event in the rolling window:

- **Acting faction** gains `baseGain × severity`
- **All rival factions** lose `baseLoss × severity`
- **Heat level** increases by `severity × 0.5` for Shooting and Driveby events

| Event Type  | Base Gain | Base Loss |
|-------------|-----------|-----------|
| Shooting    | 20        | 10        |
| Driveby     | 15        | 8         |
| Robbery     | 12        | 6         |
| Tagging     | 10        | 5         |
| Police Raid | −5        | 3         |

Police Raids subtract from the acting faction and apply minor losses to rivals (disruption effect).

### 4.3 Ownership Thresholds

After clamping, each block is evaluated:

| Condition | Result |
|-----------|--------|
| Leader > `ownerThreshold` (50) AND lead margin > `marginThreshold` (20) | Block is owned by leader |
| Top two factions both > `contestThreshold` (30) | Block is contested |
| Otherwise | Block is neutral |

### 4.4 Neighbour Spread

After ownership is resolved, each block leaks `spreadFactor × influence[faction]` into each adjacent block. Default `spreadFactor = 0.05`. This means a strongly held block slowly pressures its neighbours—taking territory from one side creates a natural forward edge.

---

## 5. Retaliation System

Retaliation is a separate accumulator per faction, independent of block influence. It represents grudge pressure—the faction's collective motivation to hunt the player.

### 5.1 Accumulation

On any Shooting or Driveby event targeting a faction:

```
retaliationScore[faction] += severity × eventWeight × aggressionMultiplier
```

| Event Type | Weight |
|------------|--------|
| Shooting   | 1.5    |
| Driveby    | 1.2    |

| Aggression Profile | Multiplier |
|--------------------|-----------|
| Low                | 0.7       |
| Medium             | 1.0       |
| High               | 1.5       |

### 5.2 Decay

Each tick: `retaliationScore[faction] *= (1 − retaliationDecay × Δt)`. Default `retaliationDecay = 0.05`. A High faction that stops being provoked will cool off in roughly 40 seconds.

### 5.3 Trigger

When `retaliationScore[faction] > retaliationThreshold` (default: 60):

1. The faction picks a target block (player's frequent location, or highest rival-controlled block)
2. AI system spawns a drive-by car or ambush crew in that block
3. UI displays a retaliation warning: *"Word is, [Faction] looking for you around [Block]."*
4. Score resets to 0

Retaliation is not instant combat—it spawns a threat that the player must deal with or avoid. Multiple factions can have active retaliation simultaneously.

---

## 6. AI Patrol Behavior

AI patrol density is derived from influence values, not scripted zone assignments.

### 6.1 Patrol Assignment

Each tick, for every faction:
- Any block where `owner == faction.id` OR `influence[faction] > 25` is a patrol target
- If fewer than `desiredPatrolCountPerBlock` (default: 3) units are present, spawn or route one from a neighbour

### 6.2 Contested Block Behavior

In contested blocks, all factions present increase aggression level. This means:
- Higher confront chance on sight of rival
- Faster backup call
- Reduced retreat threshold

### 6.3 Retaliation Spawns

When a retaliation event fires, the AI system bypasses normal patrol logic and force-spawns a dedicated unit group (drive-by car or foot squad) in the target block. These units have a single objective: find the player.

---

## 7. UI Outputs

### 7.1 Minimap Tint

| Block State | Color |
|-------------|-------|
| Owned       | Faction color (from `faction.color`) |
| Contested   | Yellow (pulsing or striped) |
| Neutral     | Grey |

Tint updates every influence tick.

### 7.2 HUD Block Label

Always visible while the player is in the world:

```
You are in: [Block Name] — [Faction Name] turf
```

If contested: `— CONTESTED`  
If neutral: `— No Man's Land`

### 7.3 Retaliation Warning

Triggered by the retaliation system. Displays as in-world radio chatter audio + HUD text for ~5 seconds:

```
Word is, [Faction Name] looking for you around [Block Name].
```

---

## 8. Tunable Parameters

All values below are exposed in the Unity Inspector on `TerritoryManager`.

| Parameter | Default | Effect |
|-----------|---------|--------|
| `decayRate` | 0.1 | How fast influence fades without activity |
| `ownerThreshold` | 50 | Minimum influence to be eligible for ownership |
| `marginThreshold` | 20 | Lead required over second faction to confirm ownership |
| `contestThreshold` | 30 | Both factions must exceed this to mark contested |
| `spreadFactor` | 0.05 | Per-tick bleed into neighbour blocks |
| `patrolThreshold` | 25 | Minimum influence to warrant AI patrols |
| `retaliationThreshold` | 60 | Score that triggers a retaliation event |
| `retaliationDecay` | 0.05 | How fast grudge pressure fades |
| `eventRetentionSeconds` | 30 | Rolling window for event replay |

---

## 9. Out of Scope (v0.1)

- Police faction influence (tracked but not player-visible in this version)
- Block-level economy (drug corners, tax income) — separate system
- Faction alliances or truces
- Player-owned territory persistence across sessions

---

## 10. Implementation Reference

See `TerritoryManager.cs`, `AIPatrolSystem.cs`, and `TerritoryUI.cs` for the Unity C# implementation. Data structures are defined in `BlockInfluenceState.cs` and companion files.
