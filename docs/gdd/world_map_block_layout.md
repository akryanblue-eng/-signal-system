# World Map Block Layout
*(Drill RAQ – Chiraq Sandbox)*

## Overview

The world map is a dense, hyper-localized 4–8 block Chicago environment designed for high-frequency interaction, AI patrol logic, territorial simulation, and emergent street encounters.
The layout prioritizes tight gangways, multi-flat brick apartments, corner stores, porches, alleys, and transit-adjacent micro-zones over large, empty spaces.

This map is the backbone of the Territorial Influence System, AI behavior, economy loops, and mission generation.

---

## 1. Map Structure Principles

### 1.1 Density Over Size

The map is intentionally compact:

- 4–8 major blocks
- 20–40 sub-zones
- 60–120 claimable nodes

This ensures:

- High encounter frequency
- Strong territorial identity
- Efficient AI routing
- Mobile performance stability

### 1.2 Authentic Chicago Topology

The layout reflects:

- North–South grid alignment
- Narrow gangways between buildings
- Multi-flat brick apartments
- Corner stores on intersections
- Vacant lots and fenced yards
- Elevated train tracks (optional future expansion)

### 1.3 Block Graph Connectivity

Each block is a node in the territorial graph.
Edges represent:

- Streets
- Alleys
- Gangways
- Parking lot cut-throughs

This graph drives:

- Influence spread
- Patrol routing
- Retaliation pathfinding
- Mission generation

---

## 2. Block Definitions

### 2.1 Block A – "Stony Front"

Primary residential block with:

- 3 multi-flat apartments
- 2 porches (claimable)
- 1 corner store
- 1 fenced vacant lot
- 2 gangways
- 1 alley exit

**Role:** Strong early-game faction turf, high tagging activity.

---

### 2.2 Block B – "The Cut"

A narrow alley-dominated block:

- Central alley spine
- 4 gangway entrances
- 1 abandoned garage
- 1 dumpster cluster
- 1 hidden stash node

**Role:** Ambush hotspot, retaliation staging area.

---

### 2.3 Block C – "Lakeshore Courts"

Low-income housing complex:

- 2 large buildings
- 6 porches
- 3 stairwell entrances
- 1 playground
- 1 basketball court

**Role:** High civilian density, high heat, police patrol zone.

---

### 2.4 Block D – "The Market Strip"

Commercial corridor:

- 2 corner stores
- 1 liquor store
- 1 barber shop
- 1 laundromat
- 1 bus stop
- 1 alley loop behind stores

**Role:** Economy hub, mission hub, witness-heavy zone.

---

### 2.5 Block E – "The Tracks"

Transit-adjacent block:

- Elevated train tracks
- Parking lot
- 1 chop-shop garage
- 2 graffiti walls
- 1 tunnel entrance

**Role:** Escape routes, chase sequences, high-risk deals.

---

## 3. Sub-Zones

Each block contains 4–10 sub-zones:

- Porches
- Storefronts
- Alley segments
- Gangway entrances
- Stairwells
- Vacant lots
- Parking cut-throughs

Sub-zones are used for:

- Patrol waypoints
- Mission triggers
- Retaliation spawn points
- Heat propagation

---

## 4. Claimable Nodes

Each block includes:

- 3–10 graffiti walls
- 2–6 porches
- 1–3 stores
- 1–2 alley hubs
- 1–2 gangway chokepoints

Nodes are:

- Visually marked
- Mechanically meaningful
- Tied to influence updates

---

## 5. Navigation Mesh Requirements

### 5.1 Multi-Layer NavMesh

- Street level
- Alley level
- Gangway level
- Interior entry points (future expansion)

### 5.2 Choke Points

Critical for:

- Ambush logic
- Police containment
- Faction patrols

### 5.3 Vehicle vs. Foot Paths

- Cars: streets + alleys
- AI foot patrols: streets + alleys + gangways

---

## 6. Heat & Surveillance Zones

Each block defines:

- Witness density
- Camera coverage
- Police patrol probability
- Civilian panic thresholds

These values feed:

- Heat system
- Retaliation logic
- Mission difficulty

---

## 7. Expansion Hooks

Future map expansions:

- Transit station interior
- High-rise block
- Industrial yard
- Riverwalk segment
- School block
- Hospital block

All expansions must connect to the existing block graph.

---

*End of Section*
