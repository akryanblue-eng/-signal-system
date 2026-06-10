"""
synthetic.py — parameterized event stream generator for closure suite.

Produces valid Chicago Chase event streams from ArcBlueprint specs.
Knob values map to generation parameters with built-in causal relationships:

  heat_decay_rate   → a_to_r delay (higher decay → R lands sooner)
  visibility_window → e_to_first_a (wider window → A appears sooner)
  pressure_gradient → heat_e delta and a_count (more pressure → more A)
  closure_threshold → a_to_r floor multiplier (higher threshold → stricter R gate)
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


GRAMMAR_TO_TYPES: Dict[str, List[str]] = {
    "speed":   ["route_change", "speed_shift", "vehicle_swap"],
    "stealth": ["stealth_break", "hide_enter", "terrain_exploit"],
    "decoy":   ["decoy_used", "vehicle_abandon"],
}

E_TYPES = [
    "line_of_sight_spotted", "pursuit_started", "rival_engaged",
    "vehicle_theft_detected", "heat_increase",
]

R_TYPES = [
    "pursuit_lost", "safehouse_reached", "arrest_confirmed",
    "heat_decay", "player_exit",
]


@dataclass
class ArcBlueprint:
    """Parameters for one arc."""
    e_type: str = "line_of_sight_spotted"
    a_grammar: str = "speed"
    a_count: int = 1
    r_type: str = "pursuit_lost"
    e_to_first_a: float = 5.0   # seconds to first A
    a_spacing: float = 2.0      # seconds between A events
    a_to_r: float = 10.0        # seconds from last A to R
    heat_e: float = 0.3
    heat_r: float = -0.5
    zone_id: str = "test_zone"
    include_null: bool = False
    close: bool = True          # False = open arc (no R)


@dataclass
class RunBlueprint:
    """Full synthetic run specification."""
    run_id: str
    arcs: List[ArcBlueprint] = field(default_factory=list)
    seed: Optional[int] = None


def knobs_to_arc_blueprint(
    knobs: Dict[str, float],
    base: Optional[ArcBlueprint] = None,
    a_grammar: str = "speed",
    r_type: str = "pursuit_lost",
) -> ArcBlueprint:
    """
    Map registry knob values onto ArcBlueprint parameters.

    Causal relationships:
      heat_decay_rate   ↑ → a_to_r ↓ (pressure decays faster → R lands sooner)
      visibility_window ↑ → e_to_first_a ↓ (wider window → A responds sooner)
      pressure_gradient ↑ → heat_e ↑, a_count ↑ (more pressure → more A needed)
      closure_threshold ↑ → a_to_r floor ↑ (stricter gate → longer R window)
    """
    bp = copy.deepcopy(base) if base else ArcBlueprint()
    bp.a_grammar = a_grammar
    bp.r_type = r_type

    hdr = float(knobs.get("heat_decay_rate", 1.0))
    vis = float(knobs.get("visibility_window", 3.0))
    pg  = float(knobs.get("pressure_gradient", 1.0))
    ct  = float(knobs.get("closure_threshold", 0.5))

    # Faster heat decay → R can land sooner (shorter a_to_r)
    bp.a_to_r = max(4.0, 14.0 / (hdr + 0.5))

    # Wider visibility window → A can respond sooner after E
    bp.e_to_first_a = max(1.5, 8.0 - vis * 0.6)

    # Higher pressure gradient → stronger E signal, more A events needed
    bp.heat_e = round(0.1 + pg * 0.12, 3)
    bp.a_count = max(1, int(1 + pg * 0.6))

    # Higher closure threshold = stricter R gate = longer required window
    # Expressed as a floor multiplier on a_to_r
    floor = 2.0 + ct * 6.0
    bp.a_to_r = max(bp.a_to_r, floor)

    return bp


def generate_run(bp: RunBlueprint) -> List[Dict[str, Any]]:
    """
    Generate a valid event stream from a RunBlueprint.

    Events are sorted by timestamp. Causal links are wired:
      E.contributes_to → each A event_id
      each A.triggered_by → E event_id
      R.triggered_by → all A event_ids
      each A.contributes_to → R event_id
    """
    rng = random.Random(bp.seed)
    events: List[Dict[str, Any]] = []
    ts: float = 0.0
    counter: int = 1

    def new_id() -> str:
        nonlocal counter
        eid = f"{bp.run_id}:{counter:03d}"
        counter += 1
        return eid

    def loc(zone: str) -> Dict[str, Any]:
        return {
            "zone_id": zone,
            "subzone": None,
            "x": round(rng.uniform(50.0, 200.0), 1),
            "y": round(rng.uniform(30.0, 100.0), 1),
        }

    for arc_bp in bp.arcs:
        # ── E event ───────────────────────────────────────────────────────────
        e_id = new_id()
        e_ev: Dict[str, Any] = {
            "event_id": e_id,
            "run_id": bp.run_id,
            "timestamp": round(ts, 2),
            "phase_hint": "E",
            "event_type": arc_bp.e_type,
            "source_system": "ai_police",
            "location": loc(arc_bp.zone_id),
            "entities": ["player_vehicle", "npc_police_01"],
            "tags": [],
            "payload": {"heat_delta": arc_bp.heat_e},
            "causal_links": {"triggered_by": [], "contributes_to": []},
        }
        events.append(e_ev)

        # ── Optional NULL ──────────────────────────────────────────────────────
        if arc_bp.include_null:
            ts += 1.5
            events.append({
                "event_id": new_id(),
                "run_id": bp.run_id,
                "timestamp": round(ts, 2),
                "phase_hint": "NULL",
                "event_type": "navigation_update",
                "source_system": "player",
                "location": loc(arc_bp.zone_id),
                "entities": ["player_vehicle"],
                "tags": [],
                "payload": {},
                "causal_links": {"triggered_by": [], "contributes_to": []},
            })

        # ── A events ──────────────────────────────────────────────────────────
        ts += arc_bp.e_to_first_a
        a_type_choices = GRAMMAR_TO_TYPES.get(arc_bp.a_grammar, ["route_change"])
        a_ids: List[str] = []
        a_evs: List[Dict[str, Any]] = []

        for i in range(arc_bp.a_count):
            a_id = new_id()
            a_type = a_type_choices[i % len(a_type_choices)]
            a_ev: Dict[str, Any] = {
                "event_id": a_id,
                "run_id": bp.run_id,
                "timestamp": round(ts, 2),
                "phase_hint": "A",
                "event_type": a_type,
                "source_system": "player",
                "location": loc(arc_bp.zone_id),
                "entities": ["player_vehicle"],
                "tags": [],
                "payload": {"speed": round(rng.uniform(40.0, 90.0), 1)},
                "causal_links": {"triggered_by": [e_id], "contributes_to": []},
            }
            e_ev["causal_links"]["contributes_to"].append(a_id)
            a_ids.append(a_id)
            a_evs.append(a_ev)
            events.append(a_ev)
            ts += arc_bp.a_spacing

        # ── R event ───────────────────────────────────────────────────────────
        if arc_bp.close:
            ts += arc_bp.a_to_r
            r_id = new_id()
            r_ev: Dict[str, Any] = {
                "event_id": r_id,
                "run_id": bp.run_id,
                "timestamp": round(ts, 2),
                "phase_hint": "R",
                "event_type": arc_bp.r_type,
                "source_system": "system",
                "location": loc(arc_bp.zone_id),
                "entities": ["player_vehicle"],
                "tags": ["arc_complete"],
                "payload": {"heat_delta": arc_bp.heat_r},
                "causal_links": {"triggered_by": a_ids[:], "contributes_to": []},
            }
            for a_ev in a_evs:
                a_ev["causal_links"]["contributes_to"].append(r_id)
            events.append(r_ev)
            ts += 3.0  # inter-arc gap

    events.sort(key=lambda ev: ev["timestamp"])
    return events
