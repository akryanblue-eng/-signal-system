# Causal Admissibility Gate — CI Stanza v0.1

Sits between (3) stress suite and (4) SHIP/TUNE/KILL in the CI pipeline.
Extends the admissibility contract from "healthy shapes" to "earned transitions."

Global invariant this enforces:
> A causal link that adds no predictive lift over the marginal transition distribution is decorative. Decorative links do not count toward arc formation.

---

## 1. Link Lift Score (LLS)

**What it measures:** whether a declared causal edge `u → v` explains the transition to `v.event_type` better than the run-level base rate.

**Computation (per run, no external model required):**

```
For each directed edge u → v in a run's causal graph:
  baseline(v)   = P(v.event_type) across all events in run
  conditional(v) = P(v.event_type | u.event_type) across all edges of same u.event_type in run
  LLS(u→v)      = log( conditional(v) / baseline(v) )
                  (clamp to 0 when denominator is 0 or only one transition observed)
```

Per-run aggregates:
- `LLS_mean`: mean over all structural edges (E→A, A→R)
- `LLS_below_epsilon`: count of edges where LLS < ε (default ε = 0.1)
- `decorative_edge_rate`: LLS_below_epsilon / total_structural_edges

**Admissibility thresholds (tunable via KnobRegistry):**

| Threshold | Value | Description |
|---|---|---|
| `lls_floor` | 0.0 | Hard floor — edge with negative lift is a contradiction |
| `lls_warn`  | 0.1 | Soft floor — edge with near-zero lift is suspicious |
| `decorative_rate_max` | 0.30 | At most 30% of structural edges may be near-decorative per run |

---

## 2. Intervention Consistency Score (ICS)

**What it measures:** whether a knob perturbation shifts the causal edges it claims to own, in the expected direction, locally — not just as global VPR/RCP aggregates.

**Requires:** a paired run set — `(baseline_run, perturbed_run)` for each knob under test.

**Computation:**

Each knob in KnobRegistry has an `affects` field listing target subsystems (E/A/R/COUPLING). For a knob perturbation:

```
For each arc edge class claimed by knob.affects:
  expected_direction = sign of expected delta (e.g., wider E window = more E events per arc)
  observed_direction = sign of actual delta across (baseline_run, perturbed_run)
  edge_consistent   = (expected_direction == observed_direction)

ICS = (consistent_edges) / (total_claimed_edges)
```

**Admissibility thresholds:**

| Threshold | Value | Description |
|---|---|---|
| `ics_floor` | 0.60 | At least 60% of claimed edges must shift in expected direction |
| `ics_warn`  | 0.80 | Below 80% triggers TUNE even if VPR/RCP are green |

**Note:** ICS requires paired runs. When no perturbation baseline is available, ICS is reported as `null` and does not block SHIP. It blocks TUNE escalation to SHIP.

---

## 3. Drift Sentinel

**What it measures:** whether LLS and ICS are degrading over time while VPR/RCP stay green. That trajectory is the signature of correlation drift.

**Requires:** trailing window of N runs against a fixed scenario pack.

**Tripwire conditions (any one fires):**

| Condition | Signal |
|---|---|
| `decorative_edge_rate > 0.30` for 3 consecutive builds | CAUSAL_DRIFT |
| `ICS < ics_warn` while `VPR/RCP both passing` for 2 consecutive builds | SILENT_DRIFT |
| `LLS_mean` drops by >0.2 between builds | LIFT_COLLAPSE |

**Window size:** default N=100 runs. Configurable via `drift_window` in KnobRegistry.

**Sentinel outputs:**

```json
{
  "drift_status": "clean | CAUSAL_DRIFT | SILENT_DRIFT | LIFT_COLLAPSE",
  "trailing_decorative_rate": [<per-build values, last N>],
  "trailing_ics": [<per-build values, last N>],
  "trigger_build": "<build_id or null>"
}
```

---

## 4. Required CI Output Stanza

Added to `TriageReport` output. Schema:

```json
"causal_admissibility": {
  "LLS_mean": <float | null>,
  "decorative_edge_rate": <float | null>,
  "lls_below_epsilon": <int | null>,
  "ICS": <float | null>,
  "drift_status": "clean | CAUSAL_DRIFT | SILENT_DRIFT | LIFT_COLLAPSE | insufficient_data",
  "causal_verdict": "PASS | WARN | FAIL",
  "causal_notes": [<string>]
}
```

**causal_verdict derivation:**

| Condition | causal_verdict |
|---|---|
| LLS_mean >= lls_warn AND decorative_rate <= decorative_rate_max AND drift_status == "clean" | `PASS` |
| Any soft threshold breached OR drift sentinel triggered | `WARN` |
| Any LLS edge < lls_floor (contradiction) OR LIFT_COLLAPSE triggered | `FAIL` |
| Insufficient run count for LLS estimation (< 3 structural edges) | `PASS` with note |

---

## 5. Compound SHIP/TUNE/KILL Extension

Original gate (5 classifier_checks) is unchanged. Causal admissibility adds a sixth gate:

```
SHIP  requires: classifier_checks >= 4/5 AND causal_verdict == PASS AND no outside-envelope perturbations
TUNE  if:       causal_verdict == WARN OR (classifier_checks 2-3 AND causal_verdict != FAIL)
KILL  if:       causal_verdict == FAIL OR classifier_checks < 2
```

The causal gate cannot be bypassed by passing classifier_checks. A run that hits 5/5 checks with FAIL causal admissibility is still KILL.

---

## 6. What Is Not In This Gate

Intentionally excluded to preserve falsifiability:

- **Semantic validation** of edge content — only lift and consistency are measured, not "does this story make sense"
- **Cross-run narrative coherence** — that belongs in the Drift Sentinel's trailing window, not per-run scoring
- **Phase hint agreement** — phase_hint is inert and must never appear in this gate's inputs

---

## 7. Implementation Sequence

1. Add `compute_causal_admissibility(arcs, run_events)` to `triage.py` — emits LLS_mean, decorative_edge_rate, causal_verdict
2. Add `causal_admissibility` stanza to `TriageReport` dataclass
3. ICS requires paired runs — implement in `calibrate.py` as `--baseline-events` flag
4. Drift Sentinel requires run persistence — implement as `drift_store/` directory with rolling JSONL per scenario

Steps 1-2 are self-contained in a single run. Steps 3-4 require multi-run infrastructure.
