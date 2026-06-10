# Combat System
*(Drill RAQ – Chiraq Sandbox)*

## Overview

The Combat System defines player-side combat mechanics built on top of the Weapons System, AI Behavior System, Heat & Surveillance System, and Block Topology.
Combat in Drill RAQ is grounded, high-pressure, unreliable, and spatially constrained, reflecting the tight gangways, porches, alleys, and corner stores of the Chiraq sandbox.

The system emphasizes:

- Deterministic weapon behavior
- High lethality
- Imperfect firearms
- Environmental interaction
- AI parity (AI uses the same rules as the player)
- Heat-driven escalation

---

## 1. Combat Philosophy

### 1.1 High Stakes

Combat is dangerous.
Weapons jam.
Heat spikes.
Police respond.
Rivals retaliate.

### 1.2 Spatial Combat

The map's geometry shapes combat:

- Gangways = flanking
- Porches = cover
- Alleys = choke points
- Corner stores = witness zones

### 1.3 Deterministic Systems

Every shot, jam, recoil pattern, and AI reaction follows fixed rules.

---

## 2. Player Combat States

### 2.1 Idle

- Weapon holstered
- Low heat generation
- Civilians calm
- AI non-aggressive

### 2.2 Ready

- Weapon drawn
- Witnesses react
- AI enters Observe state
- Heat increases slowly

### 2.3 Aim

- Reduced movement speed
- Accuracy improves
- Recoil becomes predictable
- AI becomes more alert

### 2.4 Fire

- Triggers recoil
- Jam checks
- Heat spikes
- AI enters Confront or Combat state

### 2.5 Reload

- Vulnerable state
- Animation length depends on weapon class
- Extended/drum mags increase reload time

### 2.6 Jam Clear

- Soft jam: quick
- Hard jam: long
- Illegal mods increase jam frequency

### 2.7 Sprint

- Accuracy drops
- Recoil increases
- Jam chance increases
- AI loses line-of-sight faster

---

## 3. Aiming & Accuracy

### 3.1 Aim Styles

- **Hip-fire** — fast, inaccurate
- **ADS (Aim Down Sights)** — slow, accurate
- **Quick-aim** — snap to target, medium accuracy

### 3.2 Accuracy Formula

```
accuracy = baseAccuracy
         - movementPenalty
         - recoilPenalty
         - conditionPenalty
         + aimBonus
```

### 3.3 First-Shot Accuracy

First shot after aiming is the most accurate.

---

## 4. Recoil System

### 4.1 Recoil Curves

Each weapon has:

- Vertical recoil curve
- Horizontal drift
- Randomness factor
- Illegal mod multiplier

### 4.2 Recoil Reset

Recoil resets after:

- Short pause
- ADS hold
- Jam clear

### 4.3 Sustained Fire

Sustained fire:

- Increases drift
- Increases jam chance
- Increases heat

---

## 5. Damage Model

### 5.1 Body Zones

- Head (high damage)
- Upper torso (medium)
- Lower torso (medium-low)
- Arms (low)
- Legs (low, slows movement)

### 5.2 Penetration

Penetration depends on:

- Weapon class
- Material type
- Range

### 5.3 Stagger

High-caliber hits cause:

- Flinch
- Aim disruption
- Movement slowdown

---

## 6. Cover System

### 6.1 Cover Types

- Cars
- Dumpsters
- Porches
- Alley corners
- Storefronts

### 6.2 Cover Behavior

Cover provides:

- Damage reduction
- Penetration mitigation
- Line-of-sight breaks

### 6.3 Blind Fire

Player can blind-fire:

- Low accuracy
- Low exposure
- High heat

---

## 7. Environmental Interaction

### 7.1 Material Reactions

- Drywall: penetrable
- Wood: partially penetrable
- Car doors: inconsistent
- Brick: non-penetrable
- Glass: shatters

### 7.2 Ricochet

Low-chance ricochet on:

- Metal
- Concrete

### 7.3 Destructible Props

Non-graphic destruction of:

- Porch railings
- Storefront glass
- Car windows
- Light debris

---

## 8. AI Integration

AI uses the same combat rules as the player.

### 8.1 AI Weapon Behavior

- AI suffers jams
- AI recoil is deterministic
- AI uses cover intelligently
- AI flanks using gangways

### 8.2 AI Aggression

Aggression depends on:

- Block ownership
- Heat tier
- Faction type
- Player reputation

### 8.3 AI Backup

Backup triggers:

- Foot reinforcements
- Vehicle pull-ups
- Alley ambushes

---

## 9. Heat Integration

Combat directly affects heat.

### 9.1 Heat Spikes

Heat increases from:

- Gunfire
- Automatic fire
- High-caliber shots
- Shooting near witnesses
- Shooting near cameras

### 9.2 Heat Tier Effects

- Tier 1: faster witness calls
- Tier 2: police respond to gunshots
- Tier 3: containment
- Tier 4: helicopter spotlight

---

## 10. Player Feedback

### 10.1 Visual

- Screen shake
- Recoil kick
- Hit markers (subtle)
- Stagger indicators

### 10.2 Audio

- Weapon condition sounds
- Jam sounds
- Penetration sounds
- Police radio chatter

### 10.3 UI

- Ammo count
- Jam indicator
- Heat indicator
- Block name + danger level

---

## 11. Determinism Requirements

- Recoil curves must be deterministic
- Jam checks must follow fixed probability tables
- Damage must follow strict formulas
- Penetration must follow material tables
- AI combat behavior must follow state machine rules
- Heat spikes must follow defined multipliers

---

*End of Section*
