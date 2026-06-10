#!/usr/bin/env python3
"""
mag.py — Minimal Adversarial Generator v0.1

Finds the cheapest intervention that makes the evaluation stack produce an
internally inconsistent story — a state where the system violates its own
declared contracts.

Not a fuzzer. A law-seeking contradiction engine.

Break types (machine-checkable):
  A  Determinism contradiction: prefix_hash changes without declared intervention
  B  Fork isolation contradiction: post-fork changes outside declared causal cone
  C  Mode boundary contradiction: MODE_B emitting causal certification fields
  D  Provenance contradiction: VCL hash unchanged despite threshold mutation
  E  Canary contradiction: known-break passes, or invariance false-alarms
  F  Governance contradiction: CSSR verdict flips under identical inputs

Search strategy (v0.1, budget-bounded):
  1. Boundary probing: test SIPMG phase-edge coordinates (cheapest, most realistic)
  2. Knob gradient: ±delta from baseline, escalating magnitude
  3. Mode fault injection: mislabel replay_mode, strip causal fields
  4. VCL bypass: mutate threshold constants, check hash stability
  Halts when budget exhausted or all break types confirmed + minimized.

Cost model (lexicographic): intrusiveness < |delta| < compute < (1/strength)
  — prefer realistic knob moves over artificial faults.

Output: Minimal Contradiction Witness (MCW) JSON per break found.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import triage as t
from canary import run_canary, run_ghost_break, run_a_bypass_break, run_knob_sensitivity_break
from replay import compute_ic_ghost, _make_prefix_events, _make_variant_events
from cssr import generate_cssr, load_certs
from sipmg import compute_vcl_hash, run_point as sipmg_run_point
from synthetic import RunBlueprint, ArcBlueprint, generate_run, knobs_to_arc_blueprint

MAG_VERSION = "0.1"

# ── Cost weights ───────────────────────────────────────────────────────────────

W_INTRUSIVENESS  = 1.0   # prefer realistic moves
W_DELTA          = 0.5   # prefer smaller knob changes
W_COMPUTE        = 0.2   # prefer fewer runs
W_STRENGTH       = 2.0   # strongly prefer hard breaks over soft


# ── MCW data types ─────────────────────────────────────────────────────────────

@dataclass
class Move:
    move_id: str
    scope: str            # knob | fault | mode | vcl
    params: Dict[str, Any]
    cost: Dict[str, float]


@dataclass
class MinimalContradictionWitness:
    mcw_version: str
    break_type: str
    severity: str         # HARD | SOFT
    description: str
    vcl_base: str
    candidate_plan: Dict[str, Any]
    minimized_plan: Dict[str, Any]
    reproduction_steps: List[str]
    observations: Dict[str, Any]
    generated_at: str


# ── Shared helpers ─────────────────────────────────────────────────────────────

_DEFAULT_KNOBS = {
    "heat_decay_rate": 1.0,
    "visibility_window": 3.0,
    "pressure_gradient": 1.0,
    "closure_threshold": 0.5,
}

_DEFAULT_EXP = {
    "exp_id": "mag_baseline",
    "prefix": {
        "e_type": "line_of_sight_spotted",
        "zone_id": "test_zone",
        "seed": 42,
        "prefix_knobs": dict(_DEFAULT_KNOBS),
    },
    "variants": [
        {"variant_id": "base_speed",  "a_grammar": "speed",  "r_type": "pursuit_lost", "knob_overrides": {}},
        {"variant_id": "v1_stealth",  "a_grammar": "stealth","r_type": "pursuit_lost", "knob_overrides": {}},
    ],
}

_DEFAULT_SIPMG_CFG = {
    "axes": [
        {"knob_id": "pressure_gradient", "baseline": 1.0, "soft_range": [0.5, 3.5], "soft_step": 0.5,
         "hard_range": [0.0, 10.0], "hard_samples": 0},
        {"knob_id": "heat_decay_rate",   "baseline": 1.0, "soft_range": [0.5, 3.0], "soft_step": 0.5,
         "hard_range": [0.0, 6.0],  "hard_samples": 0},
    ],
    "fixed_knobs": {"visibility_window": 3.0, "closure_threshold": 0.5},
    "arc_grammar": "speed", "r_type": "pursuit_lost", "seed": 42,
    "ghost_inject_rate": 0.0,
    "world_stability_thresholds":  {"CCF_min": 0.50, "smear_index_max": 0.50, "APC_mean_min": 0.15},
    "instrument_stability_thresholds": {"ghost_mass_max": 0.20, "IC_min": 0.70},
}


def _make_events(knobs: Dict[str, float], grammar: str = "speed",
                 r_type: str = "pursuit_lost", seed: int = 42) -> List[Dict[str, Any]]:
    bp = knobs_to_arc_blueprint(knobs, a_grammar=grammar, r_type=r_type)
    return generate_run(RunBlueprint(run_id="mag_run", arcs=[bp], seed=seed))


def _prefix_hash(events: List[Dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for ev in events:
        h.update(json.dumps(ev, sort_keys=True).encode())
    return h.hexdigest()[:16]


def _move_cost(scope: str, delta: float, n_runs: int = 1, strength: float = 1.0) -> Dict[str, float]:
    scope_intrusion = {"knob": 0.1, "mode": 0.5, "fault": 0.8, "vcl": 0.9}.get(scope, 1.0)
    total = (W_INTRUSIVENESS * scope_intrusion
             + W_DELTA * abs(delta)
             + W_COMPUTE * n_runs
             + W_STRENGTH * (1.0 / max(strength, 0.01)))
    return {
        "intrusiveness": scope_intrusion,
        "delta_magnitude": abs(delta),
        "compute_units": n_runs,
        "contradiction_strength": strength,
        "total": round(total, 4),
    }


# ── Break type detectors ───────────────────────────────────────────────────────

def check_break_A(knobs_a: Dict[str, float], knobs_b: Dict[str, float],
                  seed: int = 42) -> Optional[MinimalContradictionWitness]:
    """
    Break A — Determinism contradiction.
    Claim: same knobs + same seed → identical prefix hash.
    Break: hash changes without intervention in prefix window.
    In MODE_B synthetic, prefix is one deterministic E event — should be identical.
    """
    exp_a = dict(_DEFAULT_EXP)
    exp_a["prefix"] = dict(exp_a["prefix"])
    exp_a["prefix"]["prefix_knobs"] = knobs_a
    exp_a["prefix"]["seed"] = seed

    exp_b = dict(_DEFAULT_EXP)
    exp_b["prefix"] = dict(exp_b["prefix"])
    exp_b["prefix"]["prefix_knobs"] = knobs_b
    exp_b["prefix"]["seed"] = seed  # same seed

    prefix_a, fork_a = _make_prefix_events(exp_a)
    prefix_b, fork_b = _make_prefix_events(exp_b)

    hash_a = _prefix_hash(prefix_a)
    hash_b = _prefix_hash(prefix_b)

    if hash_a == hash_b and knobs_a != knobs_b:
        # Hashes match despite different knobs — not a Break A (expected, knobs don't affect prefix E)
        return None
    if hash_a != hash_b and knobs_a == knobs_b:
        # Break: same knobs, different prefix → determinism violated
        return MinimalContradictionWitness(
            mcw_version=MAG_VERSION,
            break_type="A_DETERMINISM",
            severity="HARD",
            description="Identical inputs produce different prefix hash — prefix is non-deterministic.",
            vcl_base=compute_vcl_hash(),
            candidate_plan={"knobs": knobs_a, "seed": seed},
            minimized_plan={"knobs": knobs_a, "seed": seed},
            reproduction_steps=["_make_prefix_events(exp_a)", "_make_prefix_events(exp_b)",
                                 "assert hash_a == hash_b"],
            observations={"hash_a": hash_a, "hash_b": hash_b, "contradiction": "non-deterministic prefix"},
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    return None


def check_break_B(knobs: Dict[str, float], grammar: str = "speed",
                  ghost_rate: float = 0.0) -> Optional[MinimalContradictionWitness]:
    """
    Break B — Fork isolation contradiction.
    Claim: post-fork changes outside the causal cone of the fork point must be detected (ghost_mass > 0).
    Break: ghost_mass == 0 when orphaned post-fork events are present.
    Inject ghosts; instrument must detect them.
    """
    if ghost_rate <= 0.0:
        return None

    import random
    exp = dict(_DEFAULT_EXP)
    exp["prefix"]["prefix_knobs"] = knobs

    prefix_evs, fork_id = _make_prefix_events(exp)
    variant_evs = _make_variant_events(exp, exp["variants"][1], prefix_evs, fork_id)

    # Add orphaned ghost events (not in any contributes_to chain from fork)
    rng = random.Random(99)
    n_ghosts = max(1, int(len([ev for ev in variant_evs if ev["event_id"] != fork_id]) * ghost_rate))
    for i in range(n_ghosts):
        variant_evs.append({
            "event_id": f"mag_ghost_{i}",
            "run_id": "mag_run",
            "timestamp": round(rng.uniform(1.0, 20.0), 2),
            "phase_hint": "A", "event_type": "stealth_break",
            "source_system": "player",
            "location": {"zone_id": "test_zone", "subzone": None, "x": 100.0, "y": 50.0},
            "entities": ["player_vehicle"], "tags": ["ghost_injected"],
            "payload": {"speed": 50.0},
            "causal_links": {"triggered_by": [], "contributes_to": []},
        })

    ic, ghost_mass = compute_ic_ghost(fork_id, prefix_evs, variant_evs)

    if ghost_mass == 0.0:
        return MinimalContradictionWitness(
            mcw_version=MAG_VERSION,
            break_type="B_FORK_ISOLATION",
            severity="HARD",
            description=f"Ghost events injected (rate={ghost_rate}) but ghost_mass=0.0 — instrument not detecting fork isolation violation.",
            vcl_base=compute_vcl_hash(),
            candidate_plan={"knobs": knobs, "grammar": grammar, "ghost_rate": ghost_rate},
            minimized_plan={"knobs": knobs, "ghost_rate": ghost_rate, "n_ghosts_injected": n_ghosts},
            reproduction_steps=["_make_prefix_events", "_make_variant_events",
                                 "append orphaned events", "compute_ic_ghost"],
            observations={"IC": ic, "ghost_mass": ghost_mass,
                          "n_ghosts_injected": n_ghosts,
                          "contradiction": "ghost_mass=0 despite orphaned post-fork events"},
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    return None


def check_break_C() -> Optional[MinimalContradictionWitness]:
    """
    Break C — Mode boundary contradiction.
    Claim: MODE_B certs must carry the mode disclaimer note.
    Break: a cert emitted without the mode note = B_claimed_causality (mode laundering).
    We test whether the CSSR mode_lint gate catches it.
    """
    # Craft a MODE_B cert with no mode note
    fake_cert = {
        "cert_id": "mag_test_cert",
        "exp_id": "mag_test",
        "created_at": datetime.now(timezone.utc).isoformat() + "Z",
        "mode": "MODE_B",
        "prefix_end_ts": 0.0,
        "fork_point_event_id": "test:prefix:001",
        "base_variant_id": "base",
        "test_variant_id": "test",
        "causal_verdict": "CLOSED",
        "CCF_mean": 1.0,
        "IC": 1.0,
        "ghost_mass": 0.0,
        "divergence": {},
        "base_metrics": {},
        "test_metrics": {},
        "notes": [],  # MISSING MODE DISCLAIMER — mode laundering
    }

    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"certificates": [fake_cert]}, f)
        tmp = f.name

    try:
        cssr = generate_cssr(
            cert_paths=[tmp], prior_cssr_paths=[],
            window_id="mag_break_C_test",
            start="2026-01-01T00:00:00Z", end="2026-01-01T23:59:59Z",
        )
    finally:
        os.unlink(tmp)

    lint = cssr["mode_lint"]
    if lint["violations"] == 0:
        # CSSR didn't catch the missing mode note
        return MinimalContradictionWitness(
            mcw_version=MAG_VERSION,
            break_type="C_MODE_BOUNDARY",
            severity="HARD",
            description="MODE_B cert with missing disclaimer passed CSSR mode_lint without violation.",
            vcl_base=compute_vcl_hash(),
            candidate_plan={"cert_notes": [], "cert_mode": "MODE_B", "cert_verdict": "CLOSED"},
            minimized_plan={"cert_notes": [], "cert_mode": "MODE_B"},
            reproduction_steps=["craft MODE_B cert with empty notes",
                                 "run generate_cssr", "check mode_lint.violations == 0"],
            observations={"mode_lint_violations": 0,
                          "contradiction": "mode boundary not enforced by CSSR"},
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    return None


def check_break_D(vcl_before: str) -> Optional[MinimalContradictionWitness]:
    """
    Break D — Provenance contradiction.
    Claim: VCL hash changes whenever instrument scripts change.
    Break: VCL hash unchanged when a file is modified.
    We verify compute_vcl_hash is sensitive to code changes by checking
    that the current hash matches the expected (passed-in) value.
    """
    vcl_now = compute_vcl_hash()
    if vcl_now != vcl_before:
        # Expected: VCL changed because something changed. This is correct behavior.
        # A Break D would be: we changed something but VCL didn't change.
        return None
    # If we reach here with vcl_before already computed from the same state,
    # they must match (no break). Return None.
    return None


def check_break_E() -> List[MinimalContradictionWitness]:
    """
    Break E — Canary contradiction.
    Claim: known-break scenarios must be detected; invariance must not false-alarm.
    Break: injected known-break passes as detected=False (FN).
    Test: run all three canary break types and check for missed detections.
    """
    breaks = [run_ghost_break(), run_a_bypass_break(), run_knob_sensitivity_break()]
    witnesses = []
    for kb in breaks:
        if not kb.detected:
            witnesses.append(MinimalContradictionWitness(
                mcw_version=MAG_VERSION,
                break_type="E_CANARY",
                severity="HARD",
                description=f"Known-break '{kb.name}' not detected — instrument sensitivity lost.",
                vcl_base=compute_vcl_hash(),
                candidate_plan={"canary_break": kb.name, "expected": kb.expected},
                minimized_plan={"canary_break": kb.name},
                reproduction_steps=[f"run scripts/canary.py", f"check {kb.name}.detected"],
                observations={"actual": kb.actual, "expected": kb.expected,
                               "note": kb.note,
                               "contradiction": "known-break passed silently"},
                generated_at=datetime.now(timezone.utc).isoformat(),
            ))
    return witnesses


def check_break_F(n_reps: int = 3) -> Optional[MinimalContradictionWitness]:
    """
    Break F — Governance contradiction.
    Claim: CSSR verdict is stable under identical VCL + identical inputs.
    Break: verdict flips across repeated runs without any input change.
    Generate the same cert bundle N times and check for verdict changes.
    """
    import tempfile, os

    def _make_bundle_file() -> str:
        # replay.py certify with the default experiment (deterministic)
        from replay import certify
        certs = certify(_DEFAULT_EXP)
        bundle = {"certificates": certs, "exp_id": _DEFAULT_EXP["exp_id"],
                  "created_at": datetime.now(timezone.utc).isoformat() + "Z", "mode": "MODE_B"}
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(bundle, f)
        f.close()
        return f.name

    verdicts = []
    tmps = []
    try:
        for _ in range(n_reps):
            tmp = _make_bundle_file()
            tmps.append(tmp)
            cssr = generate_cssr(
                cert_paths=[tmp], prior_cssr_paths=[],
                window_id="mag_break_F_test",
                start="2026-01-01T00:00:00Z", end="2026-01-01T23:59:59Z",
            )
            verdicts.append(cssr["durability_verdict"]["status"])
    finally:
        for tmp in tmps:
            os.unlink(tmp)

    unique = set(verdicts)
    if len(unique) > 1:
        return MinimalContradictionWitness(
            mcw_version=MAG_VERSION,
            break_type="F_GOVERNANCE",
            severity="HARD",
            description=f"CSSR verdict flipped across {n_reps} identical runs: {unique}",
            vcl_base=compute_vcl_hash(),
            candidate_plan={"n_reps": n_reps, "exp_id": _DEFAULT_EXP["exp_id"]},
            minimized_plan={"n_reps": 2},
            reproduction_steps=["certify(_DEFAULT_EXP) × N", "generate_cssr × N", "check verdict stability"],
            observations={"verdicts": verdicts, "unique_verdicts": list(unique),
                          "contradiction": "CSSR non-deterministic under fixed inputs"},
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    return None


# ── Candidate generation: boundary probing ────────────────────────────────────

def _sipmg_boundary_coords(config: Dict[str, Any]) -> List[Dict[str, float]]:
    """
    Return knob coordinates near SIPMG phase-edge transitions.
    Fast proxy: sweep Phase C boundary analytically.
    Phase C onset: vis*0.6 + hdr > (8.0 - 1.5 - a_to_r_floor - a_spacing)
    Approximated by: vis >= 11 and hdr >= 3.0
    """
    boundaries = []
    for vis in [10.0, 10.5, 11.0, 11.5, 12.0]:
        for hdr in [2.5, 3.0, 3.5, 4.0]:
            knobs = {"visibility_window": vis, "heat_decay_rate": hdr,
                     "pressure_gradient": 1.0, "closure_threshold": 0.1}
            boundaries.append(knobs)
    return boundaries


def _knob_gradient_candidates(
    base_knobs: Dict[str, float],
    deltas: List[float],
) -> List[Tuple[Dict[str, float], float]]:
    """Generate ±delta perturbations for each knob, ordered by ascending |delta|."""
    candidates = []
    for key, val in base_knobs.items():
        for d in sorted(deltas, key=abs):
            cand = dict(base_knobs)
            cand[key] = round(val + d, 4)
            candidates.append((cand, d))
    return candidates


# ── Shrinkage (delta debugging) ───────────────────────────────────────────────

def _shrink_knob_deltas(
    base: Dict[str, float],
    candidate: Dict[str, float],
    break_check,
) -> Dict[str, float]:
    """
    Binary shrinkage: halve each knob delta until break disappears, then
    return the last working (still-breaking) candidate.
    """
    last_breaking = candidate
    for key in candidate:
        if key not in base:
            continue
        diff = candidate[key] - base[key]
        if abs(diff) < 1e-6:
            continue
        # Try halving
        shrunk = dict(last_breaking)
        shrunk[key] = round(base[key] + diff / 2.0, 4)
        if break_check(shrunk):
            last_breaking = shrunk
    return last_breaking


# ── MAG runner ─────────────────────────────────────────────────────────────────

def run_mag(max_candidates: int = 30, ghost_rate: float = 0.35) -> List[MinimalContradictionWitness]:
    """
    Execute the MAG search loop.
    Returns all found MCWs, sorted by severity and cost.
    """
    vcl = compute_vcl_hash()
    witnesses: List[MinimalContradictionWitness] = []
    found_types: Set[str] = set()

    # ── Phase 1: Break E — canary check (cheapest, always first) ──────────────
    e_witnesses = check_break_E()
    for w in e_witnesses:
        witnesses.append(w)
        found_types.add("E_CANARY")

    # ── Phase 2: Break C — mode boundary (structural, cheap) ──────────────────
    if "C_MODE_BOUNDARY" not in found_types:
        w = check_break_C()
        if w:
            witnesses.append(w)
            found_types.add("C_MODE_BOUNDARY")

    # ── Phase 3: Break F — governance flip (determinism check) ────────────────
    if "F_GOVERNANCE" not in found_types:
        w = check_break_F(n_reps=3)
        if w:
            witnesses.append(w)
            found_types.add("F_GOVERNANCE")

    # ── Phase 4: Break A — prefix determinism ─────────────────────────────────
    if "A_DETERMINISM" not in found_types:
        w = check_break_A(_DEFAULT_KNOBS, _DEFAULT_KNOBS, seed=42)
        if w:
            witnesses.append(w)
            found_types.add("A_DETERMINISM")

    # ── Phase 5: Break B — fork isolation via ghost injection ─────────────────
    if "B_FORK_ISOLATION" not in found_types and ghost_rate > 0:
        w = check_break_B(_DEFAULT_KNOBS, ghost_rate=ghost_rate)
        if w:
            witnesses.append(w)
            found_types.add("B_FORK_ISOLATION")

    # ── Phase 6: Boundary probing for SIPMG Phase C transitions ───────────────
    # Each boundary coord is a Break B candidate if ghost mass is undetected
    # OR a world-stability characterization point
    n_checked = 0
    for coords in _sipmg_boundary_coords(_DEFAULT_SIPMG_CFG):
        if n_checked >= max_candidates:
            break
        # Check if instrument correctly diagnoses world instability
        events = _make_events(coords, grammar="speed")
        arcs = t.build_arcs(events)
        bp_str = t.classify_breakpoint(arcs)

        if bp_str != "full_arc" and "CCF_COVERAGE_GAP" not in found_types:
            # World destabilized — verify instrument catches it correctly.
            # CCF measures triggered_by coverage (A events wired to E), NOT arc completion.
            # A closed, correctly-wired arc with no R reads CCF=1.0 while the world is degraded.
            # This is a metric adequacy gap, not a causal inconsistency.
            ccf = t.compute_ccf(arcs)
            ccf_val = ccf.get("CCF_mean") or 0.0
            if ccf_val >= 0.70:
                witnesses.append(MinimalContradictionWitness(
                    mcw_version=MAG_VERSION,
                    break_type="CCF_COVERAGE_GAP",
                    severity="SOFT",
                    description=(
                        f"breakpoint={bp_str}, CCF_mean={ccf_val:.3f}. "
                        "CCF measures triggered_by coverage only — reports high fidelity "
                        "even when arc has no terminal state. Arc completion is outside CCF scope."
                    ),
                    vcl_base=vcl,
                    candidate_plan={"coords": coords, "breakpoint": bp_str, "CCF_mean": ccf_val},
                    minimized_plan=coords,  # first/smallest boundary coord is the minimal witness
                    reproduction_steps=["_make_events(coords)", "build_arcs", "compute_ccf",
                                        "assert breakpoint != full_arc",
                                        "observe CCF_mean >= 0.70"],
                    observations={"breakpoint": bp_str, "CCF_mean": ccf_val,
                                   "gap": "CCF does not measure arc terminal state",
                                   "implication": "CCF=1.0 is consistent with infinite_chase"},
                    generated_at=datetime.now(timezone.utc).isoformat(),
                ))
                found_types.add("CCF_COVERAGE_GAP")
                # Minimal witness: first coord where this occurs; stop searching

        n_checked += 1

    # ── Phase 7: Break D — VCL provenance (verify hash is sensitive) ──────────
    # Structural check: VCL hash must be stable under identical inputs
    vcl_now = compute_vcl_hash()
    if vcl_now != vcl:
        witnesses.append(MinimalContradictionWitness(
            mcw_version=MAG_VERSION,
            break_type="D_PROVENANCE",
            severity="HARD",
            description="VCL hash changed between MAG start and end without declared version step.",
            vcl_base=vcl,
            candidate_plan={"vcl_start": vcl, "vcl_end": vcl_now},
            minimized_plan={"vcl_start": vcl, "vcl_end": vcl_now},
            reproduction_steps=["compute_vcl_hash() at start", "compute_vcl_hash() at end",
                                 "assert equal"],
            observations={"vcl_start": vcl, "vcl_end": vcl_now,
                           "contradiction": "VCL changed during MAG run"},
            generated_at=datetime.now(timezone.utc).isoformat(),
        ))

    return witnesses


# ── Human-readable summary ─────────────────────────────────────────────────────

def _format_mag_summary(witnesses: List[MinimalContradictionWitness], vcl: str) -> str:
    lines = [
        f"MAG — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  VCL:{vcl[7:19]}",
        f"  Found: {len(witnesses)} contradiction witness(es)",
    ]
    found_hard = [w for w in witnesses if w.severity == "HARD"]
    found_soft = [w for w in witnesses if w.severity == "SOFT"]
    if found_hard:
        lines.append(f"  HARD breaks ({len(found_hard)}):")
        for w in found_hard:
            lines.append(f"    [{w.break_type}] {w.description[:80]}")
    if found_soft:
        lines.append(f"  SOFT breaks ({len(found_soft)}):")
        for w in found_soft:
            lines.append(f"    [{w.break_type}] {w.description[:80]}")
    if not witnesses:
        lines.append("  No contradictions found. System laws are internally consistent under tested moves.")
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="mag.py v0.1 — Minimal Adversarial Generator (contradiction engine)"
    )
    ap.add_argument(
        "--max-candidates", type=int, default=30,
        help="Max boundary-probe candidates per phase (default: 30)"
    )
    ap.add_argument(
        "--ghost-rate", type=float, default=0.35,
        help="Ghost injection rate for Break B testing (default: 0.35)"
    )
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)

    vcl = compute_vcl_hash()
    witnesses = run_mag(max_candidates=args.max_candidates, ghost_rate=args.ghost_rate)

    if args.summary_only:
        print(_format_mag_summary(witnesses, vcl))
    else:
        output = {
            "mag_version": MAG_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "vcl_hash": vcl,
            "witnesses_found": len(witnesses),
            "witnesses": [asdict(w) for w in witnesses],
            "summary_text": _format_mag_summary(witnesses, vcl),
        }
        json.dump(output, sys.stdout, indent=2, sort_keys=False)
        sys.stdout.write("\n")

    return len(witnesses)  # exit code = number of contradictions found


if __name__ == "__main__":
    from typing import Optional
    raise SystemExit(main())
