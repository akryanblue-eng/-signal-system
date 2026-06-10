# Full Stack Stress Test — [DATE]

> **Operator only. No naïve testers.**
> This run is not to generate a good story.
> It is to answer: "When everything is pushed toward instability, does the system
> still produce classifiable narrative physics?"
>
> No tuning during run. No interpretation during run. One perturbation per phase.

---

## Pre-Load Conditions

- [ ] No tuning allowed during run
- [ ] No interpretation during run
- [ ] One perturbation per phase (strictly)
- [ ] Mindset: you are stressing the system, not playing the game

---

## Phase 1 — VPR Collapse Attempt (A-space attack)

**Intent:** Force a dominant A-grammar to emerge.

**Setup:** Identical pressure injection across all runs:
- Same theft trigger: _______________
- Same starting vehicle type: _______________
- Same initial spawn location: _______________
- Same heat ramp speed: _______________

**Operator action:** During first escalation, always choose the most obvious survival
strategy. Repeat the exact same choice in subsequent runs.

**What you're inducing:** Single A-grammar becomes optimal. Other strategies disappear.

**Failure signature to watch for:**
- [ ] TopA_share > 0.7 (all runs converge to same escape logic)
- [ ] "Choice" feels cosmetic, not structural

---

## Phase 2 — RCP Collapse Attempt (R-space smear)

**Intent:** Break closure stability and compressibility.

**Setup:** At midpoint of chase (first major escalation peak), force a random disruption:
- Type used: ☐ vehicle loss  ☐ forced reroute  ☐ visibility break  ☐ rival intervention

**Operator action:** After disruption, do NOT seek optimal recovery. Alternate between:
hiding / re-engaging / abandoning objectives / re-stealing vehicles.

**What you're inducing:** Arcs that never lock. Many micro-events, no island formation.

**Failure signature to watch for:**
- [ ] Runs cannot be summarized in <3 steps
- [ ] No repeatable R patterns
- [ ] "What happened?" answers are long, messy, non-repeatable

---

## Phase 3 — E/A/R Break Test (phase continuity attack)

**Intent:** Break story formation entirely.

**Setup:** Active simultaneously:
- Police pressure (systematic containment): ☐
- Rival pressure (unpredictable interference): ☐
- Environmental instability (traffic/blockers/dead ends): ☐

**Operator action:** Make at least one non-logical adaptation per run:
- ☐ doubled back into danger
- ☐ abandoned safe escape for loot/vehicle swap
- ☐ entered known dead-end topology

**What you're inducing:** Escalation without adaptation window. Adaptation without
meaningful consequence. Resolution without causality.

**Failure signature to watch for:**
- [ ] Missing phase transitions (E → A → R collapses)
- [ ] Adaptation exists but doesn't affect outcome
- [ ] Resolution feels arbitrary or disconnected

---

## Phase 4 — Full System Stress (combined attack)

**Intent:** Worst-case entropy. "Can the system still form any coherent story islands
under full adversarial pressure?"

Inject all Phase 1–3 conditions simultaneously.
Alternate strategies each run deliberately. Do not stabilize. Do not optimize.

---

## Run Log

One row per run. Fill immediately after each run — no interpretation, raw observations.

| Run | E-Class | A-Choice | R-Outcome | Breakpoint | Landmarks | Story? | Failure Mode |
|-----|---------|----------|-----------|------------|-----------|--------|--------------|
| 1 | | | | | | Y/N | |
| 2 | | | | | | Y/N | |
| 3 | | | | | | Y/N | |
| 4 | | | | | | Y/N | |
| 5 | | | | | | Y/N | |

**Field mapping to schema:**
- E-Class → `axis` (timing / density / geometry / resource / chaos)
- A-Choice → `deformation_mode` (shift / relocate / frequency / wrapper)
- R-Outcome → `envelope_classification` (inside / edge / outside)
- Breakpoint → `failure_mode`
- Failure Mode → triage key (vpr_collapse / rcp_smear / ear_breakdown / etc.)

---

## Pass / Fail Assessment

### PASS (system is real)

Even under stress:
- [ ] At least some full arcs still form
- [ ] At least 2 distinguishable A-grammars survive
- [ ] At least 1 stable R pattern appears
- [ ] Landmark recall persists in ≥1 run
- [ ] Breakpoints remain classifiable (not noise soup)

### PARTIAL FAILURE (tune, not rebuild)

- [ ] Story formation drops but doesn't disappear
- [ ] VPR collapses but RCP holds (or vice versa)
- [ ] E/A/R still visible but unstable

### SYSTEM FAILURE (stack not valid yet)

- [ ] No consistent E/A/R structure under stress
- [ ] No repeatable A behavior
- [ ] No R islands form
- [ ] Everything becomes indistinguishable chaos

---

## Post-Run (answer only this)

> "Where did phase continuity break first?"

_______________________________________________________________

---

## Triage

Once complete, run:

```bash
python scripts/triage.py <failure_signature> [<failure_signature> ...]
```

Valid signatures: `vpr_collapse` `rcp_smear` `ear_breakdown` `infinite_chase`
`decorative_adaptation` `single_path_adaptation` `memoryless_city`

Output gives you the first knob to tune. Fix that layer only before re-running.
