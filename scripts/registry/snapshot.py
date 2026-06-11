"""
registry/snapshot.py — default registry snapshot and move set for Chicago Chase.

Constructs RegistrySnapshot from triage.py event taxonomy and synthetic.py
grammar map. If triage.py or synthetic.py change their type sets, the
registry_hash changes automatically — no manual sync required.

Single source of truth for the default knob registry (pressure_gradient,
heat_decay_rate, visibility_window, closure_threshold).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

# Add scripts/ to path so triage + synthetic are importable from the subpackage.
sys.path.insert(0, str(Path(__file__).parent.parent))

from registry.runtime import RegistrySnapshot


def default_registry_snapshot() -> RegistrySnapshot:
    """
    Build a RegistrySnapshot from the live triage.py and synthetic.py state.

    Called once per artifact write cycle. Result is hashed to produce
    registry_hash in the RBB.
    """
    import triage as t
    from synthetic import GRAMMAR_TO_TYPES

    return RegistrySnapshot(
        e_types=sorted(t.E_TYPES),
        a_types=sorted(t.A_TYPES),
        r_types=sorted(t.R_TYPES),
        arc_grammar_map={k: sorted(v) for k, v in GRAMMAR_TO_TYPES.items()},
        resolution_conditions={
            "MIN_E_TO_R_SECONDS": t.MIN_E_TO_R_SECONDS,
            "requires_A": True,
        },
        knob_registry=_default_knob_registry(),
    )


def default_move_set() -> Dict[str, Any]:
    """
    Standard move set for the default sipmg_sweep.json knob space.

    move_set_hash is derived from this dict. Adding a knob or changing a
    range here changes the hash, creating a new AEC boundary.
    """
    return {
        "knobs": {
            "pressure_gradient": {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.5},
            "heat_decay_rate":   {"default": 1.0, "min": 0.0, "max": 6.0,  "step": 0.5},
            "visibility_window": {"default": 3.0, "min": 0.0, "max": 20.0, "step": 1.0},
            "closure_threshold": {"default": 0.5, "min": 0.0, "max": 1.0,  "step": 0.1},
        },
        "grammars": ["speed", "stealth", "decoy"],
    }


def _default_knob_registry() -> Dict[str, Any]:
    """Knob registry slice of default_move_set (stored in RegistrySnapshot)."""
    return {
        k: {"default": v["default"], "min": v["min"], "max": v["max"]}
        for k, v in default_move_set()["knobs"].items()
    }
