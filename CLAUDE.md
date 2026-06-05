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

## Two-Plane Architecture

The system runs on two distinct planes that must not entangle:

### Real-Time Plane
```
AudioWorklet → scheduler → drift.stream
```
Live, timing-critical. This plane owns the clock.

### Evolution Plane
```
Genome ingestion → [compression] → [species extraction] → [autonomy]
```
Offline and semi-real-time. This plane observes and interprets.

### The Single Coupling Point
The two planes meet **only** at `drift.update`, which runs inside the AudioWorklet validation path. This is intentional — it is the only place where physics observations cross into the evolution plane. Do not add a second coupling point without explicitly designing for it.

## Core Data Abstractions

### Genome
The central data structure. Contains:
- `nodes: Map<string, GenomeNode>` — each node has `id`, `timestamp`, `strength`, `stability`, `type` (`"skin" | "memory" | <other>`)
- `edges: Edge[]` — each edge has `from`, `to`, `weight`, `type` (`"mutation" | "reinforcement" | <other>`)

Genome is currently **perfectly recorded history** — a raw pressure field, not an actionable structure. It becomes actionable only after the Memory Compression Layer (Stage 2) runs. Before that point, every transition is equally "valid"; noise and signal coexist with no identity stabilization.

Genome is a **semantic observer** — it does not control audio.

### Drift
A physics update object (`drift.update`) wired inside the AudioWorklet validation path. Drift is the bridge between raw audio events and genome writes.

### Species (Memory Compression Layer — Stage 2)
Compressed clusters of stable genome nodes. Shape:

```ts
interface SpeciesNode {
  prototypeVector: number[];   // geometric centroid of the cluster
  confidence: number;
  memberSkins: string[];       // node IDs belonging to this species
}
```

Clustering dimensions: **stability**, **tension profile**, **recurrence frequency** — no ML, pure geometry + thresholds.

Species are the unit that Field Autonomy and the Mutation Engine operate on. Autonomy without species = hallucinated agency (selecting from noise, transient attractors, dead branches).

## System Architecture

### Data Flow (Audio-First Topology — the only valid topology right now)

```
AudioWorklet → drift.update → Genome → HUD → [scheduler feedback — NOT YET]
```

Audio is always the source of truth. Genome observes downstream. Autonomy is not allowed to write back into the scheduler until Stage 3.

### Build Stages — do not skip ahead

| Stage | What it adds | Status |
|-------|-------------|--------|
| 1 | AudioWorklet → drift → Genome visualization (canvas renderer) | In progress |
| 2 | Memory Compression Layer — graph → species registry | Next |
| 3 | Scheduler reads species pressure (read-only hooks first) | Future |
| 4 | Full closed-loop autonomy (Genome-First Topology) | Future |

**Stage 2 is a hard prerequisite for Stage 3.** Compression introduces selection pressure retroactively: past drift becomes categorized → categories become real objects → objects become selectable forces. Without it, the scheduler has nothing stable to select from.

**Stage 4 (Genome-First Topology)** — `Genome → scheduler → AudioWorklet → drift.update` — is explicitly off-limits until started intentionally. It enables self-writing rhythm but introduces feedback loop risk.

The phase transition between Stage 1 and Stage 2 is: Genome goes from *recorded history* to *actionable structure*. That transition is **structure emergence**, not autonomy. Autonomy comes after structure exists.

## Renderer Rules

The canvas genome renderer uses `requestAnimationFrame` inside a `useEffect`. The cleanup **must** cancel the animation frame to avoid the double-draw / stale-closure bug:

```ts
useEffect(() => {
  const canvas = ref.current!;
  const ctx = canvas.getContext("2d")!;
  let animId: number;
  const draw = () => {
    // render nodes and edges...
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

1. **Single coupling point** — `drift.update` is the only place the real-time plane touches the evolution plane. Keep it that way.
2. **Memory Compression before Autonomy** — Species extraction (Stage 2) must exist before any autonomy work begins.
3. **Genome never controls audio** — until Stage 4 is explicitly started, treat any code path from Genome back to AudioWorklet as a bug.
4. **Species feeds scheduler read-only first** — when Stage 3 begins, wire species pressure as scheduler input only; no write-back until Stage 4.
5. **No ML for species extraction** — pure geometry + thresholds (stability, tension profile, recurrence frequency). Keeps compression deterministic and replayable.

## Repository

- **Remote:** `akryanblue-eng/-signal-system` on GitHub
- **Default branch:** `main`
- **Feature branches:** `claude/<descriptor>-<hash>` pattern

## Commands

_To be added once package.json / build tooling is committed._
