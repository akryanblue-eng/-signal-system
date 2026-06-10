# Weapons System
*(Drill RAQ – Chiraq Sandbox)*

## Overview

The Weapons System models street-level firearms, illegal modifications, reliability issues, recoil behavior, and kinetic environmental interactions within the Chiraq sandbox.
The goal is to create a grounded, high-pressure combat loop that reflects the instability, scarcity, and improvisation of real street weapons without providing real-world instructions or operational detail.

Weapons in Drill RAQ are defined by:

- Reliability (jam chance, misfire chance, overheating)
- Recoil profile (vertical, horizontal, randomness)
- Illegal modifications (switches, extended mags, mismatched parts)
- Damage model (body part zones, armor, penetration)
- Environmental interaction (drywall, wood, car doors)

This system integrates with:

- AI behavior
- Heat system
- Retaliation logic
- Block topology
- Cover system

---

## 1. Weapon Classes

### 1.1 Handguns

- Low damage
- High availability
- Moderate recoil
- High reliability
- Concealable (affects heat and witness reactions)

### 1.2 Compact SMGs

- High rate of fire
- High recoil
- Moderate reliability
- Effective in alleys and gangways

### 1.3 Full-Size SMGs

- Higher stability
- Larger magazines
- Stronger recoil control
- Louder (increases heat rapidly)

### 1.4 Shotguns

- High close-range damage
- Wide pellet spread
- Low penetration
- High intimidation effect

### 1.5 Rifles

- High damage
- High penetration
- High recoil
- Rare and high-risk to carry

---

## 2. Illegal Modification System

Illegal modifications are risk multipliers, not pure upgrades.
They increase firepower but reduce reliability and control.

### 2.1 Auto-Switch Mod

Effects:

- Converts semi-auto → pseudo full-auto
- Dramatically increases recoil
- Increases jam chance
- Increases heat generation
- Increases police attention

### 2.2 Extended Magazines

Effects:

- More rounds
- Slower reload
- Higher jam probability
- Heavier weapon feel

### 2.3 Improvised Parts

Effects:

- Unpredictable recoil
- Higher misfire chance
- Lower accuracy
- Unique sound signature

### 2.4 Drum Magazines

Effects:

- High ammo capacity
- Extremely heavy
- High jam chance
- Slower movement while firing

---

## 3. Reliability System

Weapons in Drill RAQ are intentionally imperfect.

### 3.1 Jam Types

- **Soft Jam** — quick tap-rack animation
- **Hard Jam** — longer clear animation
- **Misfire** — delayed shot or no shot

### 3.2 Reliability Formula

Reliability is influenced by:

- Weapon class
- Weapon condition
- Illegal mods
- Rate of fire
- Heat level

### 3.3 Condition States

- Pristine
- Used
- Worn
- Beat-Up

Condition affects:

- Jam chance
- Accuracy
- Recoil stability

---

## 4. Recoil & Handling

### 4.1 Recoil Profile

Each weapon has:

- Vertical recoil curve
- Horizontal recoil randomness
- First-shot kick
- Sustained fire drift

### 4.2 Movement Penalties

Running, jumping, or firing while turning increases:

- Spread
- Recoil
- Jam chance

### 4.3 Illegal Modifiers

Auto-switch mods drastically increase recoil and drift.

---

## 5. Damage Model

### 5.1 Body Zones

- Head
- Upper torso
- Lower torso
- Arms
- Legs

Damage varies by:

- Weapon class
- Range
- Penetration

### 5.2 Armor

Armor reduces:

- Incoming damage
- Penetration
- Stagger

### 5.3 Stagger System

High-caliber hits cause:

- Flinch
- Movement slowdown
- Aim disruption

---

## 6. Environmental Interaction

Weapons interact with the environment in non-graphic, systemic ways.

### 6.1 Penetration

Different materials absorb or allow partial penetration:

- Drywall
- Wood
- Car doors
- Metal fences

### 6.2 Ricochet

Low-chance ricochet on:

- Metal
- Concrete

### 6.3 Destructible Props

Non-graphic destruction of:

- Wooden porch railings
- Storefront glass
- Car windows
- Light debris

---

## 7. Audio Identity

Weapons must sound:

- Heavy
- Imperfect
- Local
- Distinct per condition and mod

Audio cues communicate:

- Jam events
- Modded fire rate
- Weapon condition
- Distance and direction

---

## 8. Heat Integration

Firing weapons increases heat based on:

- Weapon class
- Modifications
- Location (Market Strip vs. alley)
- Witness density
- Time of day

Police respond faster to:

- Automatic fire
- High-caliber shots
- Sustained bursts

---

## 9. AI Integration

AI uses the same weapon rules as the player.

### 9.1 AI Weapon Behavior

- Faction AI uses low-reliability weapons
- Police use high-reliability weapons
- Rival factions may use illegal mods
- AI reacts to jams with panic or retreat

### 9.2 Cover Behavior

AI chooses cover based on:

- Penetration risk
- Weapon class
- Player weapon type

---

## 10. Determinism Requirements

- Jam chance must be deterministic per frame
- Recoil curves must be reproducible
- Penetration must follow fixed material tables
- Damage must follow strict formulas
- Illegal mods must apply consistent penalties

---

*End of Section*
