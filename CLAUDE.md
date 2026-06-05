# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**-signal-system** is a rhythm/music intelligence system ("Beat Mania") that evolves a semantic representation of audio behavior over time. It is NOT a standard audio player — it is a self-observing system where audio generates physics, physics generates a genome, and the genome will eventually guide the scheduler back.

The system is being built in deliberate stages. Do not conflate stages or implement later stages prematurely.

## Tech Stack

- **React + TypeScript** — UI and component lifecycle
- **Canvas API (2D)** — genome visualizer (not WebGL)
- **Web Audio API / AudioWorklet** — audio source of truth; all rhythm physics originate here
- **requestAnimationFrame** — renderer loop (lifecycle-managed via `useEffect` cleanup)

## Core Data Abstractions

### Genome
The central data structure. Contains:
- `nodes: Map<string, GenomeNode>` — each node has `id`, `timestamp`, `strength`, `stability`, `type` (`"skin" | "memory" | <other>`)
- `edges: Edge[]` — each edge has `from`, `to`, `weight`, `type` (`"mutation" | "reinforcement" | <other>`)

Genome is a **semantic observer** — it records and interprets audio behavior. It does not (yet) control audio.

### Drift
A physics update object (`drift.update`) wired inside the AudioWorklet validation path. Drift is the bridge between raw audio events and genome writes. Audio is the source of truth; drift is its physics model.

### Species (Memory Compression Layer — Stage 2)
Compressed clusters of stable genome nodes. A "species" is a canonical identity extracted from the node graph (e.g., "Locked Pocket species", "Drift species", "Bounce family"). Species are the unit that Field Autonomy and the Mutation Engine operate on — **not** raw nodes.

## System Architecture

### Data Flow (Audio-First Topology — the only valid topology right now)

```
AudioWorklet → drift.update → Genome → HUD → [scheduler feedback — NOT YET]
```

Audio is always the source of truth. Genome observes downstream. Autonomy is not yet allowed to write back into the scheduler.

### Build Stages — do not skip ahead

| Stage | What it adds | Status |
|-------|-------------|--------|
| 1 | AudioWorklet → drift → Genome visualization (canvas renderer) | In progress |
| 2 | Memory Compression Layer — graph → species registry | Next |
| 3 | Scheduler reads species pressure | Future |
| 4 | Full closed-loop autonomy (Genome-First Topology) | Future |

Jumping to Stage 4 before Stage 2 means autonomy selects from noise nodes and transient attractors — entropy arbitration, not intelligence.

## Renderer Rules

The canvas genome renderer uses `requestAnimationFrame` inside a `useEffect`. The cleanup **must** cancel the animation frame to avoid the double-draw / stale-closure bug:

```ts
useEffect(() => {
  // ...
  let animId: number;
  const draw = () => {
    // ...
    animId = requestAnimationFrame(draw);
  };
  draw();
  return () => cancelAnimationFrame(animId);
}, [genome, width, height]);
```

**Node positions must not be recomputed every frame.** Recomputing layout on every `draw()` call is hidden O(N²) pressure. Cache positions and only recompute on:
- node insert
- edge insert (optional relaxation step)

This is the first physics optimization boundary and the line between "visualizer" and "field simulator frontend."

## Key Architectural Constraints

- **Memory Compression before Autonomy** — Species extraction (Stage 2) is a hard prerequisite for Field Autonomy (Stage 3). Without it, the mutation engine acts on raw event noise instead of stable identity units.
- **Genome-First Topology is experimental** — Do not wire Genome → scheduler → AudioWorklet until Stage 4 is explicitly started. It introduces feedback loop risk.
- **Drift lives inside AudioWorklet** — `drift.update` is not a standalone module; it runs in the AudioWorklet validation path where audio timing is authoritative.

## Repository

- **Remote:** `akryanblue-eng/-signal-system` on GitHub
- **Default branch:** `main`
- **Feature branches:** `claude/<descriptor>-<hash>` pattern

## Commands

_To be added once package.json / build tooling is committed._
