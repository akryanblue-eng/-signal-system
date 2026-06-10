#!/usr/bin/env python3
"""
Post-Stress Triage v2
Input: one or more failure signatures observed in a stress run
Output: ordered triage report + structured knob diffs from KnobRegistry

Master rule: E > A > R > VPR > RCP
Never fix a downstream layer before the upstream cause is stable.
Triage never recommends content changes — only parameter edits from KnobRegistry.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "schemas" / "knob_registry.json"

LAYER_ORDER = ["E", "E→A", "A", "A→R", "R", "spatial"]

# Maps failure signature → which knobs to edit (registry keys) + direction
FAILURE_MAP: dict[str, dict] = {
    "vpr_collapse": {
        "label": "VPR Collapse (A-space attack)",
        "signature": "TopA_share > 0.7 — one dominant strategy, 'optimal path' emerged",
        "broken_layer": "E",
        "first_knob_concept": "E variability — NOT A-space itself",
        "why": "A-collapse means E is too narrow. System overfits to one response when pressure is predictable.",
        "registry_edits": [
            {"knob": "spawn_delay_variance", "direction": "+", "note": "Desync pressure onset"},
            {"knob": "encounter_start_angle_variance", "direction": "+", "note": "Force new first-move decisions"},
        ],
        "expected": "A naturally re-diversifies once E stops forcing a single optimal response.",
        "classifier_output": "VPR_VIOLATION",
    },
    "rcp_smear": {
        "label": "RCP Smear (R-space collapse)",
        "signature": "No compressible arcs — cannot summarize runs cleanly — 'it just happened'",
        "broken_layer": "R",
        "first_knob_concept": "R closure strength — not R options",
        "why": "Stories need state-dependent endings. Time-based or random exits produce smear.",
        "registry_edits": [
            {"knob": "heat_decay_threshold", "direction": "-", "note": "Escape becomes state-driven, not time-driven"},
            {"knob": "pursuit_break_strength", "direction": "+", "note": "Require combined condition: LoS + distance + zone"},
        ],
        "expected": "Story arcs begin clustering into repeatable islands.",
        "classifier_output": "RCP_VIOLATION",
    },
    "ear_breakdown": {
        "label": "E/A/R Breakdown (phase continuity collapse)",
        "signature": "E fires with no A window; A exists but doesn't change R; R has no causal link",
        "broken_layer": "E→A",
        "first_knob_concept": "Time-to-adaptation window — not difficulty, not balance",
        "why": "Phase continuity breaks when players cannot react before consequences lock.",
        "registry_edits": [
            {"knob": "police_response_delay", "direction": "+", "note": "Open decision window after escalation onset"},
        ],
        "expected": "E → A → R chain becomes readable again.",
        "classifier_output": "COUPLING_FAILURE",
    },
    "infinite_chase": {
        "label": "Infinite Chase (R never stabilizes)",
        "signature": "Runs continue too long or loop — no clean resolution point",
        "broken_layer": "R",
        "first_knob_concept": "R termination clarity — closure triggers",
        "why": "Arcs oscillate when R conditions are ambiguous or time-based.",
        "registry_edits": [
            {"knob": "pursuit_break_strength", "direction": "+", "note": "Enforce distance + LoS + zone exit combined"},
            {"knob": "loose_coupling_noise", "direction": "-", "note": "Reduce R oscillation"},
        ],
        "expected": "Arcs terminate cleanly into identifiable endings.",
        "classifier_output": "RCP_VIOLATION",
    },
    "decorative_adaptation": {
        "label": "Decorative Adaptation (A present, non-causal)",
        "signature": "Players act a lot but outcomes barely change — adaptation feels cosmetic",
        "broken_layer": "A→R",
        "first_knob_concept": "A→R causal leverage — coupling strength",
        "why": "A becomes leverage only when wrong choices degrade position.",
        "registry_edits": [
            {"knob": "rival_aggression", "direction": "+", "note": "Increase consequence sensitivity to A choices"},
        ],
        "expected": "Adaptation becomes leverage. Players feel consequences of choice.",
        "classifier_output": "COUPLING_FAILURE",
    },
    "single_path_adaptation": {
        "label": "Single-Path Adaptation (strategy collapse)",
        "signature": "One dominant escape grammar across runs — other A-grammars go unused",
        "broken_layer": "A",
        "first_knob_concept": "A-space branching entropy — not difficulty",
        "why": "Non-dominant paths need to be viable, not just theoretically possible.",
        "registry_edits": [
            {"knob": "escape_route_density", "direction": "+", "note": "Add viable alternate grammars per zone"},
            {"knob": "vehicle_handling_variance", "direction": "+", "note": "Prevent single optimal vehicle behavior"},
        ],
        "expected": "Multiple stable A-grammars re-emerge across runs.",
        "classifier_output": "VPR_VIOLATION",
    },
    "memoryless_city": {
        "label": "Memoryless City (no landmark imprint)",
        "signature": "Players cannot recall locations — geography feels generic — no spatial storytelling",
        "broken_layer": "spatial",
        "first_knob_concept": "Landmark weighting — not map size",
        "why": "Cognitive compressibility requires mechanical meaning attached to specific places.",
        "registry_edits": [
            {"knob": "landmark_salience_weight", "direction": "+", "note": "Attach risk/speed/visibility changes to key nodes"},
        ],
        "expected": "City becomes cognitively compressible — stories gain spatial identity.",
        "classifier_output": "STABLE_EMERGENCE",
    },
}

ALIASES = {k.replace("_", "-"): k for k in FAILURE_MAP}


def load_registry() -> dict:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {"knobs": {}}


def resolve(name: str) -> str | None:
    key = name.lower().replace("-", "_")
    return ALIASES.get(name.replace("_", "-"), key if key in FAILURE_MAP else None)


def layer_rank(layer: str) -> int:
    try:
        return LAYER_ORDER.index(layer)
    except ValueError:
        return 99


def render_knob_diff(edit: dict, registry_knobs: dict) -> str:
    knob_name = edit["knob"]
    direction = edit["direction"]
    note = edit["note"]
    reg = registry_knobs.get(knob_name, {})
    safe = reg.get("safe_edit", "see registry")
    risk = reg.get("risk", "unknown")
    default = reg.get("default", "?")
    rng = reg.get("range", ["?", "?"])
    sign = "▲" if direction == "+" else "▼"
    return (
        f"    {sign} {knob_name}\n"
        f"       default={default}  range=[{rng[0]}, {rng[1]}]  safe_edit: {safe}\n"
        f"       reason: {note}\n"
        f"       risk: {risk}"
    )


def render(hits: list[dict], raw_inputs: list[str], registry: dict) -> str:
    sep = "=" * 64
    knobs = registry.get("knobs", {})
    lines = [sep, "POST-STRESS TRIAGE REPORT", sep]
    lines.append(f"Inputs:  {', '.join(raw_inputs)}")
    lines.append(f"Rule:    fix earliest broken layer first — never tune more than 1 knob per iteration")
    lines.append("")

    for i, h in enumerate(hits, 1):
        tag = "► FIRST" if i == 1 else f"  THEN ({i})"
        lines += [
            f"{tag}  [{h['broken_layer']}]  {h['label']}",
            f"         Classifier output: {h['classifier_output']}",
            f"         Signature:  {h['signature']}",
            f"         Why:        {h['why']}",
            f"         Expected:   {h['expected']}",
            "",
            "         Knob diffs (pick ONE, from KnobRegistry only):",
        ]
        for edit in h["registry_edits"]:
            lines.append(render_knob_diff(edit, knobs))
        lines.append("")

    lines += [
        sep,
        "INVARIANT: Triage never recommends content changes.",
        "  Only parameter edits from KnobRegistry are valid outputs.",
        "  E fixes unlock A. A fixes unlock R.",
        "  VPR/RCP are constraints on a healthy system, not repair tools.",
        sep,
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Map stress-run failure signatures to KnobRegistry edits.\n"
            f"Valid signatures: {', '.join(FAILURE_MAP)}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("failures", nargs="+", metavar="FAILURE_SIGNATURE")
    args = parser.parse_args()

    registry = load_registry()
    hits = []
    for raw in args.failures:
        key = resolve(raw)
        if key:
            hits.append(FAILURE_MAP[key])
        else:
            print(f"WARNING: unknown signature '{raw}'", file=sys.stderr)
            print(f"  Valid: {', '.join(FAILURE_MAP)}", file=sys.stderr)

    if not hits:
        return 1

    hits.sort(key=lambda h: layer_rank(h["broken_layer"]))
    print(render(hits, args.failures, registry))
    return 0


if __name__ == "__main__":
    sys.exit(main())
