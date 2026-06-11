#!/usr/bin/env python3
"""
visualize/build_driver.py — Visual Driver Builder v0.2

Reads sipmg_visual_params.json and produces:

  visual_driver.json      — { "ordered_points": [...] }  130 points, serpentine
                            traversal order. Even vis-rows: hdr ascending.
                            Odd vis-rows: hdr descending.

  driver_frames_720.json  — JSON array, 720 frames @ 24fps. Each frame maps
                            to a grid point via nearest-neighbor (no lerp).
                            Multiple frames share the same point (~5.5 frames
                            each) due to 720→130 expansion.

Serpentine traversal:
  Groups points by visibility_window (rounded to 6 decimals to avoid float
  noise splitting rows). Rows sorted by vis ascending. Within each row:
    even row index → heat_decay_rate ascending
    odd  row index → heat_decay_rate descending

Frame fields (verbatim copy from mapped point, no interpolation):
  frame     — frame index 0–719
  t         — frame_index / 24.0  (wall-clock seconds)
  phase, color_hex, brightness, glitch_freq, pulse_rate, noise_level,
  signal_integrity, breakpoint, is_boundary, coords   (all from source point)
  run_seed, run_id

run_seed = int(sha256(b"CHI-0001").hexdigest(), 16) % 10^9  = 634658948

CLI:
  python visualize/build_driver.py
      --input  experiments/sipmg_visual_params.json
      --driver experiments/visual_driver.json
      --frames experiments/driver_frames_720.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


FPS          = 24
TOTAL_FRAMES = 720
RUN_ID       = "CHI-0001"
_RUN_SEED    = int(hashlib.sha256(RUN_ID.encode()).hexdigest(), 16) % 10 ** 9

PHASE_PALETTE = {"A": "#00FF41", "B": "#FFB800", "C": "#FF4444", "D": "#FF00FF"}
_NUMERIC_FIELDS = ["brightness", "glitch_freq", "pulse_rate", "noise_level",
                   "signal_integrity"]


# ── Serpentine traversal ───────────────────────────────────────────────────────

def build_ordered_driver(visual_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort into serpentine order and return ordered_points list.

    Row key: round(visibility_window, 6)  — eliminates float noise.
    Row order: vis ascending.
    Within even rows: hdr ascending. Within odd rows: hdr descending.
    """
    rows: Dict[float, List[Dict]] = defaultdict(list)
    for p in visual_points:
        vis_key = round(p["coords"].get("visibility_window", 0.0), 6)
        rows[vis_key].append(p)

    ordered: List[Dict[str, Any]] = []
    for row_idx, vis_key in enumerate(sorted(rows.keys())):
        row = rows[vis_key]
        descending = (row_idx % 2 == 1)
        row_sorted = sorted(
            row,
            key=lambda p: round(p["coords"].get("heat_decay_rate", 0.0), 6),
            reverse=descending,
        )
        ordered.extend(row_sorted)

    result = []
    for i, p in enumerate(ordered):
        entry = dict(p)
        entry["grid_index"] = i
        entry["coords"] = {
            k: round(v, 6) for k, v in p["coords"].items()
        }
        result.append(entry)
    return result


# ── Frame expansion (nearest-neighbor, no lerp) ───────────────────────────────

_FRAME_FIELDS = ["phase", "color_hex", "brightness", "glitch_freq", "pulse_rate",
                 "noise_level", "signal_integrity", "breakpoint", "is_boundary",
                 "coords"]


def build_frames(
    ordered_points: List[Dict[str, Any]],
    n_frames: int = TOTAL_FRAMES,
    fps: int = FPS,
) -> List[Dict[str, Any]]:
    """
    Map n_frames to len(ordered_points) via nearest-neighbor.

    point_index = round(frame_index * (N-1) / (F-1))
    Multiple frames will share the same source point (~5.5 frames each).
    t = frame_index / fps  (independent wall-clock, not derived from grid).
    """
    n_pts  = len(ordered_points)
    frames: List[Dict[str, Any]] = []

    for i in range(n_frames):
        grid_t = i * (n_pts - 1) / (n_frames - 1)
        pt_idx = int(round(grid_t))
        pt_idx = max(0, min(pt_idx, n_pts - 1))
        src    = ordered_points[pt_idx]

        frame: Dict[str, Any] = {
            "frame":    i,
            "t":        round(i / fps, 10),
        }
        for f in _FRAME_FIELDS:
            frame[f] = src[f]
        frame["run_seed"] = _RUN_SEED
        frame["run_id"]   = RUN_ID
        frames.append(frame)

    return frames


# ── Sanity checks ─────────────────────────────────────────────────────────────

def sanity_check(
    ordered_points: List[Dict[str, Any]],
    frames: List[Dict[str, Any]],
) -> List[str]:
    issues: List[str] = []

    # ── visual_driver ──────────────────────────────────────────────────────────

    # 1. Length
    if len(ordered_points) != 130:
        issues.append(f"FAIL  ordered_points length={len(ordered_points)}, expected 130")

    # 2. Field presence and types
    for i, p in enumerate(ordered_points):
        if p["phase"] not in {"A", "B", "C", "D"}:
            issues.append(f"FAIL  ordered_points[{i}] phase={p['phase']} not in {{A,B,C,D}}")
        if "color_hex" not in p:
            issues.append(f"FAIL  ordered_points[{i}] missing color_hex")
        for f in _NUMERIC_FIELDS:
            v = p.get(f, None)
            if v is None:
                issues.append(f"FAIL  ordered_points[{i}] missing {f}")
            elif not (0.0 - 1e-9 <= v <= 1.0 + 1e-9):
                issues.append(f"FAIL  ordered_points[{i}] {f}={v} out of [0,1]")
        if not isinstance(p.get("is_boundary"), bool):
            issues.append(f"FAIL  ordered_points[{i}] is_boundary not bool: {p.get('is_boundary')}")
        if "visibility_window" not in p.get("coords", {}):
            issues.append(f"FAIL  ordered_points[{i}] missing coords.visibility_window")
        if "heat_decay_rate" not in p.get("coords", {}):
            issues.append(f"FAIL  ordered_points[{i}] missing coords.heat_decay_rate")

    # 3. Serpentine traversal: vis non-decreasing
    vis_vals = [round(p["coords"].get("visibility_window", 0), 6) for p in ordered_points]
    if vis_vals != sorted(vis_vals):
        # Identify where it goes wrong
        for i in range(1, len(vis_vals)):
            if vis_vals[i] < vis_vals[i-1]:
                issues.append(
                    f"FAIL  vis non-monotone at index {i}: "
                    f"{vis_vals[i-1]} → {vis_vals[i]}"
                )
                break

    # 4. Serpentine within each row
    rows: Dict[float, List[Tuple[int, float]]] = defaultdict(list)
    for i, p in enumerate(ordered_points):
        vis_key = round(p["coords"].get("visibility_window", 0), 6)
        hdr_val = round(p["coords"].get("heat_decay_rate", 0), 6)
        rows[vis_key].append((i, hdr_val))

    for row_idx, vis_key in enumerate(sorted(rows.keys())):
        row = rows[vis_key]
        hdr_seq = [h for _, h in row]
        if row_idx % 2 == 0:
            if hdr_seq != sorted(hdr_seq):
                issues.append(f"FAIL  even row vis={vis_key} hdr not ascending: {hdr_seq[:4]}...")
        else:
            if hdr_seq != sorted(hdr_seq, reverse=True):
                issues.append(f"FAIL  odd row vis={vis_key} hdr not descending: {hdr_seq[:4]}...")

    # ── driver_frames ──────────────────────────────────────────────────────────

    # 5. Length
    if len(frames) != TOTAL_FRAMES:
        issues.append(f"FAIL  frames length={len(frames)}, expected {TOTAL_FRAMES}")

    # 6. frame index and t
    for fd in frames:
        i = fd["frame"]
        if i != frames.index(fd):
            pass  # index() is slow; use enumeration below
        expected_t = round(i / FPS, 10)
        if abs(fd["t"] - expected_t) > 1e-9:
            issues.append(
                f"FAIL  frame {i} t={fd['t']} expected {expected_t}"
            )
    for idx, fd in enumerate(frames):
        if fd["frame"] != idx:
            issues.append(f"FAIL  frames[{idx}].frame={fd['frame']} (expected {idx})")

    # 7. Required locked fields present
    required = {"phase", "color_hex", "brightness", "glitch_freq", "pulse_rate",
                "noise_level", "signal_integrity", "breakpoint", "is_boundary", "coords"}
    for fd in frames[:5]:  # spot-check first 5
        missing = required - set(fd.keys())
        if missing:
            issues.append(f"FAIL  frame {fd['frame']} missing fields: {missing}")

    # 8. Palette consistency
    bad_palette = [
        fd["frame"] for fd in frames
        if fd.get("color_hex") != PHASE_PALETTE.get(fd.get("phase", ""))
    ]
    if bad_palette:
        issues.append(f"FAIL  palette mismatch in {len(bad_palette)} frames: {bad_palette[:5]}")

    # 9. No interpolation: numeric fields should exactly equal source point values
    # spot-check 10 evenly spaced frames
    n_pts = len(ordered_points)
    for i in [0, 72, 144, 216, 288, 360, 432, 504, 576, 648, 719]:
        if i >= len(frames):
            continue
        fd     = frames[i]
        grid_t = i * (n_pts - 1) / (TOTAL_FRAMES - 1)
        pt_idx = int(round(grid_t))
        pt_idx = max(0, min(pt_idx, n_pts - 1))
        src    = ordered_points[pt_idx]
        for f in _NUMERIC_FIELDS:
            if abs(fd[f] - src[f]) > 1e-9:
                issues.append(
                    f"FAIL  frame {i} {f}={fd[f]} differs from source point {pt_idx} "
                    f"{f}={src[f]} (lerp occurred?)"
                )

    # 10. run_seed consistent
    seeds = {fd["run_seed"] for fd in frames}
    if len(seeds) != 1:
        issues.append(f"FAIL  run_seed inconsistent: {seeds}")

    return issues


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="build_driver.py v0.2 — sipmg visual params → driver + frame files"
    )
    ap.add_argument("--input",  required=True, help="sipmg_visual_params.json")
    ap.add_argument("--driver", required=True, help="Output: visual_driver.json")
    ap.add_argument("--frames", required=True, help="Output: driver_frames_720.json")
    ap.add_argument("--fps",    type=int, default=FPS)
    ap.add_argument("--n-frames", type=int, default=TOTAL_FRAMES)
    args = ap.parse_args(argv)

    data       = json.loads(Path(args.input).read_text(encoding="utf-8"))
    visual_pts = data["visual_points"]

    print(f"Loaded {len(visual_pts)} visual points from {args.input}")

    ordered = build_ordered_driver(visual_pts)
    frames  = build_frames(ordered, n_frames=args.n_frames, fps=args.fps)

    # Write visual_driver.json with top-level ordered_points key
    driver_out = {"ordered_points": ordered}
    Path(args.driver).write_text(json.dumps(driver_out, indent=2), encoding="utf-8")

    # Write driver_frames_720.json as top-level array
    Path(args.frames).write_text(json.dumps(frames, indent=2), encoding="utf-8")

    issues = sanity_check(ordered, frames)

    # ── Stdout report ──────────────────────────────────────────────────────────
    phase_dist = {ph: sum(1 for p in ordered if p["phase"] == ph) for ph in "ABCD"}
    frame_dist = {ph: sum(1 for f in frames if f["phase"] == ph) for ph in "ABCD"}

    print(f"visual_driver.json     → {len(ordered)} ordered_points  {phase_dist}")
    print(f"driver_frames_720.json → {len(frames)} frames @ {args.fps}fps  {frame_dist}")
    print(f"run_seed = {_RUN_SEED}  (sha256('{RUN_ID}') % 10^9)")
    print(f"Phase C first frame: "
          f"{next((f['frame'] for f in frames if f['phase']=='C'), 'none')}")
    print()

    # Spot-check frames 0, 360, 719
    for idx in [0, 360, 719]:
        fd = frames[idx]
        print(f"frame {idx:3d}  t={fd['t']:.4f}s  "
              f"phase={fd['phase']}  color_hex={fd['color_hex']}  "
              f"vis={fd['coords']['visibility_window']}  "
              f"hdr={fd['coords']['heat_decay_rate']}  "
              f"is_boundary={fd['is_boundary']}")

    if issues:
        print(f"\nSanity check: {len(issues)} issue(s)")
        for iss in issues:
            print(f"  {iss}")
        return 1

    print(f"\nSanity check: OK  ({args.driver})  ({args.frames})")
    return 0


if __name__ == "__main__":
    from typing import Optional
    raise SystemExit(main())
