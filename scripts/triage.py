#!/usr/bin/env python3
"""
Post-Stress Triage v1
Input: one or more failure signatures observed in a stress run
Output: ordered list of knobs to tune, earliest broken layer first

Master rule: E > A > R > VPR > RCP
Never fix a downstream layer before the upstream cause is stable.
"""

import argparse
import sys

LAYER_ORDER = ["E", "E→A", "A", "A→R", "R", "spatial"]

PLAYBOOK: dict[str, dict] = {
    "vpr_collapse": {
        "label": "VPR Collapse (A-space attack)",
        "signature": "TopA_share > 0.7 — one dominant strategy, 'optimal path' emerged",
        "broken_layer": "E",
        "first_knob": "E variability — NOT A-space itself",
        "why": "A-collapse means E is too narrow. System overfits to one response when pressure is predictable.",
        "edits": [
            "AI_SpawnDelayVariance += 10–25%",
            "EncounterStartAngleVariance += 15–30°",
        ],
        "expected": "A naturally re-diversifies once E stops forcing a single optimal response.",
        "risk": "Over-randomizing E destroys setup legibility — stay within 25% variance.",
    },
    "rcp_smear": {
        "label": "RCP Smear (R-space collapse)",
        "signature": "No compressible arcs — cannot summarize runs cleanly — 'it just happened'",
        "broken_layer": "R",
        "first_knob": "R closure strength — not R options",
        "why": "Stories need state-dependent endings. Time-based or random exits produce smear.",
        "edits": [
            "HeatDecayStartThreshold -= 10–20%  (escape becomes state-driven, not time-driven)",
            "PursuitBreakCondition: require LoS break + distance threshold + zone exit (combined)",
        ],
        "expected": "Story arcs begin clustering into repeatable islands.",
        "risk": "Tightening closure too far reduces R variety — keep ≥2 viable exit conditions per E-class.",
    },
    "ear_breakdown": {
        "label": "E/A/R Breakdown (phase continuity collapse)",
        "signature": "E fires with no A window; A exists but doesn't change R; R has no causal link",
        "broken_layer": "E→A",
        "first_knob": "Time-to-adaptation window — not difficulty, not balance",
        "why": "Phase continuity breaks when players cannot react before consequences lock.",
        "edits": [
            "Decision window += 1–2 seconds after escalation onset",
            "Remove instant-lock outcomes — no immediate arrest/capture without a buffer state",
        ],
        "expected": "E → A → R chain becomes readable again.",
        "risk": "Oversized buffer window kills tension — do not exceed 3s without testing.",
    },
    "infinite_chase": {
        "label": "Infinite Chase (R never stabilizes)",
        "signature": "Runs continue too long or loop — no clean resolution point",
        "broken_layer": "R",
        "first_knob": "R termination clarity — closure triggers",
        "why": "Arcs oscillate when R conditions are ambiguous or time-based rather than state-based.",
        "edits": [
            "HeatExhaustionThreshold: set explicit numeric value, enforce it hard",
            "PursuitDisengageLogic: distance + LoS break + zone exit must all be TRUE simultaneously",
        ],
        "expected": "Arcs terminate cleanly into identifiable endings.",
        "risk": "Hard exits that ignore player state feel arbitrary — ensure conditions are legible mid-run.",
    },
    "decorative_adaptation": {
        "label": "Decorative Adaptation (A present, non-causal)",
        "signature": "Players act a lot but outcomes barely change — adaptation feels cosmetic",
        "broken_layer": "A→R",
        "first_knob": "A→R causal leverage — coupling strength",
        "why": "A stops being performance and becomes leverage only when wrong choices degrade position.",
        "edits": [
            "Environment sensitivity += to route/visibility/vehicle decisions (different AI behavior per A)",
            "Remove neutral success paths — wrong A choices must produce measurable position degradation",
        ],
        "expected": "Adaptation becomes leverage. Players feel consequences of choice.",
        "risk": "Over-penalizing suboptimal A collapses experimentation — keep partial recovery viable.",
    },
    "single_path_adaptation": {
        "label": "Single-Path Adaptation (strategy collapse)",
        "signature": "One dominant escape grammar across runs — other A-grammars go unused",
        "broken_layer": "A",
        "first_knob": "A-space branching entropy — not difficulty",
        "why": "Non-dominant paths need to be viable, not just theoretically possible.",
        "edits": [
            "Add 1–2 alternate viable escape grammars per zone (vertical / stealth / decoy / abandonment)",
            "Reduce safe default path dominance — narrow the advantage gap, do not remove the path",
        ],
        "expected": "Multiple stable A-grammars re-emerge across runs.",
        "risk": "Adding paths without AI response creates empty options — each grammar needs distinct pursuit behavior.",
    },
    "memoryless_city": {
        "label": "Memoryless City (no landmark imprint)",
        "signature": "Players cannot recall locations — geography feels generic — no spatial storytelling",
        "broken_layer": "spatial",
        "first_knob": "Landmark weighting — not map size",
        "why": "Cognitive compressibility requires mechanical meaning attached to specific places.",
        "edits": [
            "Increase visual + navigational contrast between zones (not just aesthetic)",
            "Attach risk/speed/visibility changes to 3–5 key landmarks per district",
        ],
        "expected": "City becomes cognitively compressible — stories gain spatial identity.",
        "risk": "Over-salient landmarks create tourist behavior — players navigate to them instead of through them.",
    },
}

ALIASES = {
    "vpr-collapse": "vpr_collapse",
    "rcp-smear": "rcp_smear",
    "ear-breakdown": "ear_breakdown",
    "infinite-chase": "infinite_chase",
    "decorative-adaptation": "decorative_adaptation",
    "single-path-adaptation": "single_path_adaptation",
    "memoryless-city": "memoryless_city",
}


def layer_rank(layer: str) -> int:
    try:
        return LAYER_ORDER.index(layer)
    except ValueError:
        return 99


def resolve(name: str) -> str | None:
    key = name.lower().replace(" ", "_")
    return ALIASES.get(key, key if key in PLAYBOOK else None)


def render(hits: list[dict], raw_inputs: list[str]) -> str:
    sep = "=" * 62
    lines = [sep, "POST-STRESS TRIAGE REPORT", sep]
    lines.append(f"Inputs:  {', '.join(raw_inputs)}")
    lines.append(f"Ordered: earliest broken layer first")
    lines.append("")

    for i, h in enumerate(hits, 1):
        tag = "► FIRST" if i == 1 else f"  THEN ({i})"
        lines += [
            f"{tag}  [{h['broken_layer']}]  {h['label']}",
            f"         Signature:  {h['signature']}",
            f"         Knob:       {h['first_knob']}",
            f"         Why:        {h['why']}",
            "         Edits (pick ONE per iteration):",
        ]
        for edit in h["edits"]:
            lines.append(f"           • {edit}")
        lines += [
            f"         Expected:   {h['expected']}",
            f"         Risk:       {h['risk']}",
            "",
        ]

    lines += [
        sep,
        "INVARIANT: Never tune more than 1 knob per iteration.",
        "  E fixes unlock A. A fixes unlock R.",
        "  VPR/RCP are constraints on a healthy system, not repair tools.",
        sep,
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Map stress-run failure signatures to first knob to tune.\n"
            f"Valid signatures: {', '.join(PLAYBOOK)}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("failures", nargs="+", metavar="FAILURE_SIGNATURE")
    args = parser.parse_args()

    hits = []
    for raw in args.failures:
        key = resolve(raw)
        if key:
            hits.append(PLAYBOOK[key])
        else:
            print(f"WARNING: unknown signature '{raw}' — skipping", file=sys.stderr)
            print(f"  Valid: {', '.join(PLAYBOOK)}", file=sys.stderr)

    if not hits:
        return 1

    hits.sort(key=lambda h: layer_rank(h["broken_layer"]))
    print(render(hits, args.failures))
    return 0


if __name__ == "__main__":
    sys.exit(main())
