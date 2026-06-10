# Territorial Influence & Retaliation System
*(Drill RAQ – Chiraq Sandbox)*

## Overview

The Territorial Influence & Retaliation System simulates a living block-by-block ecosystem across a hyper-realistic Chicago environment.
Every block, gangway, porch, and corner store participates in a dynamic influence graph where factions gain or lose control based on player actions, AI behavior, and environmental events.

This system replaces static "turf" mechanics with a continuously evolving simulation that drives AI patrols, retaliation, mission hooks, and world tone.

---

## 1. Block Influence Grid

### 1.1 Block Definition

Each block is a discrete polygonal region with:

- Unique `BlockId`
- World bounds (AABB or polygon)
- Neighbor references
- Local claimable nodes (porches, stores, walls)

Blocks form a connected graph representing the playable Chiraq map.

### 1.2 Influence State

Each block tracks:

- Influence per faction
- Current owner (if any)
- Contested state
- Heat level (recent violence, police presence)
- Timestamp of last major event

Influence values shift over time based on events, decay, and neighbor propagation.

---

## 2. Influence Update Loop

Runs every 1–3 seconds.

### 2.1 Decay

Old influence gradually decays:

```
influence[f] *= (1 - decayRate * Δt)
```

### 2.2 Event Application

Recent events modify influence:

- Shootings, drive-bys, robberies → major shifts
- Tagging, intimidation, presence → minor shifts

Positive for acting faction, negative for rivals.

### 2.3 Ownership Logic

A faction becomes owner if:

- Its influence exceeds `ownerThreshold`
- It leads the next faction by `marginThreshold`

Blocks become contested when multiple factions exceed `contestThreshold`.

### 2.4 Influence Spread

Influence softly spreads to neighbors:

```
neighborInfluence[f] += spreadFactor * influence[f]
```

Creates organic territorial expansion.

---

## 3. Claimable Nodes

### 3.1 Node Types

- Wall tags
- Porches
- Corner stores
- Park benches
- Alley entrances

### 3.2 Node Mechanics

Claiming a node:

- Sets node's faction
- Boosts local block influence
- Slightly reduces rival influence
- Updates visual markers (graffiti, flags, decals)

Nodes anchor AI patrols and mission triggers.

---

## 4. AI Patrol System

### 4.1 Patrol Generation

For each faction:

- Identify blocks they own or heavily influence
- Maintain a target patrol count
- Spawn or route AI to maintain presence

### 4.2 Patrol Behavior

Patrols:

- Walk loops around claimable nodes
- Interact with civilians
- Confront rivals
- Respond to heat spikes

### 4.3 Contested Blocks

AI becomes:

- More aggressive
- More numerous
- More reactive to player presence

---

## 5. Retaliation System

### 5.1 Retaliation Score

Each faction tracks a retaliation score based on:

- Severity of attacks against them
- Location of incidents
- Their aggression profile

```
retaliationScore += severity * retaliationWeight
```

### 5.2 Retaliation Triggers

When score exceeds threshold:

- Drive-bys
- Ambushes
- Alleyway traps
- Coordinated foot chases

### 5.3 Decay

Retaliation naturally decays over time.

---

## 6. Heat System Integration

Heat increases from:

- Shootings
- Police presence
- Witnesses
- Surveillance cameras

Heat affects:

- Patrol density
- Police response
- Civilian behavior
- Mission difficulty

---

## 7. UI Integration

### 7.1 Mini-Map

- Blocks tinted by faction color
- Pulsing stripes for contested zones
- Icons for claimable nodes

### 7.2 On-Foot HUD

- Block name + faction turf indicator
- Danger indicator in rival turf
- Retaliation warning icon

### 7.3 World Markers

- Graffiti
- Flags
- Storefront decals
- Vehicle presence

---

## 8. Mission Hooks

The system provides hooks for:

- Territory defense missions
- Retaliation missions
- Tagging runs
- Ambush avoidance
- Police evasion
- Set expansion quests

Missions should be system-driven, not scripted.

---

## 9. Determinism Requirements

- Influence updates must be deterministic per tick
- AI patrol routing must be reproducible
- Retaliation triggers must follow strict thresholds
- Node claiming must be atomic
- Heat propagation must follow fixed rules

This ensures consistent debugging, replay, and simulation fidelity.

---

## 10. Future Extensions

- Player-led faction creation
- Multi-block turf wars
- Territory-based economy
- Dynamic civilian migration
- Weather-based influence modifiers

---

*End of Section*
