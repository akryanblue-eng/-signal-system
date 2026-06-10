# Live Debug Overlay Spec v0.1

**Engine-agnostic. Bolt-on to Unity / Unreal / FiveM / custom sim.**
**No redesign required. Reads existing AI, heat, and physics state.**

This is not an informational HUD. It is a real-time phase space observer for emergent
narrative systems — watching entropy injection (E), decision branching (A), and attractor
formation (R) as a live dynamical system.

---

## 1. Compact Display Format

Default mode (all fields visible):

```
[E]: ACTIVE | [A]: 2 | [R]: FORMING | BP: Decorative Adaptation | ARC: Partial | LM: Y | REC: Y
```

Fields:

| Field | Values | Description |
|-------|--------|-------------|
| E | DORMANT / ACTIVE / SPIKING | Escalation state |
| A | 0 / 1 / 2 / 3+ | Meaningful decisions in rolling 10–15s window |
| R | NONE / FORMING / STABLE / BROKEN | Resolution convergence |
| BP | (see §4) | Current dominant breakpoint class |
| ARC | FULL / PARTIAL / COLLAPSED | Story arc validity |
| LM | Y / N | Landmark attachment in last 10s |
| REC | Y / N | Recovery event in last 10s |

---

## 2. E — Escalation Detector

**Events that trigger E transitions:**

- Sightline established
- Chase initiated
- Collision event
- Heat level increase
- Patrol detection
- Rival contact

**State logic:**

```
DORMANT  → no pressure events in last T seconds (T = configurable, default 8s)
ACTIVE   → pressure event(s) ongoing
SPIKING  → ≥3 pressure events within 5s window
```

**Implementation note:** Use existing heat/wanted system event hooks. Do not add new
simulation state — read what the AI system already tracks.

---

## 3. A — Adaptation Window Tracker

**Valid A increments (meaningful decisions only):**

- Route change (new topology node entered)
- Vehicle swap or ditch
- Visibility state change (entered cover, broke LoS)
- Risk posture shift (toward/away from threat)
- Recovery action after failure moment

**NOT valid A increments:**

- Passive movement
- Cosmetic actions (horn, emotes)
- Consequence events (damage, arrest) — those are E or R

**Window:** Rolling 10–15 seconds. Reset on R transition.

**State:**

```
0 = no agency — danger state (player locked out of meaningful choice)
1 = single response
2 = adaptive chain forming
3+ = improvisation state
```

---

## 4. R — Resolution Detector

**R is NOT end-of-chase. R is state stabilization.**

R transitions:

```
NONE     → still in active motion loop, E ongoing
FORMING  → pressure reduced, branching collapsing toward resolution
STABLE   → no escalation events + no pursuit lock (sustained for ≥5s)
BROKEN   → abrupt termination (crash / fail state / forced teleport)
```

**Key rule:** R only exists if E has stopped meaningfully influencing A.

If E fires again while R is FORMING → revert to ACTIVE.

---

## 5. Breakpoint Classifier

Assign one dominant tag every 3–5 seconds. Always pick best fit even if multiple apply.

| Tag | Condition |
|-----|-----------|
| `Free Escape` | A exists, R too easy — no challenge pressure |
| `Instant Collapse` | E fired, no A window opened |
| `Infinite Chase` | E+A active, R never converges |
| `Decorative Adaptation` | A > 1, outcome coupling near zero |
| `Single-Path Adaptation` | A repeats same grammar run-over-run |
| `Unstable R` | R flickers between FORMING and NONE |
| `False Story Positive` | ARC shows FULL but E/A/R integrity fails on inspection |
| `Memoryless City` | LM=N sustained across ≥3 consecutive runs |

**Implementation:** Simple state machine reading E/A/R fields above. No new data source.

---

## 6. ARC Classifier

Updated on R transition:

```
FULL      → complete E → A → R chain with no phase gap
PARTIAL   → E + A present, R weak or unstable
COLLAPSED → E without meaningful A window
```

**ARC is the signal-system's story validity judgment made visible in real time.**

---

## 7. Landmark Signal (LM)

`YES` if within last 10s:
- Player entered a named or structurally distinct spatial node
- Player used remembered geography for a navigation decision
- Player revisited a previously encountered node

`NO` otherwise.

**Implementation:** Tag 3–5 high-salience spatial nodes per district in the level data.
Check for player entry + decision event within the same 10s window.

---

## 8. Recovery Signal (REC)

`YES` if within last 10s:
- Player regained agency after a failure moment
- AND changed at least one state: vehicle / route / visibility / tactic

`NO` otherwise.

**Both conditions required.** Regaining agency without state change = cosmetic recovery.

---

## 9. Critical Alerts

Overlay flashes (operator interrupt, not player-visible):

| Alert | Condition | Meaning |
|-------|-----------|---------|
| `VPR BREACH` | Same A-grammar for ≥4 consecutive runs | Strategy collapse |
| `RCP BREACH` | A > 1 sustained but R never reaches STABLE | Smear without islands |
| `COUPLING FAIL` | E events no longer change A count | Phase continuity lost |

These are system health interrupts. Log them as `fragility_notes` in the session record.

---

## 10. Debug Modes

Toggle during live session:

| Mode | Shows |
|------|-------|
| Physics | E / A / R transitions only |
| Breakpoint | Dominant breakpoint tag only |
| Narrative | ARC + LM + REC only |
| Full (default) | All fields |

---

## 11. Data Export (session integration)

At session end, overlay writes a summary compatible with `session.schema.json`:

```json
{
  "arc_distribution": { "full": 0, "partial": 0, "collapsed": 0 },
  "breakpoint_counts": { "instant_collapse": 0, "decorative_adaptation": 0 },
  "alert_log": [],
  "lm_rate": 0.0,
  "rec_rate": 0.0
}
```

Paste into the session's `fragility_notes` or use as evidence for perturbation records.

---

## 12. Footer Invariant

Always visible at bottom of overlay:

```
Diagnosable ≠ Predictable   |   A-diversity must not collapse into R-uniformity
```

---

## 13. What this enables

With overlay live:

- Story formation visible as it happens (not post-run reconstruction)
- VPR collapse detectable within a single session
- RCP smear identified before the session ends
- Tuning decisions made before the playtest is over
- "Dead gameplay physics" distinguished from emergent arcs in real time

**This is not a debug HUD. It is a real-time phase space observer.**
