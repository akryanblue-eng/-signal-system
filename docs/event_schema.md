# Event Schema — Canonical Specification

triage.py ingests a stream of these objects. One object per line (JSONL) or a JSON array.
One file = one run. No cross-run state is maintained by the script.

---

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | recommended | Groups this event to a run. Used as `run_id` if `--run-id` not passed. |
| `type` | string | **required** | Event type. Determines E/A/R phase assignment. See taxonomy below. |
| `e_class` | string | optional | Escalation class label (e.g. `POLICE_HEAT`, `RIVAL_AMBUSH`). First value seen becomes `EAR.E_class`. |
| `adaptation` | boolean | optional | `true` = this event is a control-logic delta. **Required for A to increment.** |
| `landmark` | string | optional | Spatial node name. Collected into `EAR.landmarks[]`. |
| `resolution` | string | optional | Outcome string (e.g. `escape`, `arrest`). Locks R to LANDED. |
| `heat` | number 0–100 | optional | Heat level at event time. Logged, not used by phase logic. |
| `visibility` | number 0–1 | optional | 1.0 = fully visible to threat. Logged, not used by phase logic. |
| `loc` | string | optional | Spatial node where event occurred. Logged, not used by phase logic. |
| `t` | string (ISO 8601) | optional | Timestamp. Logged, not used by phase logic. |

---

## Type Taxonomy

### E events — new constraint appearances only

These increment `E_pressure_events`. Do NOT use for generic activity.

```
police_sightline     — pursuit initiated from sight
police_pursuit       — active pursuit underway
pressure_*           — generic pressure injection (any suffix)
heat_increase        — heat level rises (not heat_decay — that is R)
rival_appear         — rival entity enters the space
e_*                  — explicit escalation event (any suffix)
```

**NOT E:** `player_move`, `player_*`, `move_*`, `heat_decay_*`, anything passive.

### A events — control-logic deltas only

These increment `A_adaptation_events` AND `EAR.A`. The phase honesty invariant:
**movement is not adaptation.**

```
adapt_*              — any event with adapt_ prefix (adapt_cover, adapt_reroute, etc.)
```

OR: **any event type** with `"adaptation": true` in the payload.

**NOT A:** `player_move`, `player_*`, `move_*`, any event without the flag or prefix.

### R events — pressure decay and resolution only

These increment `R_resolution_events`. Setting `resolution` field also locks `EAR.R` to `LANDED`.

```
resolve_*            — resolution event (resolve_escape, resolve_arrest, etc.)
escape_*             — escape outcome event
arrest_*             — arrest outcome event
heat_decay_start     — heat measurably begins decaying (pressure-driven, not timer)
r_*                  — explicit resolution event (any suffix)
```

**NOT R:** `end_*` (ambiguous), timer events, proximity triggers.

### Neutral events — logged but not counted in E/A/R

```
player_move          — movement; logged for landmark/loc tracking only
player_*             — any player activity without adaptation=true
```

---

## Run Boundaries

**Default:** one file per run. Each JSONL file passed to `--events` is treated as one complete run.

**Multi-run files:** not supported in v0.1. Concatenate multiple scenarios as separate files
and run triage.py once per file.

---

## Minimal Valid Event Sequence (one run)

```jsonl
{"session_id":"S-001","type":"police_sightline","e_class":"POLICE_HEAT","heat":20,"visibility":1.0,"loc":"market"}
{"session_id":"S-001","type":"player_move","heat":25,"visibility":0.8,"loc":"market"}
{"session_id":"S-001","type":"adapt_cover","adaptation":true,"landmark":"alley_diner","heat":18,"visibility":0.3,"loc":"alley"}
{"session_id":"S-001","type":"resolve_escape","resolution":"escape","heat":5,"visibility":0.1,"loc":"back_street"}
```

Produces: `E=PRESENT, A=1, R=LANDED` → breakpoint `FullArc`, no violations.

---

## Phase Honesty Contract

These three rules are invariants, not suggestions:

| Phase | Fires when | Does NOT fire on |
|-------|-----------|-----------------|
| E | New constraint appears in simulation | Retroactive inference, outcome observation, generic activity |
| A | Control-logic delta by player | Movement, position updates, passive activity, noise |
| R | Pressure measurably decays | Timers, proximity, arbitrary thresholds |

If you cannot determine whether an event is E, A, or R without reading outcomes — it is not a valid phase event. Log it as neutral (`player_move` or similar) and do not assign a phase prefix.

---

## Three Calibration Knobs

These are the knobs most directly coupled to single-run phase behavior.
See `schemas/knob_registry.json` for full spec.

### `police_response_delay`
- **Axis:** COUPLING (E→A window)
- **Default:** 1.2 sec
- **Range:** [0.2, 5.0] sec, step 0.5
- **Coupling:** directly controls the E→A window width. Low values → InstantCollapse (no A window). High values → FreeEscape (insufficient pressure).
- **Phase honesty test:** change by +0.5, re-run same E-class. A_adaptation_events should increase if the window was previously too tight.

### `heat_decay_rate`
- **Axis:** RCP (R-depth)
- **Default:** 1.0x
- **Range:** [0.0, 2.0]x, step 0.05
- **Coupling:** controls speed of pressure decay. Drives R basin formation. Low → R smear (never lands). High → FreeEscape (R trivially lands).
- **Phase honesty test:** change by +0.1, re-run same scenario. R should transition from UNRESOLVED to FORMING or LANDED if it was previously stuck.

### `rival_aggression`
- **Axis:** VPR (A-space)
- **Default:** 1.0x
- **Range:** [0.0, 2.0]x, step 0.2
- **Coupling:** adds a second pressure source that forces different A-grammar selection. Low → single-path adaptation dominates. High (>1.8) → E saturation (rival + police = no A window).
- **Phase honesty test:** change by +0.4, re-run. A_adaptation_events distribution should shift toward different adapt_* event types (different grammars used).
