"""
registry/runtime.py — RegistrySnapshot: world registry state at a point in time.

A RegistrySnapshot captures the semantic model of the world: what events are
valid, what arc grammar is active, what conditions gate resolution, and what
knobs exist. It is NOT the instrument code (that's the VCL). It is the ontology.

Two runs with the same RegistrySnapshot are in the same AEC (modulo move_set).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class RegistrySnapshot:
    """
    Immutable snapshot of the world registry.

    Hashed to produce registry_hash in the RBB. If any field changes, the
    hash changes, and artifacts from the old and new snapshots cannot be
    aggregated without a Gatekeeper BLOCK.
    """

    # Event type taxonomy — phase authority (matches triage.py sets)
    e_types: List[str] = field(default_factory=list)
    a_types: List[str] = field(default_factory=list)
    r_types: List[str] = field(default_factory=list)

    # Arc grammar map: grammar name → valid A event_types for that grammar
    arc_grammar_map: Dict[str, List[str]] = field(default_factory=dict)

    # Resolution gate conditions (triage.py MIN_E_TO_R_SECONDS, requires_A, etc.)
    resolution_conditions: Dict[str, Any] = field(default_factory=dict)

    # Knob registry: knob_id → {default, min, max}
    knob_registry: Dict[str, Any] = field(default_factory=dict)
