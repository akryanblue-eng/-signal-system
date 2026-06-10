# signal-system

A falsification engine for emergent behavioral identity under controlled perturbation.

---

## Architecture

```
Stories (ground truth observations)
  └─► Perturbations (controlled reality edits)
        └─► Deformation (only valid signal)
              └─► Attractors (only stabilized deformation history)
```

**Global invariant:** No belief without a recorded stress event.

---

## Layers

| Layer | Objects | Role |
|-------|---------|------|
| Capture | Story Board, Story, Memory Driver, Intensity, ⭐ | Raw observation |
| Emergence | Attractor Map, Behavioral/Structural Attractor, Trigger Recipe | Pattern detection |
| Causal Testing | Constraint Map, Constraint Tests, Deformation Modes | Stress application |
| Truth Engine | Perturbation, Deformation, Dormant/Active/Stress-Verified | Signal validation |
| Identity | Identity Envelope, Tolerance Band, Boundary of Acceptable Deformation | Stability bounds |

---

## Directory Layout

```
stories/          story_YYYY_MM_DD_NNN.json   — capture layer events
perturbations/    perturb_YYYY_MM_DD_NNN.json — stress events
constraints/      constraint_<slug>.json       — causal hypotheses
attractors/       attractor_<slug>.json        — stabilized patterns
sessions/         session_YYYY_MM_DD.md        — derived summaries only
schemas/          *.schema.json               — canonical JSON schemas
scripts/          *.py                        — CLI tools + drift detector
```

---

## Workflow

**Default (observation-first):**

```
log_story → run perturbation → evaluate deformation → promote attractor
```

**Experiment mode** (allowed, restricted):

```
design constraint test → inject perturbation → must reference existing stories
```

**Forbidden:**

```
Constraint → Attractor → Story (retrofitting = hallucinated structure)
```

---

## Scripts

```bash
# Log a story (always the primary entry point)
python scripts/log_story.py --text "..." --driver "..." --intensity 3

# Validate all JSON files against schemas
python scripts/validate.py

# Run drift detection
python scripts/drift_detector.py
```

---

## Drift Detector

Flags five failure modes:

| Check | Rule |
|-------|------|
| Orphan attractor | Attractor with no story or no perturbation reference |
| Unfalsified constraint | Constraint marked active/verified with no perturbation log |
| Missing deformation chain | Story used in promotion but never stress-tested |
| Compression hazard | Attractor with ≥3 stories and 0 perturbations |
| Label drift | Keys not in the schema registry |

Output:

```
==================================================
DRIFT REPORT
==================================================
Orphan attractors:                  0
Unfalsified constraints:            0
Missing deformation chains:         0
Compression hazards:                0
Label drift events:                 0
==================================================
Clean. No drift detected.
```

---

## Terminology Lock (v1.0)

Valid objects only. Everything else is noise.

**Capture:** Story Board · Story · Memory Driver · Intensity (1–3) · ⭐

**Emergence:** Attractor Map · Behavioral Attractor · Structural Attractor · Trigger Recipe · Systems Intersection · Recurrence / Variation Survival / Collision Coherence

**Causal Testing:** Constraint Map · Constraint Tests (timing / density / geometry / resource / chaos) · Deformation Modes (shift / relocate / frequency / wrapper) · Failure Mode · Fragility Notes · Last Tested

**Truth Engine:** Perturbation · Deformation · Dormant / Active / Stress-Verified

**Identity:** Identity Envelope · Tolerance Band · Boundary of Acceptable Deformation
