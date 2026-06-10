# Heat & Surveillance System
*(Drill RAQ – Chiraq Sandbox)*

## Overview

The Heat & Surveillance System governs law enforcement pressure, witness behavior, camera detection, gunshot response, and block-level escalation across the Chiraq sandbox.
It is the central regulatory system that ties together:

- Territorial Influence
- AI Behavior
- Economy
- Weapons
- Missions
- Player Progression

Heat is deterministic, block-scoped, and time-decaying, ensuring predictable simulation behavior and reproducible debugging.

---

## 1. Heat Model

### 1.1 Block-Scoped Heat

Each block maintains its own `heatLevel`:

```
heatLevel ∈ [0.0, 1.0]
```

Heat is local, not global.

### 1.2 Heat Sources

Heat increases from:

- Gunfire
- Violent crimes
- Witness calls
- Camera detection
- Police presence
- Retaliation events
- High-profile player actions

### 1.3 Heat Decay

Heat decays over time:

```
heatLevel = max(0, heatLevel - decayRate * Δt)
```

Decay is slower in:

- High-density civilian blocks
- Surveillance-heavy blocks
- Recently contested blocks

---

## 2. Surveillance Zones

### 2.1 Camera Nodes

Placed in:

- Storefronts
- Transit areas
- Market Strip
- Alley entrances

Cameras detect:

- Weapons drawn
- Fights
- Shootings
- Player presence during crimes

### 2.2 Witness System

Civilians act as dynamic surveillance nodes.

Witnesses:

- Observe crimes
- Panic
- Call police
- Record the player
- Increase heat

Witness reliability varies by:

- Time of day
- Block type
- Player reputation

### 2.3 Police Patrol Visibility

Police vehicles and foot patrols create temporary surveillance zones that:

- Increase heat sensitivity
- Reduce decay rate
- Increase witness call speed

---

## 3. Heat Tiers

Heat is divided into deterministic tiers.

### Tier 0 — Calm

- Normal civilian density
- Low police presence
- High economic output

### Tier 1 — Alert

- Civilians more reactive
- Police patrol frequency increases
- Rival factions more confrontational

### Tier 2 — Active

- Police respond to gunshots
- Witness calls are faster
- Faction AI increases patrol density

### Tier 3 — Lockdown

- Police containment per block
- Tactical units deployed
- Stash nodes at risk
- Corners shut down

### Tier 4 — Citywide Pressure

- Helicopter spotlight
- Roadblocks
- Multi-block police sweeps
- Severe economic penalties

---

## 4. Police Response Logic

### 4.1 Detection Pipeline

1. Event occurs
2. Witness or camera detects
3. Call is generated
4. Dispatcher assigns units
5. Units route to block

### 4.2 Response Types

- Patrol car
- Foot chase
- Tactical van
- Helicopter
- Containment perimeter

### 4.3 Deterministic Response Time

Response time is a function of:

```
responseTime = baseTime * (1 - heatLevel) * (1 - cameraDensity) * (1 - witnessDensity)
```

---

## 5. Player Interaction With Heat

### 5.1 Heat-Raising Actions

- Shooting
- Brandishing weapons
- Fighting
- Robbing stores
- Tagging walls in high-surveillance zones
- Driving recklessly in police presence

### 5.2 Heat-Lowering Actions

- Laying low indoors
- Changing outfits
- Using back alleys
- Bribing store owners
- Completing missions that reduce heat

### 5.3 Reputation Interaction

High reputation:

- Reduces witness call likelihood
- Increases intimidation radius
- Increases police suspicion

---

## 6. Block-Level Heat Effects

### 6.1 Civilian Behavior

High heat:

- Reduces foot traffic
- Increases panic
- Increases witness calls
- Reduces corner revenue

### 6.2 Faction Behavior

High heat:

- Increases patrol density
- Increases backup frequency
- Reduces stash node safety

### 6.3 Economy

High heat:

- Reduces storefront cooperation
- Reduces laundering efficiency
- Increases upkeep costs

---

## 7. Heat & Missions

Heat dynamically modifies missions:

- High heat → harder missions
- Low heat → stealth missions possible
- Heat spikes → retaliation missions
- Heat decay → recovery missions

Mission difficulty is system-driven, not scripted.

---

## 8. Determinism Requirements

- Heat updates must be deterministic per tick
- Witness detection must follow fixed probability curves
- Camera detection must follow strict line-of-sight rules
- Police response times must follow defined formulas
- Heat decay must be reproducible across runs

---

*End of Section*
