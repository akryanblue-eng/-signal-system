#!/usr/bin/env python3
"""
sipmg.py — System Integrity Phase Map Generator v0.1

Sweeps a configured knob space and classifies each point into one of four phases:

  Phase A — Stable World / Stable Instrument   (target regime)
  Phase B — Stable World / Degrading Instrument (silent collapse risk)
  Phase C — Destabilizing World / Stable Instrument (legitimate failure, instrument honest)
  Phase D — Joint Collapse                      (world fails + instrument dulls)

World stability:  measured by triage.py metrics (breakpoint, CCF, APC, smear_index).
Instrument stability: measured by ghost_mass + IC from a minimal CRE grammar-fork at
  each point, supplemented by canary.py self-test (run once before the sweep).

Limitation — synthetic MODE_B:
  ghost_mass is structurally 0.0 when causal_links are correctly wired by the synthetic
  generator. In clean sweeps, Phase B and D are unreachable (all points classify A or C).
  Set ghost_inject_rate > 0 in the sweep config to simulate real-world causal opacity
  and expose the Phase B boundary.

VCL hash:
  sha256 prefix of all instrument scripts at sweep time. Embed in the output JSON to
  ensure results are reproducible against a specific instrument version.

CLI:
  python scripts/sipmg.py --config experiments/sipmg_sweep.json
  python scripts/sipmg.py --config ... --summary-only
  python scripts/sipmg.py --config ... --ascii-map   (2-axis sweeps only)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import triage as t
from canary import run_canary, CanaryReport
from replay import compute_ic_ghost
from synthetic import RunBlueprint, ArcBlueprint, generate_run, knobs_to_arc_blueprint

SIPMG_VERSION = "0.1"


# ── VCL hash ──────────────────────────────────────────────────────────────────

def compute_vcl_hash() -> str:
    """sha256 of all instrument scripts concatenated — instrument version lock."""
    scripts = ["triage.py", "synthetic.py", "replay.py", "canary.py", "cssr.py", "sipmg.py"]
    h = hashlib.sha256()
    for name in scripts:
        p = Path(__file__).parent / name
        if p.exists():
            h.update(p.read_bytes())
    return f"sha256:{h.hexdigest()[:24]}"


# ── Sweep point generation ────────────────────────────────────────────────────

def _soft_values(axis: Dict[str, Any]) -> List[float]:
    lo, hi = axis["soft_range"]
    step = axis["soft_step"]
    vals: List[float] = []
    v = lo
    while v <= hi + 1e-9:
        vals.append(round(v, 6))
        v += step
    return vals


def _hard_values(axis: Dict[str, Any], soft_vals: List[float]) -> List[float]:
    n = axis.get("hard_samples", 0)
    if n == 0:
        return []
    lo, hi = axis["hard_range"]
    soft_lo, soft_hi = axis["soft_range"]
    # Sample below soft_lo and above soft_hi (the "extreme" zones)
    candidates: List[float] = []
    if lo < soft_lo:
        step_below = (soft_lo - lo) / max(n // 2, 1)
        v = lo
        while v < soft_lo - 1e-9:
            candidates.append(round(v, 6))
            v += step_below
    if hi > soft_hi:
        step_above = (hi - soft_hi) / max(n - n // 2, 1)
        v = soft_hi + step_above
        while v <= hi + 1e-9:
            candidates.append(round(v, 6))
            v += step_above
    # Filter to values not already in soft range
    soft_set = set(soft_vals)
    return [v for v in candidates if v not in soft_set]


def sweep_points(config: Dict[str, Any]) -> List[Tuple[Dict[str, float], str]]:
    """
    Returns list of (coords_dict, range_type) tuples.
    range_type: "soft" or "hard"
    """
    axes = config["axes"]
    axis_soft: List[List[float]] = []
    axis_hard: List[List[float]] = []

    for ax in axes:
        sv = _soft_values(ax)
        hv = _hard_values(ax, sv)
        axis_soft.append(sv)
        axis_hard.append(hv)

    knob_ids = [ax["knob_id"] for ax in axes]
    points: List[Tuple[Dict[str, float], str]] = []

    # Soft: full product
    for combo in product(*axis_soft):
        points.append((dict(zip(knob_ids, combo)), "soft"))

    # Hard: one-axis-at-a-time extreme samples (hold others at baseline)
    baselines = {ax["knob_id"]: ax["baseline"] for ax in axes}
    for i, ax in enumerate(axes):
        for hv in axis_hard[i]:
            coords = dict(baselines)
            coords[ax["knob_id"]] = hv
            points.append((coords, "hard"))

    return points


# ── Ghost injection ───────────────────────────────────────────────────────────

def _inject_ghosts(
    events: List[Dict[str, Any]],
    prefix_ids: Set[str],
    rate: float,
    rng: random.Random,
    run_id: str,
) -> List[Dict[str, Any]]:
    """
    Append orphaned ghost events — events not reachable via any contributes_to
    chain from the fork point. These correctly generate ghost_mass in
    compute_ic_ghost because they are in post_fork but not in the causal cone.

    Wiping triggered_by on existing events does NOT work: the fork event's
    contributes_to still lists those events, keeping them in the BFS cone.
    New orphaned events are the correct simulation of real-world causal opacity.

    Count: max(1, floor(n_post_fork * rate)) — at least 1 ghost if rate > 0.
    """
    if rate <= 0.0:
        return events
    post_fork = [ev for ev in events if ev["event_id"] not in prefix_ids]
    n_ghosts = max(1, int(len(post_fork) * rate))
    result = list(events)
    for i in range(n_ghosts):
        ghost_id = f"{run_id}:ghost:{i + 1:03d}"
        result.append({
            "event_id": ghost_id,
            "run_id": run_id,
            "timestamp": round(rng.uniform(1.0, 25.0), 2),
            "phase_hint": "A",
            "event_type": "stealth_break",
            "source_system": "player",
            "location": {"zone_id": "sipmg_zone", "subzone": None,
                         "x": round(rng.uniform(50.0, 200.0), 1),
                         "y": round(rng.uniform(30.0, 100.0), 1)},
            "entities": ["player_vehicle"],
            "tags": ["ghost_injected"],
            "payload": {"speed": round(rng.uniform(40.0, 90.0), 1)},
            # Empty causal_links: not reachable via contributes_to from fork.
            # compute_ic_ghost will correctly classify as ghost mass.
            "causal_links": {"triggered_by": [], "contributes_to": []},
        })
    return result


# ── Per-point execution ────────────────────────────────────────────────────────

def run_point(
    coords: Dict[str, float],
    config: Dict[str, Any],
    canary_status: str,
) -> Dict[str, Any]:
    """
    Run one sweep point:
    1. Generate synthetic events at these knobs.
    2. Compute triage metrics (world health).
    3. Generate grammar-fork variant, optionally inject ghosts, compute IC/ghost_mass.
    4. Classify phase.
    """
    fixed = config.get("fixed_knobs", {})
    knobs = {**fixed, **coords}

    grammar = config.get("arc_grammar", "speed")
    r_type  = config.get("r_type", "pursuit_lost")
    seed    = config.get("seed", 42)
    ghost_rate = float(config.get("ghost_inject_rate", 0.0))

    # World events
    arc_bp = knobs_to_arc_blueprint(knobs, a_grammar=grammar, r_type=r_type)
    run = RunBlueprint(run_id="sipmg_world", arcs=[arc_bp], seed=seed)
    world_events = generate_run(run)
    world_arcs = t.build_arcs(world_events)

    breakpoint_ = t.classify_breakpoint(world_arcs)
    vpr  = t.compute_vpr(world_arcs)
    rcp  = t.compute_rcp(world_arcs)
    apc  = t.compute_apc(world_arcs)
    ccf  = t.compute_ccf(world_arcs)
    asi  = t.compute_asi(world_arcs, rcp)

    world_metrics = {
        "breakpoint":    breakpoint_,
        "CCF_mean":      ccf.get("CCF_mean"),
        "APC_mean":      apc.get("APC_mean"),
        "smear_index":   rcp.get("smear_index", 1.0),
        "ViableA_count": vpr.get("ViableA_count", 0),
        "asi_regime":    asi.get("regime", "non_system"),
    }

    # Instrument probe: grammar-fork CRE comparison at this knob setting
    # Fork prefix = first E event; continuation = variant grammar
    e_events = [ev for ev in world_events if t.phase_from_type(ev) == "E"]
    if e_events:
        fork_id = e_events[0]["event_id"]
        prefix  = [e_events[0]]
        prefix_ids = {fork_id}

        alt_grammar = "stealth" if grammar == "speed" else "speed"
        alt_bp  = knobs_to_arc_blueprint(knobs, a_grammar=alt_grammar, r_type=r_type)
        alt_run = RunBlueprint(run_id="sipmg_variant", arcs=[alt_bp], seed=seed + 1)
        var_events_raw = generate_run(alt_run)

        # Re-anchor causal links to shared fork_id
        # Replace the E event_id in variant events with the shared fork_id
        old_e_id = var_events_raw[0]["event_id"] if var_events_raw else None
        var_events: List[Dict[str, Any]] = []
        for ev in var_events_raw:
            ev2 = dict(ev)
            ev2["event_id"] = ev2["event_id"].replace("sipmg_variant:", "sipmg_v:")
            cl = dict((ev2.get("causal_links") or {}))
            cl["triggered_by"] = [
                fork_id if p == old_e_id else p.replace("sipmg_variant:", "sipmg_v:")
                for p in cl.get("triggered_by", [])
            ]
            cl["contributes_to"] = [
                c.replace("sipmg_variant:", "sipmg_v:") for c in cl.get("contributes_to", [])
            ]
            ev2["causal_links"] = cl
            var_events.append(ev2)

        # Replace the first event's id with fork_id so it is the prefix
        if var_events:
            var_events[0]["event_id"] = fork_id

        var_events = _inject_ghosts(
            var_events, prefix_ids, ghost_rate, random.Random(seed + 99), run_id="sipmg_v"
        )
        ic, ghost_mass = compute_ic_ghost(fork_id, prefix, var_events)
    else:
        ic, ghost_mass = 1.0, 0.0

    # Phase classification
    ws_thresh = config.get("world_stability_thresholds", {})
    ccf_min   = ws_thresh.get("CCF_min", 0.50)
    smear_max = ws_thresh.get("smear_index_max", 0.50)
    apc_min   = ws_thresh.get("APC_mean_min", 0.15)

    is_thresh = config.get("instrument_stability_thresholds", {})
    ghost_max = is_thresh.get("ghost_mass_max", 0.20)
    ic_min    = is_thresh.get("IC_min", 0.70)

    ccf_val = world_metrics["CCF_mean"] or 0.0
    apc_val = world_metrics["APC_mean"]
    smear   = world_metrics["smear_index"]

    world_stable = (
        breakpoint_ == "full_arc"
        and ccf_val >= ccf_min
        and smear <= smear_max
        and (apc_val is None or apc_val >= apc_min)
    )
    # In MODE_B with ghost_inject_rate=0.0, ghost_mass is always 0.0 and IC=1.0.
    # instrument_stable will be True for all points unless ghost_rate>0 or real data.
    instrument_stable = (
        ghost_mass <= ghost_max
        and ic >= ic_min
        and canary_status != "SILENT_COLLAPSE"
    )

    if world_stable and instrument_stable:
        phase = "A"
    elif world_stable and not instrument_stable:
        phase = "B"
    elif not world_stable and instrument_stable:
        phase = "C"
    else:
        phase = "D"

    return {
        "coords":               coords,
        "world_stability":      "stable" if world_stable else "degraded",
        "instrument_stability": "stable" if instrument_stable else "degraded",
        "phase":                phase,
        "world_metrics":        world_metrics,
        "instrument_metrics":   {
            "IC":            ic,
            "ghost_mass":    ghost_mass,
            "canary_status": canary_status,
        },
    }


# ── Boundary detection ────────────────────────────────────────────────────────

def _find_boundaries(points: List[Dict[str, Any]], axes: List[str]) -> int:
    """Count points adjacent (in coord grid) to a different phase."""
    if len(axes) != 2:
        return 0
    ax0, ax1 = axes
    coord_to_phase = {
        (p["coords"].get(ax0), p["coords"].get(ax1)): p["phase"]
        for p in points if p.get("range_type") == "soft"
    }
    boundary = 0
    for (x, y), phase in coord_to_phase.items():
        neighbours = [(x + dx, y) for dx in [-0.5, 0.5]] + [(x, y + dy) for dy in [-0.5, 0.5]]
        if any(coord_to_phase.get(n, phase) != phase for n in neighbours):
            boundary += 1
    return boundary


def _first_transition(points: List[Dict[str, Any]], target_phases: Set[str]) -> Optional[Dict]:
    """First soft-range point in target phases, ordered by coord magnitude."""
    soft = [p for p in points if p.get("range_type") == "soft" and p["phase"] in target_phases]
    if not soft:
        return None
    return min(soft, key=lambda p: sum(v ** 2 for v in p["coords"].values()))


# ── ASCII map (2D only) ───────────────────────────────────────────────────────

def _ascii_map(points: List[Dict[str, Any]], axes: List[str]) -> str:
    if len(axes) != 2:
        return "(ASCII map requires exactly 2 sweep axes)"
    ax0, ax1 = axes
    phase_char = {"A": ".", "B": "B", "C": "C", "D": "X"}

    soft = [p for p in points if p.get("range_type") == "soft"]
    xs = sorted(set(p["coords"].get(ax0) for p in soft))
    ys = sorted(set(p["coords"].get(ax1) for p in soft), reverse=True)

    grid: Dict[Tuple[float, float], str] = {}
    for p in soft:
        grid[(p["coords"].get(ax0), p["coords"].get(ax1))] = phase_char.get(p["phase"], "?")

    lines = [f"  {ax0} →"]
    x_hdr = "  " + "".join(f"{x:5.1f}" for x in xs)
    lines.append(x_hdr)
    for y in ys:
        row = f"{y:4.1f} " + "".join(f"  {grid.get((x, y), '?')}  " for x in xs)
        lines.append(row)
    lines.append(f"  ↑ {ax1}")
    lines.append("  . = Phase A  C = Phase C  B = Phase B  X = Phase D")
    return "\n".join(lines)


# ── Summary text ──────────────────────────────────────────────────────────────

def _format_summary(result: Dict[str, Any]) -> str:
    s = result["sweep_summary"]
    c = result["canary_result"]
    total = s["total_points"]
    lines = [
        f"SIPMG — {result['generated_at'][:10]}  VCL:{result['vcl_hash'][7:19]}",
        f"  Canary: {c['status']} ({c['breaks_detected']}/{c['breaks_run']})",
        f"  Sweep: {total} points "
        f"(soft={s['soft_points']}, hard={s['hard_points']})",
        f"  Phase A: {s['phase_A']:3d} ({100*s['phase_A']//total:2d}%)  target",
        f"  Phase B: {s['phase_B']:3d} ({100*s['phase_B']//total:2d}%)  silent collapse risk",
        f"  Phase C: {s['phase_C']:3d} ({100*s['phase_C']//total:2d}%)  world degraded (instrument honest)",
        f"  Phase D: {s['phase_D']:3d} ({100*s['phase_D']//total:2d}%)  joint collapse",
    ]
    if s.get("world_break_coords"):
        lines.append(f"  World boundary onset: {s['world_break_coords']}")
    if s.get("instrument_break_coords"):
        lines.append(f"  Instrument boundary onset: {s['instrument_break_coords']}")
    grate = result.get("ghost_inject_rate", 0.0)
    if grate == 0.0:
        lines.append(
            "  Note: ghost_inject_rate=0.0 — Phase B/D require >0 or real data."
        )
    return "\n".join(lines)


# ── Generator ─────────────────────────────────────────────────────────────────

def generate_sipmg(config_path: str) -> Dict[str, Any]:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    vcl_hash = compute_vcl_hash()

    # Canary self-test — runs once; all sweep points inherit this result
    canary = run_canary()
    canary_summary = {
        "status": canary.status,
        "detection_rate": canary.detection_rate,
        "breaks_detected": canary.breaks_detected,
        "breaks_run": canary.breaks_run,
    }

    if canary.status == "SILENT_COLLAPSE":
        sys.stderr.write(
            "SIPMG ABORT: canary.status=SILENT_COLLAPSE — instrument is non-responsive. "
            "Phase map results are meaningless. Fix instrument first.\n"
        )
        sys.exit(2)

    axes = config["axes"]
    axis_ids = [ax["knob_id"] for ax in axes]
    all_points = sweep_points(config)

    points_out: List[Dict[str, Any]] = []
    for coords, range_type in all_points:
        pt = run_point(coords, config, canary.status)
        pt["range_type"] = range_type
        points_out.append(pt)

    # Summary statistics
    phase_counts = defaultdict(int)
    for p in points_out:
        phase_counts[p["phase"]] += 1

    soft_pts = [p for p in points_out if p["range_type"] == "soft"]
    hard_pts = [p for p in points_out if p["range_type"] == "hard"]
    boundary_count = _find_boundaries(points_out, axis_ids)

    world_break = _first_transition(points_out, {"C", "D"})
    instr_break = _first_transition(points_out, {"B", "D"})

    sweep_summary = {
        "total_points":    len(points_out),
        "soft_points":     len(soft_pts),
        "hard_points":     len(hard_pts),
        "phase_A":         phase_counts["A"],
        "phase_B":         phase_counts["B"],
        "phase_C":         phase_counts["C"],
        "phase_D":         phase_counts["D"],
        "boundary_points": boundary_count,
        "world_break_coords":      world_break["coords"] if world_break else None,
        "instrument_break_coords": instr_break["coords"] if instr_break else None,
    }

    result: Dict[str, Any] = {
        "sipmg_version":    SIPMG_VERSION,
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "config_path":      config_path,
        "vcl_hash":         vcl_hash,
        "ghost_inject_rate": float(config.get("ghost_inject_rate", 0.0)),
        "sweep_axes":       axes,
        "sweep_summary":    sweep_summary,
        "canary_result":    canary_summary,
        "points":           points_out,
    }
    result["summary_text"] = _format_summary(result)
    return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="sipmg.py v0.1 — System Integrity Phase Map Generator"
    )
    ap.add_argument("--config", required=True, help="Sweep config JSON")
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument(
        "--ascii-map", action="store_true",
        help="Print ASCII phase map (2-axis sweeps only)"
    )
    args = ap.parse_args(argv)

    result = generate_sipmg(args.config)

    if args.summary_only:
        print(result["summary_text"])
    elif args.ascii_map:
        print(result["summary_text"])
        print()
        axis_ids = [ax["knob_id"] for ax in result["sweep_axes"]]
        print(_ascii_map(result["points"], axis_ids))
    else:
        json.dump(result, sys.stdout, indent=2, sort_keys=False)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    from typing import Optional
    raise SystemExit(main())
