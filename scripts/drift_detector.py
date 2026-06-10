#!/usr/bin/env python3
"""
Drift Detector v1
Global invariant: No promoted object without a traceable stress lineage.
No belief without a recorded stress event.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCHEMA_KEYS = {
    "id", "timestamp", "text", "name", "description", "type", "status",
    "evidence", "memory_driver", "intensity", "high_salience",
    "perturbation_refs", "attractor_refs", "story_refs", "constraint_ref",
    "axis", "intensity_applied", "deformation_mode", "identity_retained",
    "failure_mode", "fragility_notes", "envelope_classification",
    "trigger_recipe", "systems_intersection", "recurrence_count",
    "variation_survival", "collision_coherence", "last_tested",
    # session / calibration keys
    "tester_id", "duration_minutes",
    "q_one_breath", "q_regain_control", "q_clearest_place",
    "classifier_checks", "verdict", "verdict_notes",
    "describes_route_not_mission", "failure_produced_story_not_reset",
    "escape_has_location_mistake_recovery",
    "run_classified_without_rereading", "breakpoint_class_under_30s",
    # event stream keys
    "E", "loc", "entities", "state_delta", "heat", "visibility",
    "session_ref", "perturbation_ref",
    "$schema", "$id",
}


def load_dir(name: str) -> list[dict]:
    d = ROOT / name
    if not d.exists():
        return []
    return [json.loads(f.read_text()) for f in sorted(d.glob("*.json"))]


def check_orphan_attractors(attractors: list[dict]) -> list[str]:
    """Attractor with no linked story or no perturbation."""
    return [
        a["id"] for a in attractors
        if not a.get("story_refs") or not a.get("perturbation_refs")
    ]


def check_missing_deformation_chains(stories: list[dict], perturbations: list[dict]) -> list[str]:
    """Story used in attractor promotion but never referenced by any perturbation."""
    perturbed = {sid for p in perturbations for sid in p.get("story_refs", [])}
    return [
        s["id"] for s in stories
        if s.get("attractor_refs") and s["id"] not in perturbed
    ]


def check_unfalsified_constraints(constraints: list[dict]) -> list[str]:
    """Constraint marked active or stress_verified but has no perturbation log."""
    return [
        c["id"] for c in constraints
        if c.get("status") in ("active", "stress_verified")
        and not c.get("perturbation_refs")
    ]


def check_compression_hazards(attractors: list[dict]) -> list[str]:
    """Attractor with >=3 stories but 0 perturbations — unearned compression."""
    return [
        a["id"] for a in attractors
        if len(a.get("story_refs", [])) >= 3
        and not a.get("perturbation_refs")
    ]


def check_label_drift(all_objects: list[dict]) -> list[str]:
    """Keys in any JSON object not in the schema registry."""
    unknown = set()
    for obj in all_objects:
        for key in obj:
            if key not in SCHEMA_KEYS:
                unknown.add(key)
    return sorted(unknown)


def _section(label: str, items: list[str]) -> str:
    count = len(items)
    lines = [f"{label:<36}{count}"]
    for item in items:
        lines.append(f"  - {item}")
    return "\n".join(lines)


def main() -> int:
    stories = load_dir("stories")
    perturbations = load_dir("perturbations")
    constraints = load_dir("constraints")
    attractors = load_dir("attractors")
    sessions = load_dir("sessions")
    all_objects = stories + perturbations + constraints + attractors + sessions

    orphans = check_orphan_attractors(attractors)
    missing_chains = check_missing_deformation_chains(stories, perturbations)
    unfalsified = check_unfalsified_constraints(constraints)
    hazards = check_compression_hazards(attractors)
    label_drift = check_label_drift(all_objects)

    sep = "=" * 50
    print(sep)
    print("DRIFT REPORT")
    print(sep)
    print(_section("Orphan attractors:", orphans))
    print(_section("Unfalsified constraints:", unfalsified))
    print(_section("Missing deformation chains:", missing_chains))
    print(_section("Compression hazards:", hazards))
    print(_section("Label drift events:", label_drift))
    print(sep)

    total = len(orphans) + len(missing_chains) + len(unfalsified) + len(hazards) + len(label_drift)
    if total == 0:
        print("Clean. No drift detected.")
        return 0
    else:
        print(f"{total} issue(s) found. Fix before promoting any object.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
