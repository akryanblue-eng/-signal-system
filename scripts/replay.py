#!/usr/bin/env python3
"""
replay.py — Counterfactual Replay Engine (CRE) v0.1

CRE RESPONSIBILITY BOUNDARY:
  This module generates paired counterfactual event streams and structural
  arc diffs only.
  All behavioral metric computation (VPR/RCP/APC/AEI/ASI) is delegated
  to triage.py. This module may call triage.build_arcs() and
  triage.classify_arc() for structural arc comparison — not metric functions.

Execution mode (declared explicitly — do not silently upgrade):
  MODE_B — Event-conditioned pseudo-replay.
    Prefix is reconstructed from a deterministic synthetic generator
    (same RunBlueprint + seed). This is NOT bitwise-identical state
    capture. CCF outputs are labeled as MODE_B approximations.
    MODE_A (true deterministic replay) requires real simulator state
    serialization with frozen RNG and AI decision state.

Fork integrity contract (what this module guarantees in MODE_B):
  1. Prefix determinism: same seed + same blueprint → identical event stream
     up to prefix_end_ts.
  2. Fork isolation: only declared a_grammar / knob_overrides differ after
     the fork point. All prefix events are structurally identical.
  3. Causal cone: IC and ghost_mass are computed from explicit causal_links
     in the emitted event stream. Ghost effects that exist without causal
     declarations are correctly scored as ghost mass.

Outputs:
  --diff-only   → CRE diff object (structural comparison, no metrics)
  --certify     → CRE diff + triage metrics → CausalValidityCertificate
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import triage as t
from synthetic import ArcBlueprint, RunBlueprint, generate_run, knobs_to_arc_blueprint


# ── Replay mode declaration ────────────────────────────────────────────────────

CRE_MODE = "MODE_B"  # Event-conditioned pseudo-replay
CRE_MODE_NOTE = (
    "Prefix determinism guaranteed by synthetic generator seed. "
    "Fork isolation guaranteed by blueprint parameter separation. "
    "Not true bitwise-identical state capture. "
    "IC/ghost_mass are structural (causal_links-based), not behavioral."
)


# ── Structural comparison primitives ──────────────────────────────────────────

def _event_type_seq(events: List[Dict[str, Any]]) -> List[str]:
    """Extract event_type sequence (E/A/R types only, no NULL)."""
    null_types = {"ai_idle", "ambient_simulation", "navigation_update"}
    return [ev["event_type"] for ev in events if ev.get("event_type") not in null_types]


def event_seq_distance(seq1: List[str], seq2: List[str]) -> float:
    """Normalized Levenshtein distance on event_type sequences (0=identical, 1=fully different)."""
    m, n = len(seq1), len(seq2)
    if m == 0 and n == 0:
        return 0.0
    if m == 0 or n == 0:
        return 1.0
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            cost = 0 if seq1[i - 1] == seq2[j - 1] else 1
            dp[j], prev = min(dp[j] + 1, dp[j - 1] + 1, prev + cost), dp[j]
    return round(dp[n] / max(m, n), 4)


def _causal_cone(fork_event_id: str, events: List[Dict[str, Any]]) -> Set[str]:
    """
    BFS over contributes_to links from fork_event_id.
    Returns the set of all event_ids reachable from the fork point.
    """
    ev_index = {ev["event_id"]: ev for ev in events}
    cone: Set[str] = set()
    queue = [fork_event_id]
    while queue:
        cur = queue.pop(0)
        if cur in cone:
            continue
        cone.add(cur)
        if cur in ev_index:
            cl = ev_index[cur].get("causal_links") or {}
            queue.extend(cl.get("contributes_to", []))
    return cone


def compute_ic_ghost(
    fork_event_id: str,
    prefix_events: List[Dict[str, Any]],
    variant_events: List[Dict[str, Any]],
) -> Tuple[float, float]:
    """
    Compute Intervention Consistency (IC) and ghost_mass.

    Post-fork events = variant events whose event_ids are NOT in the prefix.
    These are the "new" events that constitute the divergence.

    IC: fraction of post-fork events that are in the causal cone of the
        fork point, or have at least one triggered_by reference into the cone.
    ghost_mass: 1 - IC.

    In MODE_B synthetic runs, ghost_mass = 0.0 when causal_links are correctly
    wired (all post-fork events are triggered by the fork E event).
    Non-zero ghost_mass appears when events change without declared causal ancestry.
    """
    prefix_ids: Set[str] = {ev["event_id"] for ev in prefix_events}
    post_fork = [ev for ev in variant_events if ev["event_id"] not in prefix_ids]

    if not post_fork:
        return 1.0, 0.0

    cone = _causal_cone(fork_event_id, variant_events)

    causally_connected = sum(
        1 for ev in post_fork
        if ev["event_id"] in cone
        or any(
            pred in cone
            for pred in (ev.get("causal_links") or {}).get("triggered_by", [])
        )
    )
    ic = round(causally_connected / len(post_fork), 4)
    return ic, round(1.0 - ic, 4)


def _arc_r_types(arcs: List[t.Arc]) -> List[str]:
    return [arc.R_events[0]["event_type"] for arc in arcs if arc.has_r]


def _arc_grammars(arcs: List[t.Arc]) -> Set[str]:
    from synthetic import GRAMMAR_TO_TYPES
    type_to_grammar = {v: k for k, types in GRAMMAR_TO_TYPES.items() for v in types}
    grammars: Set[str] = set()
    for arc in arcs:
        for ev in arc.A_events:
            g = type_to_grammar.get(ev.get("event_type", ""), "unknown")
            grammars.add(g)
    return grammars


# ── Experiment loading and generation ─────────────────────────────────────────

def load_experiment(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _make_prefix_events(exp: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    """
    Generate the shared prefix event stream from experiment config.
    Returns (prefix_events, fork_event_id).
    The fork event is the last E event in the prefix — the anchor for IC computation.
    """
    prefix_cfg = exp["prefix"]
    seed = prefix_cfg.get("seed", 42)
    base_knobs: Dict[str, float] = prefix_cfg.get("prefix_knobs", {})
    knob_defaults = {
        "heat_decay_rate": 1.0, "visibility_window": 3.0,
        "pressure_gradient": 1.0, "closure_threshold": 0.5,
    }
    for k, v in knob_defaults.items():
        base_knobs.setdefault(k, v)

    # Prefix = just the E event (shared starting condition)
    import random
    rng = random.Random(seed)
    fork_event_id = f"{exp['exp_id']}:prefix:001"
    prefix_ev = {
        "event_id": fork_event_id,
        "run_id": exp["exp_id"],
        "timestamp": 0.0,
        "phase_hint": "E",
        "event_type": prefix_cfg.get("e_type", "line_of_sight_spotted"),
        "source_system": "ai_police",
        "location": {
            "zone_id": prefix_cfg.get("zone_id", "test_zone"),
            "subzone": None,
            "x": round(rng.uniform(50.0, 200.0), 1),
            "y": round(rng.uniform(30.0, 100.0), 1),
        },
        "entities": ["player_vehicle", "npc_police_01"],
        "tags": [],
        "payload": {"heat_delta": 0.3},
        "causal_links": {"triggered_by": [], "contributes_to": []},
    }
    return [prefix_ev], fork_event_id


def _make_variant_events(
    exp: Dict[str, Any],
    variant: Dict[str, Any],
    prefix_events: List[Dict[str, Any]],
    fork_event_id: str,
) -> List[Dict[str, Any]]:
    """
    Generate a variant's continuation events and splice onto the prefix.
    The fork E event is the shared prefix event_id; continuation events
    have triggered_by=[fork_event_id] to establish causal connection.
    """
    prefix_cfg = exp["prefix"]
    base_knobs: Dict[str, float] = dict(prefix_cfg.get("prefix_knobs", {}))
    knob_defaults = {
        "heat_decay_rate": 1.0, "visibility_window": 3.0,
        "pressure_gradient": 1.0, "closure_threshold": 0.5,
    }
    for k, v in knob_defaults.items():
        base_knobs.setdefault(k, v)
    base_knobs.update(variant.get("knob_overrides", {}))

    arc_bp = knobs_to_arc_blueprint(
        base_knobs,
        a_grammar=variant.get("a_grammar", "speed"),
        r_type=variant.get("r_type", "pursuit_lost"),
    )

    # Substitute fork event ID into the continuation
    run_id = f"{exp['exp_id']}:{variant['variant_id']}"
    seed = prefix_cfg.get("seed", 42) + hash(variant["variant_id"]) % 1000

    import random
    rng = random.Random(seed)

    from synthetic import GRAMMAR_TO_TYPES
    a_type_choices = GRAMMAR_TO_TYPES.get(arc_bp.a_grammar, ["route_change"])
    a_ids: List[str] = []
    continuation: List[Dict[str, Any]] = []
    ts = arc_bp.e_to_first_a  # start after E window

    prefix_ev = prefix_events[0]
    # Update fork E event's contributes_to for this variant (copy to avoid mutation)
    fork_ev_copy = {**prefix_ev, "causal_links": {"triggered_by": [], "contributes_to": []}}

    def loc() -> Dict[str, Any]:
        return {
            "zone_id": arc_bp.zone_id,
            "subzone": "west",
            "x": round(rng.uniform(50.0, 200.0), 1),
            "y": round(rng.uniform(30.0, 100.0), 1),
        }

    for i in range(arc_bp.a_count):
        a_id = f"{run_id}:cont:{i + 1:03d}"
        a_type = a_type_choices[i % len(a_type_choices)]
        a_ev = {
            "event_id": a_id,
            "run_id": run_id,
            "timestamp": round(ts, 2),
            "phase_hint": "A",
            "event_type": a_type,
            "source_system": "player",
            "location": loc(),
            "entities": ["player_vehicle"],
            "tags": [],
            "payload": {"speed": round(rng.uniform(40.0, 90.0), 1)},
            "causal_links": {"triggered_by": [fork_event_id], "contributes_to": []},
        }
        fork_ev_copy["causal_links"]["contributes_to"].append(a_id)
        a_ids.append(a_id)
        continuation.append(a_ev)
        ts += arc_bp.a_spacing

    if arc_bp.close:
        ts += arc_bp.a_to_r
        r_id = f"{run_id}:cont:{arc_bp.a_count + 1:03d}"
        r_ev = {
            "event_id": r_id,
            "run_id": run_id,
            "timestamp": round(ts, 2),
            "phase_hint": "R",
            "event_type": arc_bp.r_type,
            "source_system": "system",
            "location": loc(),
            "entities": ["player_vehicle"],
            "tags": ["arc_complete"],
            "payload": {"heat_delta": arc_bp.heat_r},
            "causal_links": {"triggered_by": a_ids[:], "contributes_to": []},
        }
        for a_ev in continuation:
            a_ev["causal_links"]["contributes_to"].append(r_id)
        continuation.append(r_ev)

    return [fork_ev_copy] + continuation


# ── CRE comparison engine ──────────────────────────────────────────────────────

def cre_compare(exp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate paired counterfactual event streams and compute structural diffs.

    Returns CRE diff object only — no behavioral metrics.
    Metrics must be computed externally via triage.py.
    """
    prefix_events, fork_event_id = _make_prefix_events(exp)
    variants = exp["variants"]

    # First variant is always the base
    base_variant = variants[0]
    base_events = _make_variant_events(exp, base_variant, prefix_events, fork_event_id)
    base_arcs = t.build_arcs(base_events)
    base_seq = _event_type_seq(base_events)

    results = []
    for variant in variants[1:]:
        var_events = _make_variant_events(exp, variant, prefix_events, fork_event_id)
        var_arcs = t.build_arcs(var_events)
        var_seq = _event_type_seq(var_events)

        ic, ghost_mass = compute_ic_ghost(fork_event_id, prefix_events, var_events)

        base_bp = t.classify_breakpoint(base_arcs)
        var_bp = t.classify_breakpoint(var_arcs)
        base_r = _arc_r_types(base_arcs)
        var_r = _arc_r_types(var_arcs)
        base_grammars = _arc_grammars(base_arcs)
        var_grammars = _arc_grammars(var_arcs)

        seq_dist = event_seq_distance(base_seq, var_seq)
        grammar_delta = list(base_grammars.symmetric_difference(var_grammars))
        causal_locality_ok = ic >= 0.70 and ghost_mass <= 0.20

        results.append({
            "variant_id": variant["variant_id"],
            "event_count": len(var_events),
            "arc_count": len(var_arcs),
            "breakpoint": var_bp,
            "r_types": var_r,
            "diff_vs_base": {
                "r_changed": set(base_r) != set(var_r),
                "breakpoint_changed": base_bp != var_bp,
                "event_seq_distance": seq_dist,
                "a_grammar_delta": grammar_delta,
                "IC": ic,
                "ghost_mass": ghost_mass,
                "causal_locality_ok": causal_locality_ok,
            },
        })

    return {
        "exp_id": exp["exp_id"],
        "mode": CRE_MODE,
        "mode_note": CRE_MODE_NOTE,
        "fork_point_event_id": fork_event_id,
        "prefix_event_count": len(prefix_events),
        "base_variant_id": base_variant["variant_id"],
        "base_breakpoint": t.classify_breakpoint(base_arcs),
        "base_r_types": _arc_r_types(base_arcs),
        "variants": results,
    }


# ── Certificate assembly (delegates metrics to triage.py) ─────────────────────

def certify(exp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Run CRE comparison then call triage.py for behavioral metrics.
    Assemble CausalValidityCertificate per variant pair.

    CRE generates the diff. triage.py generates the metrics.
    This function is the seam between them — it does not compute either.
    """
    prefix_events, fork_event_id = _make_prefix_events(exp)
    variants = exp["variants"]
    base_variant = variants[0]
    base_events = _make_variant_events(exp, base_variant, prefix_events, fork_event_id)

    # triage metrics for base
    base_arcs = t.build_arcs(base_events)
    base_vpr = t.compute_vpr(base_arcs)
    base_rcp = t.compute_rcp(base_arcs)
    base_apc = t.compute_apc(base_arcs)
    base_ccf = t.compute_ccf(base_arcs)
    base_asi = t.compute_asi(base_arcs, base_rcp)

    def _base_metrics() -> Dict[str, Any]:
        return {
            "breakpoint": t.classify_breakpoint(base_arcs),
            "TopA_share": base_vpr["TopA_share"],
            "ViableA_count": base_vpr["ViableA_count"],
            "smear_index": base_rcp["smear_index"],
            "APC_mean": base_apc["APC_mean"],
            "E_explained_mean": base_ccf["E_explained_mean"],
            "asi": base_asi["asi"],
            "asi_regime": base_asi["regime"],
        }

    certs = []
    for variant in variants[1:]:
        var_events = _make_variant_events(exp, variant, prefix_events, fork_event_id)
        var_arcs = t.build_arcs(var_events)
        var_vpr = t.compute_vpr(var_arcs)
        var_rcp = t.compute_rcp(var_arcs)
        var_apc = t.compute_apc(var_arcs)
        var_ccf = t.compute_ccf(var_arcs)
        var_asi = t.compute_asi(var_arcs, var_rcp)

        ic, ghost_mass = compute_ic_ghost(fork_event_id, prefix_events, var_events)

        # CCF_mean: (E_explained * IC) - ghost_mass, clamped to [0,1]
        e_exp = var_ccf.get("E_explained_mean") or 0.0
        ccf_mean = max(0.0, min(1.0, e_exp * ic - ghost_mass))

        if ic >= 0.70 and ghost_mass <= 0.20:
            verdict = "CLOSED"
        elif ic >= 0.40 and ghost_mass <= 0.40:
            verdict = "OPEN"
        else:
            verdict = "CONTAMINATED"

        base_bp = t.classify_breakpoint(base_arcs)
        var_bp  = t.classify_breakpoint(var_arcs)
        base_seq = _event_type_seq(base_events)
        var_seq  = _event_type_seq(var_events)

        cert: Dict[str, Any] = {
            "cert_id": f"cert_{exp['exp_id']}_{variant['variant_id']}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}",
            "exp_id": exp["exp_id"],
            "created_at": datetime.utcnow().isoformat() + "Z",
            "mode": CRE_MODE,
            "prefix_end_ts": 0.0,
            "fork_point_event_id": fork_event_id,
            "base_variant_id": base_variant["variant_id"],
            "test_variant_id": variant["variant_id"],
            "causal_verdict": verdict,
            "CCF_mean": round(ccf_mean, 4),
            "IC": ic,
            "ghost_mass": ghost_mass,
            "divergence": {
                "r_changed": set(_arc_r_types(base_arcs)) != set(_arc_r_types(var_arcs)),
                "breakpoint_changed": base_bp != var_bp,
                "event_seq_distance": event_seq_distance(base_seq, var_seq),
                "a_grammar_delta": list(_arc_grammars(base_arcs).symmetric_difference(_arc_grammars(var_arcs))),
                "causal_locality_ok": ic >= 0.70 and ghost_mass <= 0.20,
            },
            "base_metrics": _base_metrics(),
            "test_metrics": {
                "breakpoint": var_bp,
                "TopA_share": var_vpr["TopA_share"],
                "ViableA_count": var_vpr["ViableA_count"],
                "smear_index": var_rcp["smear_index"],
                "APC_mean": var_apc["APC_mean"],
                "E_explained_mean": var_ccf["E_explained_mean"],
                "asi": var_asi["asi"],
                "asi_regime": var_asi["regime"],
            },
            "notes": [CRE_MODE_NOTE],
        }
        certs.append(cert)

    return certs


# ── Main ────────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="replay.py v0.1 — CRE: paired counterfactual event stream generator"
    )
    ap.add_argument("--experiment", required=True, help="CRE experiment config JSON")
    ap.add_argument("--certify", action="store_true",
                    help="Produce CausalValidityCertificates (delegates metrics to triage.py)")
    ap.add_argument("--registry", default=None, help="Knob registry (required for --certify if using registry knobs)")
    args = ap.parse_args(argv)

    exp = load_experiment(Path(args.experiment))

    if args.certify:
        certs = certify(exp)
        output = {
            "certificates": certs,
            "exp_id": exp["exp_id"],
            "created_at": datetime.utcnow().isoformat() + "Z",
            "mode": CRE_MODE,
        }
    else:
        output = cre_compare(exp)

    json.dump(output, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    from typing import Optional
    raise SystemExit(main())
