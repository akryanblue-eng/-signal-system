# Mission System
*(Drill RAQ – Chiraq Sandbox)*

## Overview

The Mission System provides dynamic, system-generated objectives that emerge from the state of the world rather than fixed scripts.
Missions are triggered by:

- Block influence changes
- Heat spikes
- AI retaliation
- Economic conditions
- Player reputation
- Weapon events
- Civilian/witness behavior

Every mission is deterministic, block-anchored, and state-driven, ensuring reproducibility and tight integration with the full simulation stack.

---

## 1. Mission Categories

### 1.1 Territory Missions

Triggered by:

- Contested blocks
- Influence shifts
- Rival patrol density
- Node takeovers

Types:

- **Hold the Block** — defend a block until influence stabilizes
- **Tag Run** — claim graffiti walls to push influence
- **Porch Defense** — protect a claimable node
- **Retake the Alley** — clear rivals from Block B (The Cut)

---

### 1.2 Economy Missions

Triggered by:

- Corner revenue thresholds
- Stash node risk
- Storefront cooperation
- Heat penalties

Types:

- **Collect Corners** — gather earnings before heat spikes
- **Stash Recovery** — retrieve goods before a raid
- **Storefront Diplomacy** — intimidate or bribe owners
- **Supply Run** — move goods between blocks under pressure

---

### 1.3 Heat & Surveillance Missions

Triggered by:

- Camera detection
- Witness calls
- Police sweeps
- High heat tiers

Types:

- **Lay Low** — reduce heat by avoiding detection
- **Camera Sweep** — disable or avoid surveillance nodes
- **Witness Hunt** — locate and intimidate key witnesses
- **Escape the Sweep** — evade multi-block police containment

---

### 1.4 Retaliation Missions

Triggered by:

- Faction retaliation score
- Player aggression
- Rival block dominance

Types:

- **Drive-By Response** — counter a rival attack
- **Ambush Setup** — lure rivals into a gangway trap
- **Block Sweep** — clear a rival-controlled block
- **Backup Call** — assist allied AI in a turf fight

---

### 1.5 Music Career Missions

Triggered by:

- Reputation milestones
- Studio ownership
- Local hype

Types:

- **Record Session** — produce a track under time pressure
- **Promo Run** — distribute mixtapes in rival turf
- **Pop-Out Performance** — perform at a block party
- **Music Video Shoot** — defend the set from rivals

---

## 2. Mission Generation Pipeline

### 2.1 Trigger Event

A world event occurs:

- Heat spike
- Influence shift
- AI confrontation
- Economic change
- Witness call
- Player action

### 2.2 Mission Selector

The system evaluates:

- Block state
- Faction state
- Player reputation
- Heat tier
- AI density
- Economic conditions

It selects the mission category with the highest weighted relevance.

### 2.3 Objective Builder

Constructs objectives using:

- Block graph
- Claimable nodes
- Patrol routes
- Heat zones
- AI spawn points

### 2.4 Difficulty Scaling

Difficulty is deterministic:

```
difficulty = baseDifficulty
           + heatModifier
           + AIThreatModifier
           + blockDensityModifier
           + reputationModifier
```

### 2.5 Reward Calculation

Rewards depend on:

- Risk
- Heat
- Block ownership
- Economic state

---

## 3. Mission Structure

### 3.1 Primary Objective

Always tied to:

- A block
- A node
- A faction
- A heat condition

Examples:

- "Hold Block A until influence stabilizes."
- "Disable 3 cameras in Block D."
- "Escort stash from Block B to Block E."

### 3.2 Secondary Objectives

Optional tasks that:

- Increase payout
- Reduce heat
- Improve reputation

Examples:

- "Avoid firing weapons."
- "Stay undetected."
- "Tag 2 extra walls."

### 3.3 Failure Conditions

Deterministic:

- Player death
- Heat Tier 4 escalation
- Node loss
- Stash destruction
- Rival takeover

---

## 4. Mission Flow States

### 4.1 Initialization

- Spawn AI
- Set patrol density
- Mark objective nodes
- Adjust heat decay

### 4.2 Active

- AI reacts dynamically
- Heat changes in real time
- Influence shifts
- Civilians witness events
- Police escalate

### 4.3 Resolution

- Influence updates
- Economic adjustments
- Reputation changes
- Retaliation score updates

### 4.4 Cooldown

Blocks enter a mission cooldown to prevent spam.

---

## 5. Mission Anchoring to Block Graph

Every mission references:

- `blockId`
- `subZones`
- `claimableNodes`
- `patrolRoutes`
- `heatLevel`

This ensures:

- No floating objectives
- No teleporting logic
- No disconnected mission states

---

## 6. AI Integration

AI behavior during missions:

- Patrol density increases
- Backup triggers faster
- Rival factions coordinate
- Police escalate based on heat
- Civilians panic and call police

AI uses the same deterministic state machine defined in `ai_behavior.md`.

---

## 7. Heat Integration

Heat modifies:

- Mission difficulty
- AI aggression
- Police response
- Civilian density
- Witness likelihood

Heat spikes can spawn new missions mid-mission.

---

## 8. Economy Integration

Missions affect:

- Corner revenue
- Stash safety
- Storefront cooperation
- Laundering efficiency

Economy missions are directly tied to Block D and claimable nodes.

---

## 9. Weapons Integration

Weapons influence missions via:

- Jam events
- Recoil control
- Penetration
- Noise (heat spikes)
- Illegal mods (risk multipliers)

Weapon choice changes mission flow.

---

## 10. Determinism Requirements

- Mission selection must be deterministic given identical world state
- AI spawns must follow fixed rules
- Heat changes must follow defined formulas
- Rewards must be reproducible
- Failure conditions must be strictly evaluated

---

*End of Section*
