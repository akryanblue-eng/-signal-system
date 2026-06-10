#!/usr/bin/env python3
"""
triage.py v2.1 — arc-first kernel + A3 fix + ASI

Changes from v2.0:
  - A3 fix: R is now a proposed state, not an executed state.
    R events collect into arc.r_candidates; select_resolution() promotes
    the best candidate only if arc.has_a AND dt >= MIN_E_TO_R_SECONDS.
    Arcs that resolve before adaptation window opens stay open (no R).
  - Arc.first_e_ts tracks E arrival time for window computation.
  - compute_rcp() gains p_r_without_a and mean_e_to_r_time.
  - compute_asi() collapses RCP into a single Arc Stability Index scalar
    with regime classification: healthy / tuning / imbalanced / non_system.
  - ASI is diagnostic only — not an optimization target.

Three hard invariants (unchanged):
  1. event_type is phase authority — phase_hint is advisory.
  2. A only counts when causally linked to a prior E.
  3. Arc = contiguous causal cluster (BFS on causal_links graph).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ── Phase taxonomy (event_type is authority) ───────────────────────────────────

E_TYPES: Set[str] = {
    "heat_increase", "line_of_sight_spotted", "vehicle_theft_detected",
    "pursuit_started", "rival_engaged", "blockade_spawned", "collision_detected",
}

A_TYPES: Set[str] = {
    "route_change", "vehicle_swap", "vehicle_abandon", "stealth_break",
    "hide_enter", "decoy_used", "speed_shift", "terrain_exploit",
}

R_TYPES: Set[str] = {
    "heat_decay", "pursuit_lost", "safehouse_reached", "arrest_confirmed",
    "timeout_decay", "player_exit",
}

NULL_TYPES: Set[str] = {"ai_idle", "ambient_simulation", "navigation_update"}

A_GRAMMAR: Dict[str, str] = {
    "route_change": "speed",
    "vehicle_swap": "speed",
    "vehicle_abandon": "decoy",
    "stealth_break": "stealth",
    "hide_enter": "stealth",
    "decoy_used": "decoy",
    "speed_shift": "speed",
    "terrain_exploit": "stealth",
}

# Adaptation window floor. R candidates are rejected if E→R delta < this.
# Medium vertical slice default. Register in KnobRegistry when pairing with live runs.
MIN_E_TO_R_SECONDS: float = 8.0


# ── Knob registry types ────────────────────────────────────────────────────────

_LAYER_TO_AXIS: Dict[str, Optional[str]] = {
    "E": "COUPLING", "E→A": "COUPLING", "A": "VPR",
    "A→R": "VPR", "R": "RCP", "spatial": "VPR",
}


class Axis(str, Enum):
    VPR = "VPR"
    RCP = "RCP"
    COUPLING = "COUPLING"


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


# ── Arc ────────────────────────────────────────────────────────────────────────

@dataclass
class Arc:
    run_id: str
    arc_index: int
    arc_id: str = ""
    E_events: List[Dict[str, Any]] = field(default_factory=list)
    A_events: List[Dict[str, Any]] = field(default_factory=list)
    A_decorative: List[Dict[str, Any]] = field(default_factory=list)
    R_events: List[Dict[str, Any]] = field(default_factory=list)
    # R candidates: all R-typed events in cluster. select_resolution() promotes at most one.
    r_candidates: List[Dict[str, Any]] = field(default_factory=list)
    phase_overrides: List[str] = field(default_factory=list)
    breakpoint: str = ""
    trust_scores: Dict[str, float] = field(default_factory=dict)
    # Timestamp of first E event; used for E→R window validation.
    first_e_ts: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.arc_id:
            self.arc_id = f"{self.run_id}:arc{self.arc_index}"

    @property
    def has_e(self) -> bool:
        return bool(self.E_events)

    @property
    def has_a(self) -> bool:
        return bool(self.A_events)

    @property
    def has_r(self) -> bool:
        return bool(self.R_events)

    @property
    def is_full(self) -> bool:
        return self.has_e and self.has_a and self.has_r


@dataclass
class TriageReport:
    run_id: str
    created_at: str
    arcs: List[Arc]
    breakpoint: str
    violations: List[str]
    vpr: Dict[str, Any]
    rcp: Dict[str, Any]
    asi: Dict[str, Any]
    apc: Dict[str, Any]
    knob_deltas: List[KnobDelta]
    notes: Dict[str, Any]


# ── Registry loading ────────────────────────────────────────────────────────────

def load_registry(path: Path) -> Dict[str, KnobSpec]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    knobs = raw.get("knobs", raw)
    if isinstance(knobs, dict):
        items = []
        for knob_id, spec in knobs.items():
            if knob_id.startswith("_"):
                continue
            s = dict(spec)
            s.setdefault("knob_id", knob_id)
            items.append(s)
        knobs = items
    out: Dict[str, KnobSpec] = {}
    for item in knobs:
        axis_raw = item.get("axis") or _LAYER_TO_AXIS.get(item.get("layer", ""), None)
        axis_enum = Axis(axis_raw) if axis_raw and axis_raw in {a.value for a in Axis} else None
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


# ── Event classification ───────────────────────────────────────────────────────

def phase_from_type(ev: Dict[str, Any]) -> str:
    et = ev.get("event_type", "")
    if et in E_TYPES:
        return "E"
    if et in A_TYPES:
        return "A"
    if et in R_TYPES:
        return "R"
    return "NULL"


def get_phase_hint(ev: Dict[str, Any]) -> str:
    """Read phase_hint (v2.0) with fallback to phase (v1.0 compat)."""
    return ev.get("phase_hint", ev.get("phase", "NULL"))


def validate_event(ev: Dict[str, Any]) -> bool:
    for f in ("event_id", "event_type", "run_id", "timestamp"):
        if f not in ev:
            return False
    true_phase = phase_from_type(ev)
    if true_phase in ("E", "A", "R") and not ev.get("causal_links"):
        return False
    return True


def score_event_trust(ev: Dict[str, Any]) -> float:
    """
    Trust score for phase assignment. Scale 0–3.0.
    +1 base, +1 payload corroborates, +1 causal evidence, -1 phase_hint mismatch.
    """
    true_phase = phase_from_type(ev)
    declared_phase = get_phase_hint(ev)
    payload = ev.get("payload") or {}
    cl = ev.get("causal_links") or {}

    score = 1.0
    heat_delta = payload.get("heat_delta", 0)
    if true_phase == "E" and heat_delta > 0:
        score += 1.0
    elif true_phase == "R" and heat_delta < 0:
        score += 1.0
    elif true_phase == "A" and ev.get("event_type") in A_TYPES:
        score += 1.0

    if cl.get("triggered_by"):
        score += 1.0

    if declared_phase != true_phase and declared_phase != "NULL":
        score -= 1.0

    return max(0.0, score)


# ── R candidate selection (A3 fix) ────────────────────────────────────────────

def select_resolution(arc: Arc, min_e_to_r: float = MIN_E_TO_R_SECONDS) -> None:
    """
    Promote the first admissible R candidate to arc.R_events.

    R is a proposed state, not an executed state. Admissibility gate:
      - arc.has_a must be True (adaptation window opened)
      - dt = r.timestamp - arc.first_e_ts >= min_e_to_r (time sufficient)

    If no candidate passes, R_events stays empty. The arc remains open
    and classifies as infinite_chase or instant_collapse depending on A.

    r_candidates is preserved for diagnostics regardless of outcome.
    """
    if not arc.r_candidates:
        return
    for r in arc.r_candidates:
        r_ts = float(r.get("timestamp", 0))
        dt = (r_ts - arc.first_e_ts) if arc.first_e_ts is not None else 0.0
        if arc.has_a and dt >= min_e_to_r:
            arc.R_events = [r]
            return


# ── Arc formation via causal clustering ────────────────────────────────────────

def build_arcs(events: List[Dict[str, Any]], min_e_to_r: float = MIN_E_TO_R_SECONDS) -> List[Arc]:
    """
    Build arcs via causal graph clustering (v2.0 approach).

    Algorithm:
    1. Index and validate events.
    2. Build undirected adjacency from triggered_by + contributes_to.
    3. BFS to find connected components — each with an E event becomes a cluster.
    4. Sort clusters by earliest timestamp.
    5. Within each cluster, assign events by event_type authority.
       A events require triggered_by to intersect cluster's E ids (else decorative).
       R events go to r_candidates.
    6. Call select_resolution() to gate R against A-window.
    7. Log phase_hint mismatches in arc.phase_overrides.
    """
    ev_index: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        if validate_event(ev):
            ev_index[ev["event_id"]] = ev

    if not ev_index:
        return []

    # Build undirected adjacency
    adjacency: Dict[str, Set[str]] = defaultdict(set)
    for eid, ev in ev_index.items():
        cl = ev.get("causal_links") or {}
        for parent_id in cl.get("triggered_by", []):
            if parent_id in ev_index:
                adjacency[eid].add(parent_id)
                adjacency[parent_id].add(eid)
        for child_id in cl.get("contributes_to", []):
            if child_id in ev_index:
                adjacency[eid].add(child_id)
                adjacency[child_id].add(eid)

    # BFS: find connected components
    visited: Set[str] = set()
    clusters: List[List[str]] = []
    for eid in ev_index:
        if eid not in visited:
            component: List[str] = []
            queue = [eid]
            while queue:
                cur = queue.pop(0)
                if cur in visited:
                    continue
                visited.add(cur)
                component.append(cur)
                queue.extend(adjacency[cur] - visited)
            clusters.append(component)

    # Filter to E-bearing clusters, sort by earliest timestamp
    def cluster_min_ts(c: List[str]) -> float:
        return min(float(ev_index[eid].get("timestamp", 0)) for eid in c)

    arc_clusters = [
        c for c in clusters
        if any(phase_from_type(ev_index[eid]) == "E" for eid in c)
    ]
    arc_clusters.sort(key=cluster_min_ts)

    run_id = next(iter(ev_index.values())).get("run_id", "unknown")
    arcs: List[Arc] = []

    for arc_idx, cluster in enumerate(arc_clusters, 1):
        cluster_evs = sorted(
            [ev_index[eid] for eid in cluster],
            key=lambda ev: float(ev.get("timestamp", 0)),
        )

        arc = Arc(run_id=run_id, arc_index=arc_idx)
        arc_e_ids: Set[str] = set()

        for ev in cluster_evs:
            eid = ev["event_id"]
            true_phase = phase_from_type(ev)
            declared = get_phase_hint(ev)

            arc.trust_scores[eid] = score_event_trust(ev)

            if declared != true_phase and declared != "NULL":
                arc.phase_overrides.append(eid)

            if true_phase == "E":
                arc.E_events.append(ev)
                arc_e_ids.add(eid)
                if arc.first_e_ts is None:
                    arc.first_e_ts = float(ev.get("timestamp", 0))
            elif true_phase == "A":
                triggered_by = set((ev.get("causal_links") or {}).get("triggered_by", []))
                if triggered_by & arc_e_ids:
                    arc.A_events.append(ev)
                else:
                    arc.A_decorative.append(ev)
            elif true_phase == "R":
                arc.r_candidates.append(ev)

        select_resolution(arc, min_e_to_r)
        arc.breakpoint = classify_arc(arc)
        arcs.append(arc)

    return arcs


# ── Breakpoint classifier ───────────────────────────────────────────────────────

def classify_arc(arc: Arc) -> str:
    if not arc.has_e:
        return "collapsed_arc"
    if not arc.has_r:
        if arc.has_a:
            return "infinite_chase"
        return "instant_collapse"
    r_type = arc.R_events[0].get("event_type", "")
    if not arc.has_a:
        return "free_escape" if r_type in ("pursuit_lost", "safehouse_reached") else "collapsed_arc"
    if arc.is_full:
        total_a = len(arc.A_events) + len(arc.A_decorative)
        if total_a > 0 and len(arc.A_decorative) / total_a > 0.6:
            return "decorative_adaptation"
        return "full_arc"
    return "partial_arc"


def classify_breakpoint(arcs: List[Arc]) -> str:
    if not arcs:
        return "no_arcs"
    counts = Counter(arc.breakpoint for arc in arcs)
    return counts.most_common(1)[0][0]


# ── VPR (A-space diversity) ────────────────────────────────────────────────────

def compute_vpr(arcs: List[Arc]) -> Dict[str, Any]:
    grammar_counts: Dict[str, int] = {"stealth": 0, "speed": 0, "decoy": 0, "unknown": 0}
    e_to_grammars: Dict[str, Set[str]] = defaultdict(set)

    for arc in arcs:
        arc_grammars: Set[str] = set()
        for ev in arc.A_events:
            g = A_GRAMMAR.get(ev.get("event_type", ""), "unknown")
            grammar_counts[g] += 1
            arc_grammars.add(g)
        for e_ev in arc.E_events:
            e_type = e_ev.get("event_type", "unknown")
            e_to_grammars[e_type].update(arc_grammars)

    total_a = sum(grammar_counts.values())
    top_share = (max(grammar_counts.values()) / total_a) if total_a > 0 else 0.0
    viable = sum(1 for g, c in grammar_counts.items() if c > 0 and g != "unknown")

    return {
        "ViableA_count": viable,
        "TopA_share": round(top_share, 3),
        "A_grammars": {
            g: round(grammar_counts[g] / total_a, 3) if total_a > 0 else 0.0
            for g in ("stealth", "speed", "decoy")
        },
        "SameE_diversity": {
            et: (len(gs) > 1) for et, gs in e_to_grammars.items()
        },
        "violation_flag": top_share > 0.7,
    }


# ── RCP (R-basin coherence) ────────────────────────────────────────────────────

def compute_rcp(arcs: List[Arc]) -> Dict[str, Any]:
    if not arcs:
        return {
            "arc_count": 0, "arc_clusters": 0,
            "cluster_stability": 0.0,
            "compressibility_score": 0.0,
            "smear_index": 1.0,
            "R_type_counts": {},
            "p_r_without_a": 1.0,
            "mean_e_to_r_time": 0.0,
        }

    r_type_counts: Dict[str, int] = Counter(
        arc.R_events[0].get("event_type", "unknown")
        for arc in arcs if arc.has_r
    )
    landed = sum(1 for arc in arcs if arc.has_r)
    compressibility = landed / len(arcs)
    arc_clusters = len(set(arc.breakpoint for arc in arcs))

    # P(R | A == 0): resolution without adaptation
    r_without_a = sum(1 for arc in arcs if arc.has_r and not arc.has_a)
    p_r_without_a = (r_without_a / landed) if landed > 0 else 0.0

    # Mean E→R window time (arcs with both E and R)
    e_to_r_times = []
    for arc in arcs:
        if arc.has_r and arc.first_e_ts is not None:
            r_ts = float(arc.R_events[0].get("timestamp", 0))
            e_to_r_times.append(r_ts - arc.first_e_ts)
    mean_e_to_r = sum(e_to_r_times) / len(e_to_r_times) if e_to_r_times else 0.0

    return {
        "arc_count": len(arcs),
        "arc_clusters": arc_clusters,
        "cluster_stability": 0.0,  # needs cross-run data
        "compressibility_score": round(compressibility, 3),
        "smear_index": round(1.0 - compressibility, 3),
        "R_type_counts": dict(r_type_counts),
        "p_r_without_a": round(p_r_without_a, 3),
        "mean_e_to_r_time": round(mean_e_to_r, 3),
    }


# ── ASI (Arc Stability Index) ──────────────────────────────────────────────────

def compute_asi(arcs: List[Arc], rcp: Dict[str, Any], min_e_to_r: float = MIN_E_TO_R_SECONDS) -> Dict[str, Any]:
    """
    Arc Stability Index v0.1 — single scalar for CI arc health gate.

    Components:
      r_diversity   (0.30): R island richness — attractor variety
      r_legitimacy  (0.30): 1 - P(R|A==0) — closures must be earned
      r_tempo       (0.25): mean E→R time / min_e_to_r — window sufficiency
      r_entropy     (0.15): normalized R-type distribution entropy

    ASI is a diagnostic scalar, NOT an optimization target.
    Optimizing ASI directly will flatten diversity and destroy VPR.

    Regimes:
      >= 0.75  healthy    — stable arcs, multiple R basins, A window open
      >= 0.55  tuning     — one axis weak, usually tempo or legitimacy
      >= 0.35  imbalanced — premature R locking or single-basin collapse
       < 0.35  non_system — arcs not forming
    """
    # R diversity: attractor variety (3 island types = full score)
    r_island_count = len(rcp.get("R_type_counts", {}))
    r_diversity = min(r_island_count / 3.0, 1.0)

    # R legitimacy: penalize closures without adaptation
    p_r_without_a = rcp.get("p_r_without_a", 1.0)
    r_legitimacy = 1.0 - p_r_without_a

    # R temporal sufficiency: E→R window vs floor
    mean_e_to_r = rcp.get("mean_e_to_r_time", 0.0)
    r_tempo = min(mean_e_to_r / min_e_to_r, 1.0) if min_e_to_r > 0 else 0.0

    # R entropy: normalized distribution entropy across R types
    r_counts = rcp.get("R_type_counts", {})
    total_r = sum(r_counts.values())
    r_entropy = 0.0
    if total_r > 0 and len(r_counts) > 1:
        raw = -sum((c / total_r) * math.log2(c / total_r) for c in r_counts.values() if c > 0)
        r_entropy = raw / math.log2(len(r_counts))

    asi = (
        0.30 * r_diversity +
        0.30 * r_legitimacy +
        0.25 * r_tempo +
        0.15 * r_entropy
    )
    asi = round(asi, 3)

    if asi >= 0.75:
        regime = "healthy"
    elif asi >= 0.55:
        regime = "tuning"
    elif asi >= 0.35:
        regime = "imbalanced"
    else:
        regime = "non_system"

    return {
        "asi": asi,
        "regime": regime,
        "components": {
            "r_diversity": round(r_diversity, 3),
            "r_legitimacy": round(r_legitimacy, 3),
            "r_tempo": round(r_tempo, 3),
            "r_entropy": round(r_entropy, 3),
        },
        "inputs": {
            "r_island_count": r_island_count,
            "p_r_without_a": round(p_r_without_a, 3),
            "mean_e_to_r_time": round(mean_e_to_r, 3),
            "min_e_to_r_floor": min_e_to_r,
        },
    }


# ── APC (Arc Phase Coherence) ─────────────────────────────────────────────────

def compute_apc(arcs: List[Arc], low_tau: float = 0.3) -> Dict[str, Any]:
    """
    Arc Phase Coherence v0.1 — detects A disappearing while R looks healthy.

    Per-arc: participation_ratio = A_span_dt / E_to_R_dt
      where A_span_dt = time from first A event to R (0 if no A).
    APC_arc = has_A * participation_ratio

    Guards the failure mode: R looks structurally fine but A is a late blip
    or absent entirely. APC_zero_share rising while RCP is green = A3 signature.

    CI guardrails:
      KILL  if APC_zero_share > 0.30
      TUNE  if APC_zero_share in (0.15, 0.30] OR APC_mean < 0.25
      SHIP  only if APC_zero_share <= 0.15 AND APC_mean >= 0.30
    """
    r_arcs = [arc for arc in arcs if arc.has_r]
    if not r_arcs:
        return {
            "APC_mean": None,
            "APC_zero_share": None,
            "APC_low_share": None,
            "apc_verdict": "insufficient_data",
            "per_arc": [],
        }

    per_arc = []
    for arc in r_arcs:
        r_ts = float(arc.R_events[0].get("timestamp", 0))
        e_to_r_dt = (r_ts - arc.first_e_ts) if arc.first_e_ts is not None else 0.0

        if arc.has_a and e_to_r_dt > 0:
            first_a_ts = float(arc.A_events[0].get("timestamp", 0))
            a_span_dt = r_ts - first_a_ts
            participation = max(a_span_dt / e_to_r_dt, 0.0)
        else:
            participation = 0.0

        apc_arc = participation if arc.has_a else 0.0
        per_arc.append({"arc_id": arc.arc_id, "apc": round(apc_arc, 3), "e_to_r_dt": round(e_to_r_dt, 3)})

    scores = [p["apc"] for p in per_arc]
    apc_mean = sum(scores) / len(scores)
    zero_share = sum(1 for s in scores if s == 0.0) / len(scores)
    low_share = sum(1 for s in scores if s < low_tau) / len(scores)

    if zero_share > 0.30:
        verdict = "KILL"
    elif zero_share > 0.15 or apc_mean < 0.25:
        verdict = "TUNE"
    else:
        verdict = "SHIP"

    return {
        "APC_mean": round(apc_mean, 3),
        "APC_zero_share": round(zero_share, 3),
        "APC_low_share": round(low_share, 3),
        "apc_verdict": verdict,
        "per_arc": per_arc,
    }


# ── Violations ─────────────────────────────────────────────────────────────────

def eval_violations(
    arcs: List[Arc],
    vpr: Dict[str, Any],
    rcp: Dict[str, Any],
) -> List[Violation]:
    v: List[Violation] = []

    if any(arc.has_e and not arc.has_a for arc in arcs):
        v.append(Violation.COUPLING_FAILURE)

    if any(arc.has_e and not arc.has_r for arc in arcs):
        v.append(Violation.RCP_VIOLATION)

    if vpr.get("violation_flag"):
        v.append(Violation.VPR_VIOLATION)

    return v


# ── Knob diffs ─────────────────────────────────────────────────────────────────

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
    arcs: List[Arc],
    vpr: Dict[str, Any],
    rcp: Dict[str, Any],
) -> List[KnobDelta]:
    deltas: List[KnobDelta] = []

    def add_delta(knob_id: str, delta: float, reason: str, evidence: Dict[str, Any]) -> None:
        if knob_id not in registry:
            return
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

    if breakpoint in ("infinite_chase",) or Violation.RCP_VIOLATION in violations:
        add_delta(
            "closure_threshold", -0.05,
            reason="RCP: arc(s) unresolved — strengthen basin landing",
            evidence={"breakpoint": breakpoint, "smear_index": rcp.get("smear_index")},
        )
        add_delta(
            "heat_decay_rate", +0.05,
            reason="RCP: improve de-escalation so R can land",
            evidence={"arc_count": rcp.get("arc_count")},
        )

    if Violation.VPR_VIOLATION in violations:
        add_delta(
            "pressure_gradient", +0.1,
            reason="VPR: A-grammar collapse — increase E variation to force diversity",
            evidence={"TopA_share": vpr.get("TopA_share"), "ViableA_count": vpr.get("ViableA_count")},
        )

    if Violation.COUPLING_FAILURE in violations:
        add_delta(
            "visibility_window", +0.5,
            reason="Coupling: E present but A window never opened — widen response window",
            evidence={"coupling_fail_arcs": sum(1 for arc in arcs if arc.has_e and not arc.has_a)},
        )

    return deltas[:6]


# ── Misc ────────────────────────────────────────────────────────────────────────

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
        description="triage.py v2.1 — arc-first + A3 fix + ASI. EventStream → arcs → VPR/RCP/ASI → knob diffs"
    )
    ap.add_argument("--events", required=True, help="Events file (.jsonl or .json array)")
    ap.add_argument("--registry", required=True, help="Knob registry JSON")
    ap.add_argument("--current-knobs", default=None, help="JSON object of current knob values")
    ap.add_argument("--run-id", default=None, help="Run id (derived from events if omitted)")
    ap.add_argument(
        "--min-e-to-r", type=float, default=MIN_E_TO_R_SECONDS,
        help=f"Minimum E→R window in seconds for R admissibility (default: {MIN_E_TO_R_SECONDS})"
    )
    args = ap.parse_args(argv)

    registry = load_registry(Path(args.registry))
    events = iter_events_from_path(Path(args.events))
    current_knobs = load_current_knobs(Path(args.current_knobs) if args.current_knobs else None)

    arcs = build_arcs(events, min_e_to_r=args.min_e_to_r)
    breakpoint_ = classify_breakpoint(arcs)
    vpr = compute_vpr(arcs)
    rcp = compute_rcp(arcs)
    asi = compute_asi(arcs, rcp, min_e_to_r=args.min_e_to_r)
    apc = compute_apc(arcs)
    violations = eval_violations(arcs, vpr, rcp)
    knob_deltas = propose_knob_diffs(
        registry, current_knobs, breakpoint_, violations, arcs, vpr, rcp
    )

    run_id = (
        args.run_id
        or (str(events[0].get("run_id")) if events else None)
        or Path(args.events).stem
    )

    report = TriageReport(
        run_id=run_id,
        created_at=datetime.utcnow().isoformat() + "Z",
        arcs=arcs,
        breakpoint=breakpoint_,
        violations=[v.value for v in violations],
        vpr=vpr,
        rcp=rcp,
        asi=asi,
        apc=apc,
        knob_deltas=knob_deltas,
        notes={
            "registry_path": args.registry,
            "events_path": args.events,
            "current_knobs_path": args.current_knobs,
            "version": "triage.py v2.1",
            "arc_count": len(arcs),
            "phase_overrides": sum(len(arc.phase_overrides) for arc in arcs),
            "min_e_to_r": args.min_e_to_r,
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
