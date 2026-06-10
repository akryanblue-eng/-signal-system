#!/usr/bin/env python3
"""
Calibration report generator.
Reads session JSON + perturbation files → outputs SHIP / TUNE / KILL verdict.

Verdict logic (derived, not scored):
  SHIP  — ≥4 of 5 signals pass AND no outside-envelope perturbations
  TUNE  — 2–3 signals OR any edge perturbations (no outside)
  KILL  — <2 signals OR any outside-envelope perturbation
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SIGNAL_LABELS = {
    "describes_route_not_mission":        "Player describes route (not mission)",
    "failure_produced_story_not_reset":   "Failure produced a story (not a reset)",
    "escape_has_location_mistake_recovery": "'I escaped because…' = location + mistake + recovery",
    "run_classified_without_rereading":   "Run classified without rereading framework",
    "breakpoint_class_under_30s":         "Breakpoint class identified in <30 seconds",
}


def load_session(path: Path) -> dict:
    return json.loads(path.read_text())


def load_perturbations_for_session(session: dict) -> list[dict]:
    refs = session.get("perturbation_refs", [])
    result = []
    for ref in refs:
        p_path = ROOT / "perturbations" / f"{ref}.json"
        if p_path.exists():
            result.append(json.loads(p_path.read_text()))
    return result


def derive_verdict(checks: dict, perturbations: list[dict]) -> tuple[str, str]:
    signals_passed = sum(1 for v in checks.values() if v)
    outside = [p for p in perturbations if p.get("envelope_classification") == "outside"]
    edge = [p for p in perturbations if p.get("envelope_classification") == "edge"]

    if outside or signals_passed < 2:
        reason = (
            f"identity broke in {len(outside)} perturbation(s)" if outside
            else f"only {signals_passed}/5 signals passed"
        )
        return "kill", reason

    if signals_passed < 4 or edge:
        parts = []
        if signals_passed < 4:
            parts.append(f"{signals_passed}/5 signals passed")
        if edge:
            parts.append(f"{len(edge)} edge perturbation(s) present")
        return "tune", "; ".join(parts)

    return "ship", f"all {signals_passed}/5 signals passed, envelope clean"


def render_report(session: dict, perturbations: list[dict], verdict: str, reason: str) -> str:
    checks = session["classifier_checks"]
    lines = [
        "=" * 56,
        "CALIBRATION REPORT",
        "=" * 56,
        f"Session:   {session['id']}",
        f"Tester:    {session['tester_id']}",
        f"Duration:  {session['duration_minutes']} min",
        "",
        "── Three Questions ─────────────────────────────────",
        f"One breath:      {session['q_one_breath']}",
        f"Regain control:  {session['q_regain_control']}",
        f"Clearest place:  {session['q_clearest_place']}",
        "",
        "── Go / No-Go Signals ──────────────────────────────",
    ]

    for key, label in SIGNAL_LABELS.items():
        mark = "✓" if checks.get(key) else "✗"
        lines.append(f"  {mark}  {label}")

    passed = sum(1 for v in checks.values() if v)
    lines.append(f"\n  {passed}/5 signals passed")

    if perturbations:
        lines.append("")
        lines.append("── Perturbation Envelope ───────────────────────────")
        counts = {"inside": 0, "edge": 0, "outside": 0}
        for p in perturbations:
            c = p.get("envelope_classification", "unknown")
            counts[c] = counts.get(c, 0) + 1
        for cls, n in counts.items():
            lines.append(f"  {cls:<10} {n}")

    notes = session.get("fragility_notes")
    if notes:
        lines.append("")
        lines.append("── Fragility Notes ─────────────────────────────────")
        lines.append(f"  {notes}")

    lines += [
        "",
        "=" * 56,
        f"VERDICT:  {verdict.upper()}",
        f"REASON:   {reason}",
        "=" * 56,
    ]

    if verdict == "ship":
        lines.append("Gate is real. System is producing classifiable outcomes.")
    elif verdict == "tune":
        lines.append("Gate is describing reality. Tighten deformation shaping.")
    else:
        lines.append("Gate failed. Identity broke or signals absent. Kill the slice.")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate calibration report and SHIP/TUNE/KILL verdict from a session file."
    )
    parser.add_argument("session_file", help="Path to session JSON file")
    parser.add_argument("--write-verdict", action="store_true",
                        help="Write derived verdict back into the session file")
    args = parser.parse_args()

    path = Path(args.session_file)
    if not path.exists():
        print(f"Session file not found: {path}", file=sys.stderr)
        return 1

    session = load_session(path)
    perturbations = load_perturbations_for_session(session)
    verdict, reason = derive_verdict(session["classifier_checks"], perturbations)

    print(render_report(session, perturbations, verdict, reason))

    if args.write_verdict:
        session["verdict"] = verdict
        session["verdict_notes"] = reason
        path.write_text(json.dumps(session, indent=2))
        print(f"\nVerdict written to {path.name}")

    return 0 if verdict == "ship" else 1


if __name__ == "__main__":
    sys.exit(main())
