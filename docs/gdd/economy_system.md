# Economy System
*(Drill RAQ – Chiraq Sandbox)*

## Overview

The Economy System models street-level income, laundering, stash logistics, corner operations, and legitimate business fronts across the Chiraq sandbox.
It is asymmetrical, risk-weighted, and territorially dependent, meaning every dollar earned or lost is shaped by:

- Block ownership
- Claimable nodes
- Heat levels
- AI patrol density
- Player reputation
- Police surveillance

The goal is to create a high-stakes, high-reward economic loop that feels authentic to Chicago street operations while remaining mechanically tight and deterministic.

---

## 1. Core Principles

### 1.1 Asymmetry

Not all blocks produce equal income.
Not all operations carry equal risk.
Not all factions have equal access.

### 1.2 Territory-Driven

Economic output is directly tied to:

- Block influence
- Node control
- Heat
- Civilian density
- Police presence

### 1.3 Multi-Layered Income

Players earn money through:

- Street operations
- Stash node management
- Corner store fronts
- Music career progression
- Laundering through legitimate businesses

### 1.4 Risk vs. Reward

High-risk blocks (e.g., The Market Strip) generate more income but attract:

- Police
- Rival factions
- Witnesses
- Retaliation

---

## 2. Revenue Sources

### 2.1 Corner Operations (Block D – Market Strip)

Primary income source.

**Mechanics**

Each corner store generates passive revenue based on:

- Civilian traffic
- Heat level
- Player reputation
- Faction ownership

**Revenue Formula**

```
cornerRevenue = baseRate * civilianDensity * (1 - heatPenalty) * influenceMultiplier
```

**Player Actions**

- Collect earnings
- Intimidate rivals
- Bribe store owners
- Protect the block

---

### 2.2 Stash Nodes (Block B – The Cut)

High-risk, high-reward storage points.

**Mechanics**

- Store illegal goods
- Increase passive income
- Enable bulk operations
- Vulnerable to raids and rival theft

**Risk Factors**

- Heat
- Witnesses
- Rival influence
- Police patrols

---

### 2.3 Street Deals (All Blocks)

Direct player-driven income.

**Mechanics**

- Quick cash
- Attracts heat
- Increases faction retaliation
- Affected by block ownership

**Modifiers**

- Owned block: safer, higher payout
- Rival block: dangerous, lower payout
- Contested block: volatile, unpredictable

---

### 2.4 Legitimate Front Businesses

Long-term, stable income.

**Types**

- Car wash
- Corner store
- Barber shop
- Laundromat
- Recording studio

**Mechanics**

- Launder illegal money
- Generate clean income
- Reduce heat
- Provide mission hooks

---

### 2.5 Music Career Progression

A unique progression loop.

**Mechanics**

- Record tracks
- Build local hype
- Perform shows
- Earn streaming revenue
- Boost faction reputation

**Synergy**

Music fame:

- Reduces intimidation needed
- Increases corner revenue
- Attracts rival jealousy
- Draws police attention

---

## 3. Money Flow Between Blocks

### 3.1 Tax Flow

Each block under player control contributes a tax percentage to the player's organization.

```
blockTax = blockRevenue * taxRate
```

### 3.2 Upkeep Costs

Blocks require:

- Patrol funding
- Bribes
- Repairs
- Node maintenance

### 3.3 Profit Distribution

Player can:

- Reinforce blocks
- Upgrade stash nodes
- Improve store fronts
- Fund music production
- Pay AI crew members

---

## 4. Heat & Surveillance Integration

### 4.1 Heat Penalties

High heat reduces:

- Corner revenue
- Civilian traffic
- Storefront cooperation

### 4.2 Surveillance Zones

Cameras and witnesses:

- Increase risk
- Trigger investigations
- Reduce laundering efficiency

### 4.3 Police Pressure

Police raids:

- Seize stash nodes
- Shut down corners
- Freeze legitimate businesses

---

## 5. Claimable Node Economy Effects

### 5.1 Graffiti Walls

- Increase influence
- Boost corner revenue
- Attract rival retaliation

### 5.2 Porches

- Serve as lookout points
- Reduce risk of street deals
- Increase stash node safety

### 5.3 Stores

- Anchor corner operations
- Provide passive income
- Enable laundering

---

## 6. Player Progression Through Economy

### 6.1 Early Game

- Street deals
- Small stash nodes
- Low-tier corners

### 6.2 Mid Game

- Multiple block control
- Laundering businesses
- Music hype
- Crew upgrades

### 6.3 Late Game

- Multi-block tax flow
- High-tier fronts
- Large stash operations
- City-wide influence

---

## 7. Determinism Requirements

- Revenue ticks must be deterministic
- Heat penalties must follow fixed formulas
- Stash raids must follow threshold logic
- Tax flow must be reproducible
- Laundering must follow strict rules

---

*End of Section*
