#!/usr/bin/env python3
"""
canary.py — Instrument sensitivity self-test v0.1

Detects silent evaluator collapse (Region C: high stability / low sensitivity).

Runs three known-break scenarios. Each is a deliberate causal violation that
the instrument MUST catch. If a known-break passes silently, the instrument is
dulling — metrics are stable but detection power is gone.

Known-break scenarios:

  ghost_break:       Post-fork event with no causal ancestry from fork point.
                     Expected: ghost_mass > GHOST_FLOOR (compute_ic_ghost detects disconnection).
                     Silent: ghost_mass == 0 despite orphaned post-fork event.

  a_bypass_break:    R event directly triggered by E, with no A events.
                     Expected: arc classified as instant_collapse (select_resolution gates R).
                     Silent: arc classified as full_arc (A-gate not enforced).

  knob_sensitivity:  Large pressure_gradient shift (1.0 → 6.0).
                     Expected: |APC_test − APC_base| >= APC_DELTA_FLOOR.
                     Silent: APC delta < floor (instrument insensitive to large knob change).

Canary status (lexicographic):
  ALIVE:            All 3 known-breaks detected.
  DULLING:          1–2 known-breaks missed (sensitivity degrading).
  SILENT_COLLAPSE:  0 known-breaks detected (instrument non-responsive).

Output:
  JSON to stdout (default) or --summary-only text block.
  Designed to be piped into cssr.py via --canary-result (future integration).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import triage as t
from replay import compute_ic_ghost
from synthetic import RunBlueprint, ArcBlueprint, generate_run, knobs_to_arc_blueprint

CANARY_VERSION = "0.1"

# ── Sensitivity thresholds ─────────────────────────────────────────────────────

GHOST_FLOOR         = 0.10   # ghost_mass must exceed this for detection
APC_DELTA_FLOOR     = 0.10   # |APC_test - APC_base| minimum for sensitivity detection
KNOB_PG_BASE        = 1.0
KNOB_PG_TEST        = 10.0   # large shift (7 units); produces a_count 1→7, APC delta ~0.14


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class KnownBreak:
    name: str
    description: str
    expected_signature: str
    detected: bool
    expected: Dict[str, Any]
    actual: Dict[str, Any]
    note: str = ""


@dataclass
class CanaryReport:
    canary_version: str
    generated_at: str
    status: str           # ALIVE | DULLING | SILENT_COLLAPSE
    breaks_run: int
    breaks_detected: int
    detection_rate: float
    known_breaks: List[KnownBreak]
    summary_text: str
    notes: List[str] = field(default_factory=list)


# ── Event stream builders ──────────────────────────────────────────────────────

def _base_ev(eid: str, run_id: str, ts: float, phase: str, etype: str,
             triggered_by: List[str], contributes_to: List[str]) -> Dict[str, Any]:
    return {
        "event_id": eid,
        "run_id": run_id,
        "timestamp": ts,
        "phase_hint": phase,
        "event_type": etype,
        "source_system": "canary",
        "location": {"zone_id": "canary_zone", "subzone": None, "x": 100.0, "y": 50.0},
        "entities": ["player_vehicle"],
        "tags": [],
        "payload": {"heat_delta": 0.3 if phase == "E" else (-0.5 if phase == "R" else 0.0)},
        "causal_links": {"triggered_by": triggered_by, "contributes_to": contributes_to},
    }


def _ghost_break_streams() -> Tuple[List[Dict], List[Dict]]:
    """
    Prefix: one E event (fork anchor).
    Variant: correctly-wired A + R, plus one orphaned ghost A event.

    Ghost event has no causal link to fork — it is a real event but causally
    opaque. compute_ic_ghost must detect it as ghost_mass > 0.
    """
    fork_id = "canary_ghost:E:001"
    a_id    = "canary_ghost:A:001"
    r_id    = "canary_ghost:R:001"
    ghost_id = "canary_ghost:GHOST:001"

    prefix = [
        _base_ev(fork_id, "canary_ghost", 0.0, "E", "line_of_sight_spotted",
                 [], [a_id])   # fork contributes_to only the wired A, not the ghost
    ]
    variant = [
        _base_ev(fork_id, "canary_ghost", 0.0, "E", "line_of_sight_spotted",
                 [], [a_id]),
        _base_ev(a_id, "canary_ghost", 6.0, "A", "route_change",
                 [fork_id], [r_id]),
        _base_ev(r_id, "canary_ghost", 18.0, "R", "pursuit_lost",
                 [a_id], []),
        _base_ev(ghost_id, "canary_ghost", 10.0, "A", "stealth_break",
                 [], []),   # orphan: no triggered_by linking to fork
    ]
    return prefix, variant


def _a_bypass_stream() -> List[Dict]:
    """
    E event directly contributes_to R — no A events between them.
    R has triggered_by=[fork_id], dt=15s (above MIN_E_TO_R_SECONDS).

    select_resolution requires arc.has_a. Without A, R must not be promoted.
    Expected arc breakpoint: instant_collapse (not full_arc).
    """
    fork_id = "canary_bypass:E:001"
    r_id    = "canary_bypass:R:001"

    return [
        _base_ev(fork_id, "canary_bypass", 0.0, "E", "line_of_sight_spotted",
                 [], [r_id]),
        _base_ev(r_id, "canary_bypass", 15.0, "R", "pursuit_lost",
                 [fork_id], []),
    ]


def _knob_sensitivity_streams() -> Tuple[List[Dict], List[Dict]]:
    """
    Two synthetic runs: base (pressure_gradient=1.0) and test (pressure_gradient=6.0).
    Large knob shift must produce measurable APC delta.
    """
    base_knobs = {"heat_decay_rate": 1.0, "visibility_window": 3.0,
                  "pressure_gradient": KNOB_PG_BASE, "closure_threshold": 0.5}
    test_knobs = {**base_knobs, "pressure_gradient": KNOB_PG_TEST}

    base_bp = knobs_to_arc_blueprint(base_knobs)
    test_bp = knobs_to_arc_blueprint(test_knobs)

    base_run = RunBlueprint(run_id="canary_sens_base", arcs=[base_bp], seed=7)
    test_run = RunBlueprint(run_id="canary_sens_test", arcs=[test_bp], seed=7)

    return generate_run(base_run), generate_run(test_run)


# ── Individual break runners ───────────────────────────────────────────────────

def run_ghost_break() -> KnownBreak:
    prefix, variant = _ghost_break_streams()
    fork_id = prefix[0]["event_id"]

    ic, ghost_mass = compute_ic_ghost(fork_id, prefix, variant)
    detected = ghost_mass > GHOST_FLOOR

    return KnownBreak(
        name="ghost_break",
        description="Post-fork orphaned event with no causal ancestry from fork point",
        expected_signature=f"ghost_mass > {GHOST_FLOOR}",
        detected=detected,
        expected={"ghost_mass_gt": GHOST_FLOOR},
        actual={"IC": ic, "ghost_mass": ghost_mass},
        note="" if detected else
              f"SILENT: ghost_mass={ghost_mass:.3f}, expected >{GHOST_FLOOR}. "
              "Instrument not detecting causally-disconnected post-fork events.",
    )


def run_a_bypass_break() -> KnownBreak:
    events = _a_bypass_stream()
    arcs = t.build_arcs(events)

    breakpoint_ = arcs[0].breakpoint if arcs else "no_arcs"
    detected = breakpoint_ != "full_arc"

    return KnownBreak(
        name="a_bypass_break",
        description="R directly triggered by E with no A events (select_resolution gate test)",
        expected_signature="breakpoint != full_arc (instant_collapse expected)",
        detected=detected,
        expected={"breakpoint_not": "full_arc", "expected_value": "instant_collapse"},
        actual={
            "breakpoint": breakpoint_,
            "arc_count": len(arcs),
            "has_a": arcs[0].has_a if arcs else None,
            "has_r": arcs[0].has_r if arcs else None,
            "r_candidates": len(arcs[0].r_candidates) if arcs else 0,
        },
        note="" if detected else
              f"SILENT: breakpoint='{breakpoint_}'. select_resolution gate not enforced — "
              "R promoted without A. A-space no longer a necessary condition for resolution.",
    )


def run_knob_sensitivity_break() -> KnownBreak:
    base_events, test_events = _knob_sensitivity_streams()

    base_arcs = t.build_arcs(base_events)
    test_arcs = t.build_arcs(test_events)

    base_apc = t.compute_apc(base_arcs).get("APC_mean") or 0.0
    test_apc = t.compute_apc(test_arcs).get("APC_mean") or 0.0
    delta = abs(test_apc - base_apc)
    detected = delta >= APC_DELTA_FLOOR

    return KnownBreak(
        name="knob_sensitivity",
        description=f"Large pressure_gradient shift ({KNOB_PG_BASE}→{KNOB_PG_TEST}): "
                    "APC must show measurable structural change",
        expected_signature=f"|APC_test - APC_base| >= {APC_DELTA_FLOOR}",
        detected=detected,
        expected={
            "apc_delta_gte": APC_DELTA_FLOOR,
            "pg_base": KNOB_PG_BASE,
            "pg_test": KNOB_PG_TEST,
        },
        actual={
            "APC_base": round(base_apc, 4),
            "APC_test": round(test_apc, 4),
            "apc_delta": round(delta, 4),
        },
        note="" if detected else
              f"SILENT: |ΔAPC|={delta:.4f} < {APC_DELTA_FLOOR}. "
              f"Instrument insensitive to pg={KNOB_PG_BASE}→{KNOB_PG_TEST} shift. "
              "Either APC is saturated or knob→metric coupling is broken.",
    )


# ── Summary ────────────────────────────────────────────────────────────────────

def _format_summary(report: CanaryReport) -> str:
    lines = [
        f"CANARY — {report.generated_at[:10]}",
        f"  Status: {report.status} ({report.breaks_detected}/{report.breaks_run} breaks detected)",
    ]
    for kb in report.known_breaks:
        icon = "OK" if kb.detected else "MISSED"
        lines.append(f"  [{icon}] {kb.name}: {kb.expected_signature}")
        if not kb.detected:
            lines.append(f"       → {kb.note}")
    return "\n".join(lines)


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_canary() -> CanaryReport:
    breaks = [
        run_ghost_break(),
        run_a_bypass_break(),
        run_knob_sensitivity_break(),
    ]

    detected = sum(1 for b in breaks if b.detected)
    n = len(breaks)
    rate = round(detected / n, 4)

    if detected == n:
        status = "ALIVE"
    elif detected >= 1:
        status = "DULLING"
    else:
        status = "SILENT_COLLAPSE"

    notes: List[str] = []
    if status == "ALIVE":
        notes.append(
            "All known-break signatures detected. Instrument sensitivity confirmed. "
            "Stable CSSR readings are meaningful (not Region C)."
        )
    elif status == "DULLING":
        missed = [b.name for b in breaks if not b.detected]
        notes.append(
            f"Missed: {missed}. Instrument losing sensitivity. "
            "CSSR stability readings may mask real change. Investigate before trusting STABLE verdict."
        )
    else:
        notes.append(
            "ALL known-breaks missed. Instrument is non-responsive. "
            "STABLE CSSR readings are meaningless. Do not ship."
        )

    report = CanaryReport(
        canary_version=CANARY_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        breaks_run=n,
        breaks_detected=detected,
        detection_rate=rate,
        known_breaks=breaks,
        summary_text="",
        notes=notes,
    )
    report.summary_text = _format_summary(report)
    return report


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="canary.py v0.1 — instrument sensitivity self-test (Region C detector)"
    )
    ap.add_argument(
        "--summary-only", action="store_true",
        help="Print only the human-readable summary"
    )
    args = ap.parse_args(argv)

    report = run_canary()

    if args.summary_only:
        print(report.summary_text)
    else:
        def encode(obj: Any) -> Any:
            if hasattr(obj, "__dataclass_fields__"):
                return asdict(obj)
            raise TypeError(f"Unserializable: {type(obj)}")
        json.dump(report, sys.stdout, default=encode, indent=2, sort_keys=False)
        sys.stdout.write("\n")

    return 0 if report.status == "ALIVE" else 1


if __name__ == "__main__":
    from typing import Optional
    raise SystemExit(main())
