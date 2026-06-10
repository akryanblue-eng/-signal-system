#!/usr/bin/env python3
"""
triage.py v0.1 — execution anchor

Binds:
  EventStream -> metrics -> breakpoint -> {VPR/RCP/coupling} -> structured knob diffs

Inputs:
  - Event stream: JSONL (one JSON object per line) OR a JSON array of events
  - Knob registry: JSON file (source-of-truth for knob metadata & constraints)
  - Optional current-knobs: JSON object of {knob_id: current_float_value}

Outputs:
  - One JSON object report (stdout), suitable for piping to a file.

Design constraints:
  - No new systems
  - No hidden dependencies
  - Registry is source-of-truth for knob metadata & validity
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ── Types ──────────────────────────────────────────────────────────────────────

class Axis(str, Enum):
    VPR = "VPR"          # A-width / policy-space integrity
    RCP = "RCP"          # R-depth / attractor formation integrity
    COUPLING = "COUPLING"  # E/A/R transition physics integrity


class Violation(str, Enum):
    VPR_VIOLATION = "VPR_VIOLATION"
    RCP_VIOLATION = "RCP_VIOLATION"
    COUPLING_FAILURE = "COUPLING_FAILURE"


@dataclass
class KnobSpec:
    knob_id: str
    name: str
    unit: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    axis: Optional[Axis] = None
    description: Optional[str] = None


@dataclass
class KnobDelta:
    knob_id: str
    knob_name: str
    axis: Optional[str]
    unit: Optional[str]
    old: Optional[float]
    new: Optional[float]
    delta: Optional[float]
    step: Optional[float]
    bounded: bool
    bounds: Optional[Dict[str, float]]
    reason: str
    evidence: Dict[str, Any]


@dataclass
class TriageReport:
    run_id: str
    created_at: str
    EAR: Dict[str, Any]
    breakpoint: str
    violations: List[str]
    metrics: Dict[str, Any]
    knob_deltas: List[KnobDelta]
    notes: Dict[str, Any]


# ── Registry loading ────────────────────────────────────────────────────────────

# Maps our internal layer names to Axis enum values for cross-format compatibility.
_LAYER_TO_AXIS: Dict[str, Optional[str]] = {
    "E": "COUPLING",
    "E→A": "COUPLING",
    "A": "VPR",
    "A→R": "VPR",
    "R": "RCP",
    "spatial": "VPR",
}


def load_registry(path: Path) -> Dict[str, KnobSpec]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    knobs = raw.get("knobs", raw)  # allow {"knobs": [...]} or {"knobs": {...}} or bare

    if isinstance(knobs, dict):
        items = []
        for knob_id, spec in knobs.items():
            if knob_id.startswith("_"):
                continue  # skip metadata keys like _version, _invariant
            s = dict(spec)
            s.setdefault("knob_id", knob_id)
            items.append(s)
        knobs = items

    out: Dict[str, KnobSpec] = {}
    for item in knobs:
        # Resolve axis: prefer explicit "axis" field; fall back to "layer" mapping.
        axis_raw = item.get("axis")
        if not axis_raw:
            axis_raw = _LAYER_TO_AXIS.get(item.get("layer", ""), None)

        axis_enum: Optional[Axis] = None
        if axis_raw and axis_raw in {a.value for a in Axis}:
            axis_enum = Axis(axis_raw)

        # Resolve min/max: prefer explicit fields; fall back to "range" array.
        rng = item.get("range")
        min_val = item.get("min")
        max_val = item.get("max")
        if rng and isinstance(rng, list) and len(rng) == 2:
            if min_val is None:
                min_val = float(rng[0])
            if max_val is None:
                max_val = float(rng[1])

        spec = KnobSpec(
            knob_id=str(item["knob_id"]),
            name=str(item.get("name") or item["knob_id"]),
            unit=item.get("unit"),
            min=float(min_val) if min_val is not None else None,
            max=float(max_val) if max_val is not None else None,
            step=float(item["step"]) if item.get("step") is not None else None,
            axis=axis_enum,
            description=item.get("description") or item.get("risk"),
        )
        out[spec.knob_id] = spec

    return out


# ── Event loading ───────────────────────────────────────────────────────────────

def iter_events_from_path(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        arr = json.loads(text)
        if not isinstance(arr, list):
            raise ValueError("Event file starts with '[' but is not a JSON array.")
        return arr
    events: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


# ── EAR extraction ──────────────────────────────────────────────────────────────

def compute_ear(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Phase-honest EAR summary.

    E: new constraint appearances only — NOT movement, NOT noise, NOT retro.
       Type prefixes: police_sightline, police_pursuit, pressure_*, heat_increase,
       rival_appear, e_* (explicit). Generic player_move does NOT count.

    A: control-logic deltas only — NOT movement, NOT activity, NOT noise.
       Requires adaptation=true flag OR adapt_* type prefix.
       player_move, player_*, move_* are logged for landmark tracking but
       do NOT increment A. This is the phase honesty invariant.

    R: locks when pressure measurably decays — NOT on timers, NOT proximity.
       Type prefixes: resolve_*, escape_*, arrest_*, heat_decay_start, r_*.
       Requires resolution field OR explicit decay-type prefix.
    """
    e_class: Optional[str] = None
    landmarks: List[str] = []
    adaptation_count = 0
    resolution_type: Optional[str] = None
    e_pressure = 0
    a_adapt = 0       # honest A: control-logic deltas only
    r_resolution = 0

    # E: specific constraint-appearance prefixes only — not generic heat_ events
    E_PREFIXES = ("police_sightline", "police_pursuit", "pressure_", "heat_increase",
                  "rival_appear", "e_")
    # R: pressure-decay and resolution events only — not end_ (ambiguous)
    R_PREFIXES = ("resolve_", "escape_", "arrest_", "heat_decay_start", "r_")

    for ev in events:
        et = str(ev.get("type", "")).lower()

        if e_class is None and ev.get("e_class"):
            e_class = str(ev["e_class"])
        if ev.get("landmark"):
            landmarks.append(str(ev["landmark"]))
        if ev.get("resolution"):
            resolution_type = str(ev["resolution"])

        # E: new constraint appearances
        if any(et.startswith(p) for p in E_PREFIXES):
            e_pressure += 1

        # A: control-logic deltas only — adaptation flag or adapt_ prefix required
        if ev.get("adaptation") is True or et.startswith("adapt_"):
            adaptation_count += 1
            a_adapt += 1

        # R: pressure-decay events only
        if any(et.startswith(p) for p in R_PREFIXES) or ev.get("resolution"):
            r_resolution += 1

    E = "PRESENT" if e_pressure > 0 else "ABSENT"
    A = adaptation_count
    R = (
        "LANDED" if resolution_type
        else ("FORMING" if r_resolution > 0 else "UNRESOLVED")
    )

    return {
        "E": E,
        "A": A,
        "R": R,
        "E_class": e_class,
        "landmarks": sorted(set(landmarks)),
        "resolution_type": resolution_type,
        "event_counts": {
            "E_pressure_events": e_pressure,
            "A_adaptation_events": a_adapt,   # renamed: honest count only
            "R_resolution_events": r_resolution,
            "total_events": len(events),
        },
    }


# ── Breakpoint classifier ───────────────────────────────────────────────────────

def classify_breakpoint(ear: Dict[str, Any]) -> str:
    """
    Single dominant breakpoint label. Keep the label set stable; add detail
    in metrics/notes, not by multiplying labels.
    Replace logic with your full breakpoint catalog as it solidifies.
    """
    if ear["E"] == "ABSENT":
        return "NoPressure_E_Absent"
    if ear["R"] == "UNRESOLVED":
        if ear["A"] <= 0:
            return "InstantCollapse"
        return "InfiniteChase"
    if ear["R"] == "LANDED" and ear["A"] <= 0:
        return "FreeEscape"
    return "FullArc"


# ── Violation checks ────────────────────────────────────────────────────────────

def eval_violations(ear: Dict[str, Any], metrics: Dict[str, Any]) -> List[Violation]:
    """
    Minimal placeholder gates. Replace with real measures:
      VPR  → TopA_share, ViableA_count
      RCP  → R clustering, return-stability index
      COUPLING → E→A latency, consequence fidelity
    """
    v: List[Violation] = []

    # COUPLING: pressure present, but zero control-logic deltas recorded
    # (E fired, A window never opened — structural pipeline failure)
    if ear["E"] == "PRESENT" and ear["event_counts"]["A_adaptation_events"] == 0:
        v.append(Violation.COUPLING_FAILURE)

    # RCP: pressure present, arc never resolves
    # (R island never forms — state-based exit conditions not met)
    if ear["E"] == "PRESENT" and ear["R"] == "UNRESOLVED":
        v.append(Violation.RCP_VIOLATION)

    # VPR (single-run stub): pressure present, no meaningful adaptation at all
    # NOTE: real VPR requires cross-run TopA_share — this is a placeholder
    # that flags complete A absence. Replace with multi-run diversity metric.
    if ear["E"] == "PRESENT" and ear["A"] == 0:
        v.append(Violation.VPR_VIOLATION)

    return v


# ── Knob diff engine ────────────────────────────────────────────────────────────

def clamp_to_bounds(value: float, spec: KnobSpec) -> Tuple[float, bool]:
    bounded = False
    if spec.min is not None and value < spec.min:
        value = spec.min
        bounded = True
    if spec.max is not None and value > spec.max:
        value = spec.max
        bounded = True
    return value, bounded


def quantize_to_step(value: float, spec: KnobSpec) -> float:
    if not spec.step:
        return value
    return round(value / spec.step) * spec.step


def propose_knob_diffs(
    registry: Dict[str, KnobSpec],
    current_knobs: Dict[str, float],
    breakpoint: str,
    violations: List[Violation],
    ear: Dict[str, Any],
) -> List[KnobDelta]:
    """
    Emits structured diffs. Every proposed change must reference a known
    registry knob_id. Outputs small, single-axis deltas only.

    Replace the mapping table below with your canonical wiring once the
    full breakpoint catalog is hardened.
    """
    deltas: List[KnobDelta] = []

    def add_delta(
        knob_id: str,
        delta: float,
        reason: str,
        evidence: Dict[str, Any],
    ) -> None:
        if knob_id not in registry:
            return  # unknown knob — skip silently rather than crashing the run
        spec = registry[knob_id]
        old = current_knobs.get(knob_id)
        new = (old if old is not None else (spec.min or 0.0)) + float(delta)
        new = quantize_to_step(new, spec)
        new, bounded = clamp_to_bounds(new, spec)
        deltas.append(KnobDelta(
            knob_id=spec.knob_id,
            knob_name=spec.name,
            axis=spec.axis.value if spec.axis else None,
            unit=spec.unit,
            old=old,
            new=new,
            delta=(new - old) if old is not None else None,
            step=spec.step,
            bounded=bounded,
            bounds=(
                {"min": spec.min, "max": spec.max}
                if (spec.min is not None or spec.max is not None) else None
            ),
            reason=reason,
            evidence=evidence,
        ))

    # ── Mapping table ──────────────────────────────────────────────────────────
    # Knob IDs must exist in registry. Replace with your full catalog mapping.

    if breakpoint == "InfiniteChase" or Violation.RCP_VIOLATION in violations:
        add_delta(
            knob_id="closure_threshold",
            delta=-0.05,
            reason="RCP: unresolved arcs under pressure — strengthen basin landing",
            evidence={
                "breakpoint": breakpoint,
                "resolution_type": ear.get("resolution_type"),
                "EAR": {"E": ear["E"], "R": ear["R"]},
            },
        )
        add_delta(
            knob_id="heat_decay_rate",
            delta=+0.05,
            reason="RCP: improve de-escalation path so resolution can land",
            evidence={"E_class": ear.get("E_class")},
        )

    if Violation.VPR_VIOLATION in violations:
        add_delta(
            knob_id="pressure_gradient",
            delta=+0.1,
            reason="VPR: no adaptation observed — increase pressure variation to force multiple grammars",
            evidence={
                "adaptation_count": ear.get("A"),
                "E_class": ear.get("E_class"),
            },
        )

    if Violation.COUPLING_FAILURE in violations:
        add_delta(
            knob_id="visibility_window",
            delta=+0.5,
            reason="Coupling: pressure present but no A events — widen perception/response window",
            evidence={"event_counts": ear.get("event_counts")},
        )

    return deltas[:6]  # hard cap: keep output short and reviewable


# ── Current knobs ───────────────────────────────────────────────────────────────

def load_current_knobs(path: Optional[Path]) -> Dict[str, float]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return {str(k): float(v) for k, v in raw.items() if not str(k).startswith("_")}
    raise ValueError("Current knobs file must be a JSON object: {knob_id: number, ...}")


# ── Main ────────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="triage.py v0.1 — EventStream → knob diffs via KnobRegistry"
    )
    ap.add_argument("--events", required=True, help="Events file (.jsonl or .json array)")
    ap.add_argument("--registry", required=True, help="Knob registry JSON")
    ap.add_argument("--current-knobs", default=None, help="JSON object of current knob values")
    ap.add_argument("--run-id", default=None, help="Run/session id (derived from events if omitted)")
    args = ap.parse_args(argv)

    registry = load_registry(Path(args.registry))
    events = iter_events_from_path(Path(args.events))
    current_knobs = load_current_knobs(Path(args.current_knobs) if args.current_knobs else None)

    ear = compute_ear(events)
    breakpoint_ = classify_breakpoint(ear)
    metrics: Dict[str, Any] = {
        "story": breakpoint_ == "FullArc",
        "ear_event_counts": ear.get("event_counts", {}),
        "landmark_count": len(ear.get("landmarks", [])),
        "adaptation_count": ear.get("A"),
    }
    violations = eval_violations(ear, metrics)
    knob_deltas = propose_knob_diffs(
        registry=registry,
        current_knobs=current_knobs,
        breakpoint=breakpoint_,
        violations=violations,
        ear=ear,
    )

    run_id = (
        args.run_id
        or str(events[0].get("session_id")) if events else None
        or Path(args.events).stem
    )

    report = TriageReport(
        run_id=run_id,
        created_at=datetime.utcnow().isoformat() + "Z",
        EAR=ear,
        breakpoint=breakpoint_,
        violations=[v.value for v in violations],
        metrics=metrics,
        knob_deltas=knob_deltas,
        notes={
            "registry_path": args.registry,
            "events_path": args.events,
            "current_knobs_path": args.current_knobs,
            "version": "triage.py v0.1",
        },
    )

    def encode(obj: Any) -> Any:
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        if isinstance(obj, Enum):
            return obj.value
        raise TypeError(f"Unserializable: {type(obj)}")

    json.dump(report, sys.stdout, default=encode, indent=2, sort_keys=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
