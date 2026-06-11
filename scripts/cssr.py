#!/usr/bin/env python3
"""
cssr.py — Causal System Stability Report (CSSR) v0.1

Aggregates CausalValidityCertificates (CVCs) from replay.py across a time
window and produces a single durability verdict.

Verdict logic is lexicographic — hard-cap violations gate to CRITICAL
regardless of aggregate metric stability. "Looks fine on average" cannot
mask intermittent causal dishonesty.

Thresholds (tune per deployment via module constants):

  G_HARD    = 0.40  ghost_mass_max hard cap  → CRITICAL if exceeded
  F_HARD    = 0.10  fork_integrity_fail_rate → CRITICAL if exceeded
  C_HARD    = 0.05  cert_flip_rate            → CRITICAL if exceeded
  CCF_FLOOR = 0.40  CCF_mean minimum          → CRITICAL if below

  G_SOFT    = 0.20  ghost_mass_p95 soft cap  → DEGRADED if sustained W windows
  CCF_WARN  = 0.55  CCF_mean warn threshold  → DEGRADED if trending toward
  DRIFT_EPS = 0.03  |ΔCCF_mean| per window   → WATCH if exceeded
  W_MIN     = 3     windows required for trend judgments

Inputs:
  --certs          Paths to CVC bundle JSONs (output of replay.py --certify)
  --prior-windows  Paths to prior CSSR JSONs, oldest first (for trend detection)
  --window-id      Human-readable window label (e.g. "2026-06-10_build_417")
  --start / --end  ISO 8601 time range for the window

Output (stdout):
  CSSR JSON (default) or --summary-only text block.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from registry.gatekeeper import Gatekeeper, GatekeeperResult

CSSR_VERSION = "0.1"

# ── Threshold constants ────────────────────────────────────────────────────────

G_HARD      = 0.40   # ghost_mass_max → CRITICAL
F_HARD      = 0.10   # fork_integrity_fail_rate → CRITICAL
C_HARD      = 0.05   # cert_flip_rate → CRITICAL
CCF_FLOOR   = 0.40   # CCF_mean minimum → CRITICAL

G_SOFT      = 0.20   # ghost_mass_p95 → DEGRADED if sustained
CCF_WARN    = 0.55   # CCF_mean → DEGRADED if trending toward
DRIFT_EPS   = 0.03   # |ΔCCF| per window → WATCH
W_MIN       = 3      # windows needed for trend judgments

MODE_NOTE_REQUIRED = "Not true bitwise-identical state capture"


# ── Numeric helpers ────────────────────────────────────────────────────────────

def _mean(values: List[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return round(math.sqrt(sum((v - m) ** 2 for v in values) / len(values)), 6)


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = (len(s) - 1) * p / 100.0
    lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (idx - lo), 6)


def _trend_slope(values: List[float]) -> float:
    """OLS slope over an ordered value list (units: value/step)."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = _mean(values)
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return round(num / den, 6) if den > 0 else 0.0


def _trend_direction(slope: float, eps: float = 0.002) -> str:
    if slope > eps:
        return "up"
    if slope < -eps:
        return "down"
    return "flat"


# ── Loading ────────────────────────────────────────────────────────────────────

def load_certs(paths: List[str]) -> List[Dict[str, Any]]:
    """
    Load CVCs from file paths. Accepts:
      - CVC bundle: output of `replay.py --certify` (has "certificates" key)
      - Single cert object (has "cert_id" key)
    """
    certs: List[Dict[str, Any]] = []
    for p in paths:
        raw = json.loads(Path(p).read_text(encoding="utf-8"))
        if "certificates" in raw:
            certs.extend(raw["certificates"])
        elif "cert_id" in raw:
            certs.append(raw)
        # Unknown shape: silently skip (will surface as missing data)
    return certs


def load_prior_windows(paths: List[str]) -> List[Dict[str, Any]]:
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]


# ── Computation axes ───────────────────────────────────────────────────────────

def compute_volume(certs: List[Dict[str, Any]]) -> Dict[str, Any]:
    mode_a = sum(1 for c in certs if c.get("mode") == "MODE_A")
    mode_b = sum(1 for c in certs if c.get("mode") == "MODE_B")
    exp_ids = {c.get("exp_id", "") for c in certs}
    return {
        "total_runs": len(certs),
        "cre_experiments": len(exp_ids),
        "modeA_certificates": mode_a,
        "modeB_certificates": mode_b,
    }


def compute_stability_metrics(
    certs: List[Dict[str, Any]],
    prior_windows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    ccf_values = [c["CCF_mean"] for c in certs if c.get("CCF_mean") is not None]
    ccf_mean = _mean(ccf_values)
    ccf_std  = _std(ccf_values)

    if prior_windows:
        prior_ccf = prior_windows[-1].get("stability", {}).get("CCF_mean", ccf_mean)
        ccf_drift = round(abs(ccf_mean - prior_ccf), 4)
    else:
        ccf_drift = 0.0

    apc_values = [
        c.get("test_metrics", {}).get("APC_mean")
        for c in certs
        if (c.get("test_metrics") or {}).get("APC_mean") is not None
    ]
    apc_mean = round(_mean(apc_values), 4) if apc_values else None

    return {
        "CCF_mean":            round(ccf_mean, 4),
        "CCF_std":             round(ccf_std, 4),
        "CCF_drift":           ccf_drift,
        "APC_mean":            apc_mean,
        "AEI_mean":            None,   # requires triage AEI in CVC; not yet in schema
        "R_island_count_mean": None,
    }


def compute_ghost_profile(
    certs: List[Dict[str, Any]],
    prior_windows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    masses = [c.get("ghost_mass", 0.0) for c in certs]
    current_mean = _mean(masses)
    p95  = _percentile(masses, 95)
    gmax = max(masses) if masses else 0.0

    series = [w.get("ghost_profile", {}).get("ghost_mass_mean", 0.0) for w in prior_windows]
    series.append(current_mean)
    slope = _trend_slope(series)

    return {
        "ghost_mass_mean":        round(current_mean, 4),
        "ghost_mass_p95":         round(p95, 4),
        "ghost_mass_max":         round(gmax, 4),
        "ghost_mass_trend":       _trend_direction(slope),
        "ghost_mass_trend_slope": slope,
    }


def compute_fork_integrity(
    certs: List[Dict[str, Any]],
    prior_windows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Fork violation: cert missing fork_point_event_id AND ghost_mass > 0.
    Causal link is broken — ghost mass present but no declared anchor.
    """
    violations = sum(
        1 for c in certs
        if (not c.get("fork_point_event_id")) and c.get("ghost_mass", 0.0) > 0.0
    )
    rate = round(violations / len(certs), 4) if certs else 0.0

    series = [w.get("fork_integrity", {}).get("fork_violation_rate", 0.0) for w in prior_windows]
    series.append(rate)
    slope = _trend_slope(series)

    return {
        "fork_violations":            violations,
        "fork_violation_rate":        rate,
        "fork_violation_trend":       _trend_direction(slope),
        "fork_violation_trend_slope": slope,
        "prefix_hash_mismatch_rate":  0.0,  # MODE_A only; not yet implemented
    }


def compute_mode_lint(certs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    WARN:   MODE_B cert missing the required mode disclaimer note.
    SEVERE: cert with no 'mode' field — replay integrity unverifiable.
    """
    violations = 0
    violation_types: Dict[str, int] = {}
    severity_max = "none"

    for c in certs:
        mode  = c.get("mode")
        notes = c.get("notes") or []

        if not mode:
            violations += 1
            violation_types["missing_mode"] = violation_types.get("missing_mode", 0) + 1
            severity_max = "SEVERE"
        elif mode == "MODE_B":
            if not any(MODE_NOTE_REQUIRED in n for n in notes):
                violations += 1
                violation_types["B_claimed_causality"] = (
                    violation_types.get("B_claimed_causality", 0) + 1
                )
                if severity_max == "none":
                    severity_max = "WARN"

    return {
        "violations":      violations,
        "violation_types": violation_types,
        "severity_max":    severity_max,
        "violation_rate":  round(violations / len(certs), 4) if certs else 0.0,
    }


def compute_cert_stability(
    certs: List[Dict[str, Any]],
    prior_windows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    modeA_cert_rate: fraction of certs that are MODE_A (fully certified).
    cert_flip_rate:  rate of same-scenario verdict flips within and across windows.
    """
    mode_a_count = sum(1 for c in certs if c.get("mode") == "MODE_A")
    mode_a_rate  = round(mode_a_count / len(certs), 4) if certs else 0.0

    # Within-window flips: same (exp_id, test_variant_id) → multiple distinct verdicts
    scenario_verdicts: Dict[Tuple[str, str], set] = {}
    for c in certs:
        key = (c.get("exp_id", ""), c.get("test_variant_id", ""))
        scenario_verdicts.setdefault(key, set()).add(c.get("causal_verdict", ""))
    within_flips = sum(1 for vs in scenario_verdicts.values() if len(vs) > 1)

    # Cross-window flips: compare against last prior window's cert snapshot
    cross_flips = 0
    if prior_windows:
        prior_snap: Dict[Tuple[str, str], str] = {
            (r.get("exp_id", ""), r.get("test_variant_id", "")): r.get("causal_verdict", "")
            for r in prior_windows[-1].get("_cert_snapshot", [])
        }
        for c in certs:
            key = (c.get("exp_id", ""), c.get("test_variant_id", ""))
            if key in prior_snap and prior_snap[key] != c.get("causal_verdict", ""):
                cross_flips += 1

    total_flips = within_flips + cross_flips
    flip_rate   = round(total_flips / max(len(certs), 1), 4)

    return {
        "modeA_cert_rate":          mode_a_rate,
        "cert_flip_rate":           flip_rate,
        "cert_flip_count":          total_flips,
        "within_window_flip_count": within_flips,
        "cross_window_flip_count":  cross_flips,
    }


# ── Lexicographic verdict ──────────────────────────────────────────────────────

def compute_verdict(
    ghost:     Dict[str, Any],
    fork:      Dict[str, Any],
    mode_lint: Dict[str, Any],
    cert_stab: Dict[str, Any],
    stability: Dict[str, Any],
    prior_windows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Priority order: CRITICAL → DEGRADED → WATCH → STABLE.
    A verdict at level N short-circuits all lower levels.
    """
    ccf_mean = stability.get("CCF_mean") or 0.0
    n_prior  = len(prior_windows)

    # ── CRITICAL ──────────────────────────────────────────────────────────────
    critical: List[str] = []

    if mode_lint["severity_max"] == "SEVERE":
        critical.append(
            f"mode_lint SEVERE: {mode_lint['violations']} cert(s) missing mode field"
        )
    if ghost["ghost_mass_max"] > G_HARD:
        critical.append(
            f"ghost_mass_max {ghost['ghost_mass_max']:.3f} > hard cap {G_HARD}"
        )
    if fork["fork_violation_rate"] > F_HARD:
        critical.append(
            f"fork_violation_rate {fork['fork_violation_rate']:.3f} > hard cap {F_HARD}"
        )
    if cert_stab["cert_flip_rate"] > C_HARD:
        critical.append(
            f"cert_flip_rate {cert_stab['cert_flip_rate']:.3f} > hard cap {C_HARD}"
        )
    if ccf_mean < CCF_FLOOR:
        critical.append(
            f"CCF_mean {ccf_mean:.3f} below admissible floor {CCF_FLOOR}"
        )

    if critical:
        return {
            "status": "CRITICAL",
            "reasons": critical,
            "confidence": round(max(0.0, 0.5 - 0.1 * (len(critical) - 1)), 2),
        }

    # ── DEGRADED ──────────────────────────────────────────────────────────────
    degraded: List[str] = []

    if n_prior >= W_MIN:
        fork_series = [
            w.get("fork_integrity", {}).get("fork_violation_rate", 0.0)
            for w in prior_windows[-W_MIN:]
        ] + [fork["fork_violation_rate"]]
        if _trend_slope(fork_series) > 0.005:
            degraded.append(
                f"fork_violation_rate increasing over {W_MIN + 1} windows "
                f"(slope={_trend_slope(fork_series):.4f})"
            )

        ccf_series = [
            w.get("stability", {}).get("CCF_mean", ccf_mean)
            for w in prior_windows[-W_MIN:]
        ] + [ccf_mean]
        ccf_slope = _trend_slope(ccf_series)
        if ccf_slope < -0.01 and ccf_mean < CCF_WARN:
            degraded.append(
                f"CCF_mean trending down ({ccf_slope:.4f}/window), "
                f"current {ccf_mean:.3f} approaching warn floor {CCF_WARN}"
            )

        g_p95_series = [
            w.get("ghost_profile", {}).get("ghost_mass_p95", 0.0)
            for w in prior_windows[-W_MIN:]
        ] + [ghost["ghost_mass_p95"]]
        if all(v > G_SOFT for v in g_p95_series):
            degraded.append(
                f"ghost_mass_p95 above soft cap {G_SOFT} for {W_MIN + 1} consecutive windows"
            )

    if mode_lint["violations"] > 0 and mode_lint["severity_max"] == "WARN":
        degraded.append(
            f"mode_lint WARN: {mode_lint['violation_types']}"
        )

    if degraded:
        return {
            "status": "DEGRADED",
            "reasons": degraded,
            "confidence": round(max(0.3, 0.7 - 0.05 * len(degraded)), 2),
        }

    # ── WATCH ─────────────────────────────────────────────────────────────────
    watch: List[str] = []

    if stability["CCF_drift"] > DRIFT_EPS:
        watch.append(
            f"CCF_mean drift {stability['CCF_drift']:.3f} exceeds epsilon {DRIFT_EPS}"
        )
    if ghost["ghost_mass_trend"] == "up":
        watch.append(
            f"ghost_mass trending up (slope={ghost['ghost_mass_trend_slope']:.4f})"
        )
    if fork["fork_violations"] > 0:
        watch.append(
            f"{fork['fork_violations']} fork violation(s) this window "
            f"(rate={fork['fork_violation_rate']:.3f}, {fork['fork_violation_trend']} trend)"
        )
    if cert_stab["cert_flip_count"] > 0:
        watch.append(f"{cert_stab['cert_flip_count']} cert flip(s) detected")

    if watch:
        return {
            "status": "WATCH",
            "reasons": watch,
            "confidence": round(max(0.5, 0.85 - 0.05 * len(watch)), 2),
        }

    # ── STABLE ────────────────────────────────────────────────────────────────
    return {
        "status": "STABLE",
        "reasons": [
            f"CCF_mean {ccf_mean:.3f} stable (drift={stability['CCF_drift']:.3f} < {DRIFT_EPS})",
            f"ghost_mass bounded (mean={ghost['ghost_mass_mean']:.3f}, "
            f"max={ghost['ghost_mass_max']:.3f}, {ghost['ghost_mass_trend']} trend)",
            f"fork_integrity: {fork['fork_violations']} violation(s), "
            f"rate={fork['fork_violation_rate']:.3f}, {fork['fork_violation_trend']} trend",
            "mode_lint: no violations",
        ],
        "confidence": 0.95,
    }


# ── Human-readable summary ────────────────────────────────────────────────────

def format_summary(cssr: Dict[str, Any]) -> str:
    v  = cssr["durability_verdict"]
    g  = cssr["ghost_profile"]
    f  = cssr["fork_integrity"]
    ml = cssr["mode_lint"]
    st = cssr["stability"]
    gk = cssr.get("gatekeeper", {})

    apc_str = f", APC={st['APC_mean']:.2f}" if st.get("APC_mean") is not None else ""
    gk_str  = "PASS" if gk.get("passed", True) else "BLOCK"
    gk_n    = len(gk.get("violations", []))

    lines = [
        f"CSSR — {cssr['window_id']}",
        f"  Gatekeeper: {gk_str} ({gk_n} violation(s))",
        f"  CCF {st['CCF_mean']:.2f} ± {st['CCF_std']:.2f}, drift={st['CCF_drift']:.3f}{apc_str}",
        f"  Ghost mass: mean={g['ghost_mass_mean']:.3f}, p95={g['ghost_mass_p95']:.3f}, "
        f"max={g['ghost_mass_max']:.3f}, {g['ghost_mass_trend']} trend",
        f"  Fork integrity: {f['fork_violations']} violation(s), "
        f"rate={f['fork_violation_rate']:.3f}, {f['fork_violation_trend']} trend",
        f"  Mode-lint: {ml['violations']} violation(s) [{ml['severity_max']}]",
        f"Verdict: {v['status']} (confidence={v['confidence']:.2f})",
    ]
    for r in v["reasons"]:
        lines.append(f"  • {r}")
    return "\n".join(lines)


# ── Generator ─────────────────────────────────────────────────────────────────

def generate_cssr(
    cert_paths:       List[str],
    prior_cssr_paths: List[str],
    window_id:        str,
    start:            str,
    end:              str,
) -> Dict[str, Any]:
    certs         = load_certs(cert_paths)
    prior_windows = load_prior_windows(prior_cssr_paths)

    if not certs:
        raise ValueError("No valid CausalValidityCertificates loaded.")

    # ── AEC enforcement (Rule 4) ───────────────────────────────────────────────
    gk        = Gatekeeper()
    gk_result = gk.enforce_cssr_input(certs)
    gk_dict   = gk_result.as_dict()

    volume    = compute_volume(certs)
    stability = compute_stability_metrics(certs, prior_windows)
    ghost     = compute_ghost_profile(certs, prior_windows)
    fork      = compute_fork_integrity(certs, prior_windows)
    mode_lint = compute_mode_lint(certs)
    cert_stab = compute_cert_stability(certs, prior_windows)
    verdict   = compute_verdict(ghost, fork, mode_lint, cert_stab, stability, prior_windows)

    # Gatekeeper BLOCK overrides all other verdicts.
    if gk_result.blocked:
        block_reasons = [v.message for v in gk_result.violations if v.severity == "BLOCK"]
        verdict = {
            "status": "CRITICAL",
            "reasons": block_reasons,
            "confidence": 0.0,
        }

    cssr: Dict[str, Any] = {
        "cssr_version":            CSSR_VERSION,
        "window_id":               window_id,
        "time_range":              {"start": start, "end": end},
        "generated_at":            datetime.now(timezone.utc).isoformat(),
        "gatekeeper":              gk_dict,
        "volume":                  volume,
        "certification_stability": cert_stab,
        "stability":               stability,
        "ghost_profile":           ghost,
        "fork_integrity":          fork,
        "mode_lint":               mode_lint,
        "durability_verdict":      verdict,
        # Compact cert snapshot for cross-window flip detection by the next run
        "_cert_snapshot": [
            {
                "exp_id":          c.get("exp_id"),
                "test_variant_id": c.get("test_variant_id"),
                "causal_verdict":  c.get("causal_verdict"),
                "mode":            c.get("mode"),
            }
            for c in certs
        ],
    }
    cssr["summary_text"] = format_summary(cssr)
    return cssr


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="cssr.py v0.1 — Causal System Stability Report generator"
    )
    ap.add_argument(
        "--certs", nargs="+", required=True,
        help="CVC bundle JSON files (output of replay.py --certify)"
    )
    ap.add_argument(
        "--prior-windows", nargs="*", default=[],
        help="Prior CSSR JSON files, oldest first (enables trend detection)"
    )
    ap.add_argument(
        "--window-id", default="",
        help="Human-readable window ID (e.g. '2026-06-10_build_417')"
    )
    ap.add_argument("--start", default="", help="Window start (ISO 8601)")
    ap.add_argument("--end",   default="", help="Window end (ISO 8601)")
    ap.add_argument(
        "--summary-only", action="store_true",
        help="Print only the human-readable summary text"
    )
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    if not args.window_id:
        args.window_id = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if not args.start:
        args.start = now.strftime("%Y-%m-%dT00:00:00Z")
    if not args.end:
        args.end = now.strftime("%Y-%m-%dT23:59:59Z")

    cssr = generate_cssr(
        cert_paths=args.certs,
        prior_cssr_paths=args.prior_windows or [],
        window_id=args.window_id,
        start=args.start,
        end=args.end,
    )

    if args.summary_only:
        print(cssr["summary_text"])
    else:
        json.dump(cssr, sys.stdout, indent=2, sort_keys=False)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    from typing import Optional
    raise SystemExit(main())
