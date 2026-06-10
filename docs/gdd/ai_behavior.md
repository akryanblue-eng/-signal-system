# AI Behavior System
*(Drill RAQ – Chiraq Sandbox)*

## Overview

The AI Behavior System governs how NPC factions, civilians, and police navigate, patrol, confront, flee, retaliate, and escalate within the Chiraq sandbox.
AI behavior is state-driven, territorially aware, and influenced by block ownership, heat levels, and player reputation.

This system integrates directly with:

- The Block Influence Grid
- The World Map Block Layout
- The Heat & Surveillance System
- The Retaliation System

AI must feel organic, local, and reactive, not scripted.

---

## 1. AI Categories

### 1.1 Faction AI (Sets)

- Patrol their turf
- Confront rivals
- Respond to contested blocks
- Initiate retaliation events
- Defend claimable nodes

### 1.2 Civilian AI

- Panic and flee during violence
- Call police when witnessing crimes
- Provide ambient life
- React to player reputation ("Look" mechanic)

### 1.3 Police AI

- Tactical containment
- Foot chases through gangways
- Vehicle PIT maneuvers
- Camera-triggered investigations
- Heat-based escalation

---

## 2. AI State Machine

All AI types share a common base state machine with specialized branches.

### 2.1 Base States

- **Idle** — standing, leaning, talking
- **Patrol** — walking routes based on block influence
- **Observe** — watching player or rivals
- **Confront** — verbal or physical escalation
- **Flee** — escape from danger
- **Backup** — calling allies or police
- **Combat** — shooting, taking cover, flanking
- **Search** — looking for player after losing line-of-sight
- **Recover** — returning to normal behavior

---

## 3. Patrol Logic

### 3.1 Patrol Generation

Patrols spawn or route based on:

- Block ownership
- Influence thresholds
- Contested status
- Heat level

### 3.2 Patrol Routes

Routes prioritize:

- Claimable nodes
- Alley hubs
- Gangway entrances
- Storefronts
- High-heat corners

### 3.3 Patrol Density

- Owned blocks: normal density
- Contested blocks: high density
- Rival blocks: low density unless retaliating

---

## 4. Confrontation Logic

### 4.1 Trigger Conditions

AI confronts the player or rivals when:

- Player enters rival turf with negative reputation
- Player stares too long ("Look" mechanic)
- Player brandishes a weapon
- Player commits a crime in view

### 4.2 Confrontation Stages

1. Verbal Warning
2. Approach
3. Aggressive Posture
4. Combat Initiation

### 4.3 Group Behavior

Nearby AI join confrontations based on:

- Faction loyalty
- Block influence
- Heat level

---

## 5. Flee Logic

AI flees when:

- Outnumbered
- Low health
- Police arrive
- Player reputation is overwhelmingly high

Fleeing AI:

- Use gangways and alleys
- Avoid open streets
- Attempt to call backup

---

## 6. Backup Logic

### 6.1 Faction Backup

Triggered when:

- AI is attacked in their own turf
- Block is contested
- Player kills a faction member

Backup types:

- Foot reinforcements
- Vehicle pull-ups
- Alley ambushes

### 6.2 Police Backup

Triggered by:

- Civilian calls
- Camera detection
- High heat
- Gunfire in public

Police escalate from:

- Patrol cars →
- Tactical units →
- Helicopter spotlight

---

## 7. Combat Behavior

### 7.1 Cover System

AI uses:

- Cars
- Porches
- Dumpsters
- Alley corners
- Stairwell entrances

### 7.2 Movement

- Flanking
- Retreating
- Advancing under fire
- Switching between cover points

### 7.3 Weapon Handling

- Accuracy varies by faction
- Low-tier weapons jam
- High recoil for illegal mods

---

## 8. Contested Block Rules

### 8.1 Behavior Changes

In contested blocks, AI:

- Patrol more aggressively
- Confront faster
- Call backup sooner
- Engage in turf skirmishes with rivals

### 8.2 Player Impact

Player actions can:

- Tip the balance
- Trigger faction wars
- Cause temporary ceasefires
- Increase heat dramatically

---

## 9. Civilian Behavior

### 9.1 Panic System

Civilians panic when:

- Gunshots occur
- Fights break out
- Police chase happens nearby

### 9.2 Witness System

Civilians may:

- Call police
- Run away
- Record the player
- Freeze in fear

### 9.3 Reputation Reactions

High player reputation:

- Civilians avoid eye contact
- Some greet respectfully
- Others flee immediately

---

## 10. Police Behavior

### 10.1 Detection

Police detect crimes via:

- Witness calls
- Cameras
- Patrols
- Gunshot detection

### 10.2 Tactics

- Foot chases through gangways
- Vehicle PIT maneuvers
- Containment per block
- Backup escalation

### 10.3 Heat Integration

Higher heat:

- Faster response
- More units
- Tactical gear
- Helicopter spotlight

---

## 11. Determinism Requirements

- State transitions must be deterministic
- Patrol routes must be reproducible
- Backup triggers must follow fixed thresholds
- Combat behavior must follow defined rules
- Flee logic must be consistent across runs

---

*End of Section*
