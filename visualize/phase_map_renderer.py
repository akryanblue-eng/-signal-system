#!/usr/bin/env python3
"""
visualize/phase_map_renderer.py — SIPMG Phase Map Visual Driver v0.1

Reads a sipmg output JSON and renders:
  1. A static 2D phase map heatmap (PNG)
  2. Per-point visual parameter table (JSON) for downstream animation drivers
  3. An animated GIF sweeping across knob-space in phase-transition order

Phase → Visual mapping:
  A  Stable world / stable instrument   → green (#00FF41), low glitch, high brightness
  B  Stable world / dulling instrument  → amber (#FFB800), medium pulse, desaturating
  C  World degrading / instrument honest → red (#FF4444), active noise, honest signal
  D  Joint collapse                     → magenta (#FF00FF), maximum entropy, signal lost

Visual parameters per point:
  color_hex        — phase base color
  brightness       — CCF_mean (0–1), dims as causal coverage degrades
  glitch_freq      — 0.0 (A) → 0.3 (B) → 0.6 (C) → 1.0 (D) normalized
  pulse_rate       — APC_mean, reflects A-participation in resolved arcs
  noise_level      — smear_index + ghost_mass combined
  signal_integrity — IC (instrument's causal cone coverage)
  is_boundary      — True if adjacent to a different phase

Requires: matplotlib, numpy, Pillow (for GIF)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    import matplotlib.patches as mpatches
    from matplotlib.colors import ListedColormap
    import numpy as np
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ── Phase palette (terminal/Stark-Lab aesthetic) ───────────────────────────────

PHASE_COLORS: Dict[str, str] = {
    "A": "#00FF41",   # matrix green — clean signal
    "B": "#FFB800",   # amber — silent degradation
    "C": "#FF4444",   # red — world failing, instrument honest
    "D": "#FF00FF",   # magenta — joint collapse
}

PHASE_LABELS: Dict[str, str] = {
    "A": "Phase A — Stable",
    "B": "Phase B — Instrument Dulling",
    "C": "Phase C — World Degrading",
    "D": "Phase D — Joint Collapse",
}

GLITCH_FREQ: Dict[str, float] = {
    "A": 0.0,
    "B": 0.3,
    "C": 0.6,
    "D": 1.0,
}

BG_COLOR = "#0a0a0a"   # near-black background
GRID_COLOR = "#1a1a1a"


# ── Visual parameter extraction ────────────────────────────────────────────────

def extract_visual_params(point: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map SIPMG point metrics to visual animation parameters.

    All output values are in [0, 1] or simple floats ready for use as
    multipliers in shader/animation code.
    """
    phase  = point["phase"]
    wm     = point.get("world_metrics", {})
    im     = point.get("instrument_metrics", {})

    ccf    = wm.get("CCF_mean") or 0.0
    apc    = wm.get("APC_mean") or 0.0
    smear  = wm.get("smear_index") or 0.0
    ghost  = im.get("ghost_mass", 0.0)
    ic     = im.get("IC", 1.0)

    # brightness: CCF drives how "readable" the signal is
    brightness = round(max(0.1, ccf), 4)

    # glitch_freq: base per phase, modulated by world degradation
    base_glitch = GLITCH_FREQ[phase]
    world_stress = (smear + (1.0 - ccf)) / 2.0
    glitch_freq = round(min(1.0, base_glitch + world_stress * 0.3), 4)

    # pulse_rate: A-participation in resolved arcs — active evasion intensity
    pulse_rate = round(apc, 4)

    # noise_level: combined smear (arc fragmentation) + ghost mass (causal opacity)
    noise_level = round(min(1.0, (smear + ghost) / 2.0), 4)

    # signal_integrity: IC from instrument probe
    signal_integrity = round(ic, 4)

    # color with brightness-scaled alpha component
    base_color = PHASE_COLORS[phase]

    return {
        "phase":            phase,
        "coords":           point["coords"],
        "color_hex":        base_color,
        "brightness":       brightness,
        "glitch_freq":      glitch_freq,
        "pulse_rate":       pulse_rate,
        "noise_level":      noise_level,
        "signal_integrity": signal_integrity,
        "world_stability":  point["world_stability"],
        "inst_stability":   point["instrument_stability"],
        "breakpoint":       wm.get("breakpoint", "unknown"),
    }


def build_visual_params(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build full visual parameter set from a SIPMG output dict."""
    axes = data.get("sweep_axes", [])
    axis_ids = [ax["knob_id"] for ax in axes]

    soft_points = [p for p in data["points"] if p.get("range_type") == "soft"]

    # Detect boundary points (adjacent to different phase)
    boundary_keys: set = set()
    if len(axis_ids) == 2:
        ax0, ax1 = axis_ids
        coord_to_phase: Dict[Tuple[float, float], str] = {
            (p["coords"].get(ax0, 0), p["coords"].get(ax1, 0)): p["phase"]
            for p in soft_points
        }
        # Use actual step sizes from axes
        steps = {ax["knob_id"]: ax.get("soft_step", 1.0) for ax in axes}
        dx = steps.get(ax0, 1.0)
        dy = steps.get(ax1, 1.0)

        for (x, y), phase in coord_to_phase.items():
            neighbors = [(x + dx, y), (x - dx, y), (x, y + dy), (x, y - dy)]
            if any(coord_to_phase.get(n, phase) != phase for n in neighbors):
                boundary_keys.add((x, y))

    params = []
    for p in soft_points:
        vp = extract_visual_params(p)
        if len(axis_ids) == 2:
            ax0, ax1 = axis_ids
            key = (p["coords"].get(ax0, 0), p["coords"].get(ax1, 0))
            vp["is_boundary"] = key in boundary_keys
        else:
            vp["is_boundary"] = False
        params.append(vp)

    return {
        "sipmg_version":  data.get("sipmg_version"),
        "generated_at":   data.get("generated_at"),
        "vcl_hash":       data.get("vcl_hash"),
        "sweep_summary":  data.get("sweep_summary"),
        "canary_status":  data.get("canary_result", {}).get("status"),
        "axes":           axes,
        "axis_ids":       axis_ids,
        "ghost_inject_rate": data.get("ghost_inject_rate", 0.0),
        "visual_points":  params,
    }


# ── Phase map heatmap (matplotlib) ────────────────────────────────────────────

def render_phase_map(
    vp_data: Dict[str, Any],
    output_path: str,
    title: Optional[str] = None,
) -> None:
    if not HAS_MPL:
        print("matplotlib not available — skipping PNG render", file=sys.stderr)
        return

    axis_ids = vp_data["axis_ids"]
    if len(axis_ids) != 2:
        print("PNG render requires exactly 2 sweep axes", file=sys.stderr)
        return

    ax0, ax1 = axis_ids
    points = vp_data["visual_points"]

    xs = sorted(set(p["coords"].get(ax0) for p in points))
    ys = sorted(set(p["coords"].get(ax1) for p in points))

    # Phase integer grid (0=A, 1=B, 2=C, 3=D)
    phase_int = {"A": 0, "B": 1, "C": 2, "D": 3}
    grid = np.full((len(ys), len(xs)), -1, dtype=float)
    bright_grid = np.zeros((len(ys), len(xs)), dtype=float)

    x_idx = {x: i for i, x in enumerate(xs)}
    y_idx = {y: i for i, y in enumerate(ys)}

    for p in points:
        xi = x_idx.get(p["coords"].get(ax0))
        yi = y_idx.get(p["coords"].get(ax1))
        if xi is not None and yi is not None:
            grid[yi, xi] = phase_int[p["phase"]]
            bright_grid[yi, xi] = p["brightness"]

    # Custom colormap: A=green, B=amber, C=red, D=magenta
    cmap_colors = [
        mcolors.to_rgba("#00FF41"),   # A
        mcolors.to_rgba("#FFB800"),   # B
        mcolors.to_rgba("#FF4444"),   # C
        mcolors.to_rgba("#FF00FF"),   # D
    ]
    cmap = ListedColormap(cmap_colors)

    fig, axes_grid = plt.subplots(1, 2, figsize=(14, 6),
                                   gridspec_kw={"width_ratios": [3, 1]})
    fig.patch.set_facecolor(BG_COLOR)

    # ── Left: phase map ────────────────────────────────────────────────────────
    ax = axes_grid[0]
    ax.set_facecolor(BG_COLOR)

    im = ax.imshow(
        grid,
        origin="lower",
        aspect="auto",
        cmap=cmap,
        vmin=-0.5, vmax=3.5,
        extent=[xs[0], xs[-1], ys[0], ys[-1]],
        interpolation="nearest",
        alpha=0.85,
    )

    # Overlay brightness contours (CCF_mean)
    ax.contour(
        xs, ys, bright_grid,
        levels=[0.5, 0.7, 0.9],
        colors=["#ffffff"],
        alpha=0.2,
        linewidths=0.8,
    )

    # Mark boundary points
    for p in points:
        if p["is_boundary"]:
            ax.plot(
                p["coords"].get(ax0), p["coords"].get(ax1),
                "w+", markersize=6, markeredgewidth=0.8, alpha=0.5,
            )

    # World boundary annotation
    wb = vp_data["sweep_summary"].get("world_break_coords")
    if wb and ax0 in wb:
        ax.axvline(x=wb[ax0], color="#FFFFFF", linestyle="--", linewidth=0.8, alpha=0.4)
        ax.text(wb[ax0] + 0.1, ys[-1] * 0.97, "world\nboundary",
                color="#FFFFFF", fontsize=7, alpha=0.6, va="top", ha="left")

    ax.set_xlabel(ax0, color="#aaaaaa")
    ax.set_ylabel(ax1, color="#aaaaaa")
    ax.tick_params(colors="#aaaaaa")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333333")

    phase_dist = vp_data["sweep_summary"]
    title_str = title or (
        f"SIPMG Phase Map  |  "
        f"A:{phase_dist.get('phase_A',0)}  "
        f"B:{phase_dist.get('phase_B',0)}  "
        f"C:{phase_dist.get('phase_C',0)}  "
        f"D:{phase_dist.get('phase_D',0)}  "
        f"ghost_rate={vp_data['ghost_inject_rate']:.2f}"
    )
    ax.set_title(title_str, color="#cccccc", fontsize=9, pad=8)

    # ── Right: visual parameter bar charts ────────────────────────────────────
    ax_stats = axes_grid[1]
    ax_stats.set_facecolor(BG_COLOR)
    ax_stats.axis("off")

    # Per-phase mean visual parameters
    per_phase: Dict[str, List[float]] = {ph: [] for ph in "ABCD"}
    for p in points:
        per_phase[p["phase"]].append(p["glitch_freq"])

    stat_lines = ["Visual Parameters\n"]
    for ph in "ABCD":
        ppts = [p for p in points if p["phase"] == ph]
        if ppts:
            mean_bright = sum(p["brightness"] for p in ppts) / len(ppts)
            mean_glitch = sum(p["glitch_freq"] for p in ppts) / len(ppts)
            mean_noise  = sum(p["noise_level"] for p in ppts) / len(ppts)
            stat_lines.append(
                f"Phase {ph} ({len(ppts)}pt)\n"
                f"  bright={mean_bright:.2f}  "
                f"glitch={mean_glitch:.2f}  "
                f"noise={mean_noise:.2f}"
            )

    stat_lines.append(f"\nCanary: {vp_data['canary_status']}")
    stat_lines.append(f"VCL: {vp_data['vcl_hash'][7:19]}")

    ax_stats.text(
        0.05, 0.95, "\n".join(stat_lines),
        transform=ax_stats.transAxes,
        color="#aaaaaa", fontsize=7.5,
        va="top", ha="left",
        fontfamily="monospace",
    )

    # Legend
    patches = [
        mpatches.Patch(color=PHASE_COLORS[ph], label=PHASE_LABELS[ph])
        for ph in "ABCD" if any(p["phase"] == ph for p in points)
    ]
    ax.legend(handles=patches, loc="upper left", fontsize=7,
              facecolor="#111111", edgecolor="#333333",
              labelcolor="#cccccc", framealpha=0.8)

    plt.tight_layout(pad=1.5)
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=BG_COLOR)
    plt.close()
    print(f"Phase map PNG → {output_path}")


# ── Frame-by-frame animation data (PIL) ───────────────────────────────────────

def render_animation_frames(
    vp_data: Dict[str, Any],
    output_path: str,
    frame_size: Tuple[int, int] = (640, 480),
    n_frames: int = 30,
) -> None:
    """
    Render an animated GIF that sweeps through visual parameters over time.

    Animation model:
      - Each frame: entire phase grid rendered with time-varying glitch overlay
      - Glitch amplitude: sin(t * glitch_freq * 2π) per phase region
      - Boundary regions pulse at boundary_pulse_rate
      - brightness fades/pulses per CCF_mean at that point
    """
    if not HAS_PIL or not HAS_MPL:
        print("PIL or matplotlib not available — skipping GIF render", file=sys.stderr)
        return

    axis_ids = vp_data["axis_ids"]
    if len(axis_ids) != 2:
        print("GIF render requires exactly 2 sweep axes", file=sys.stderr)
        return

    ax0, ax1 = axis_ids
    points = vp_data["visual_points"]
    W, H = frame_size

    xs = sorted(set(p["coords"].get(ax0) for p in points))
    ys = sorted(set(p["coords"].get(ax1) for p in points))

    x_min, x_max = xs[0], xs[-1]
    y_min, y_max = ys[0], ys[-1]
    x_range = max(x_max - x_min, 1e-6)
    y_range = max(y_max - y_min, 1e-6)

    # Build pixel lookup table: coord → visual params
    def to_px(x, y) -> Tuple[int, int]:
        px = int((x - x_min) / x_range * (W - 40) + 20)
        py = int((1.0 - (y - y_min) / y_range) * (H - 60) + 20)
        return px, py

    cell_w = int((W - 40) / max(len(xs), 1))
    cell_h = int((H - 60) / max(len(ys), 1))

    frames: List[Image.Image] = []

    for frame_i in range(n_frames):
        t = frame_i / n_frames   # [0, 1)

        img = Image.new("RGB", (W, H), BG_COLOR)
        draw = ImageDraw.Draw(img)

        for p in points:
            x = p["coords"].get(ax0)
            y = p["coords"].get(ax1)
            px, py = to_px(x, y)

            # Time-varying brightness: base * (1 + 0.2 * sin(2π * t * pulse_rate))
            anim_bright = p["brightness"] * (
                1.0 + 0.25 * math.sin(2 * math.pi * t * max(p["pulse_rate"], 0.1))
            )
            anim_bright = max(0.05, min(1.0, anim_bright))

            # Glitch: random brightness spike when glitch_freq fires
            glitch_threshold = p["glitch_freq"] * 0.3
            glitch_fire = math.sin(2 * math.pi * t * (1.0 + p["glitch_freq"] * 4))
            if glitch_fire > (1.0 - glitch_threshold * 2):
                anim_bright = min(1.0, anim_bright * 1.8)

            # Boundary pulse: boundary cells have a white outline flash
            border_col = None
            if p["is_boundary"]:
                pulse = math.sin(2 * math.pi * t * 2.0)
                if pulse > 0.5:
                    border_col = "#FFFFFF"

            # Color with animated brightness
            base_rgb = tuple(
                int(v * anim_bright)
                for v in mcolors.to_rgb(p["color_hex"]) for _ in []
            )
            base_rgb = tuple(
                int(c * anim_bright * 255)
                for c in mcolors.to_rgb(p["color_hex"])
            )

            cx, cy = px - cell_w // 2, py - cell_h // 2
            draw.rectangle(
                [cx, cy, cx + cell_w - 1, cy + cell_h - 1],
                fill=base_rgb,
                outline=border_col,
            )

        # HUD overlay
        summary = vp_data["sweep_summary"]
        hud_lines = [
            f"SIPMG PHASE MAP  t={t:.2f}",
            f"A:{summary.get('phase_A',0)} B:{summary.get('phase_B',0)} "
            f"C:{summary.get('phase_C',0)} D:{summary.get('phase_D',0)}",
            f"ghost_rate={vp_data['ghost_inject_rate']:.2f}  "
            f"canary={vp_data['canary_status']}",
            f"x={ax0}  y={ax1}",
        ]
        for i, line in enumerate(hud_lines):
            draw.text((8, 8 + i * 14), line, fill="#00FF41")

        # Phase legend (bottom)
        legend_x = 8
        for ph in "ABCD":
            n = summary.get(f"phase_{ph}", 0)
            if n > 0:
                col = PHASE_COLORS[ph]
                draw.rectangle([legend_x, H - 22, legend_x + 12, H - 10], fill=col)
                draw.text((legend_x + 15, H - 22), f"Phase {ph} ({n})", fill=col)
                legend_x += 95

        frames.append(img)

    duration_ms = max(40, int(2000 / n_frames))
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=duration_ms,
        optimize=False,
    )
    print(f"Animation GIF → {output_path}")


# ── ANSI terminal renderer (no external dependencies) ─────────────────────────

# ANSI 256-color closest matches for phase palette
PHASE_ANSI_BG: Dict[str, str] = {
    "A": "\x1b[48;5;46m",    # bright green  (#00FF00 approx)
    "B": "\x1b[48;5;214m",   # amber/orange  (#FFB800 approx)
    "C": "\x1b[48;5;196m",   # bright red    (#FF0000 approx)
    "D": "\x1b[48;5;201m",   # magenta       (#FF00FF approx)
}
PHASE_ANSI_FG: Dict[str, str] = {
    "A": "\x1b[38;5;46m",
    "B": "\x1b[38;5;214m",
    "C": "\x1b[38;5;196m",
    "D": "\x1b[38;5;201m",
}
ANSI_RESET = "\x1b[0m"
ANSI_DIM   = "\x1b[2m"
ANSI_BOLD  = "\x1b[1m"


def render_terminal(vp_data: Dict[str, Any]) -> str:
    """
    Render a 2D phase map as ANSI-colored text to stdout.

    Each cell shows the phase letter colored by phase palette.
    Boundary cells are shown in bold. Glitch_freq and brightness are
    shown in a per-phase legend below the map.

    No external dependencies required.
    """
    axis_ids = vp_data["axis_ids"]
    if len(axis_ids) != 2:
        return "(terminal render requires exactly 2 sweep axes)"

    ax0, ax1 = axis_ids
    points = vp_data["visual_points"]

    xs = sorted(set(p["coords"].get(ax0) for p in points))
    ys = sorted(set(p["coords"].get(ax1) for p in points), reverse=True)

    # Build lookup: (x, y) → visual_params
    grid: Dict[Tuple[float, float], Dict] = {
        (p["coords"].get(ax0), p["coords"].get(ax1)): p
        for p in points
    }

    lines: List[str] = []
    summary = vp_data["sweep_summary"]
    canary  = vp_data["canary_status"]
    vcl     = vp_data["vcl_hash"][7:19]

    # Header
    lines.append(f"{ANSI_BOLD}SIPMG PHASE MAP{ANSI_RESET}  "
                 f"VCL:{ANSI_DIM}{vcl}{ANSI_RESET}  "
                 f"canary:{PHASE_ANSI_FG['A'] if canary=='ALIVE' else PHASE_ANSI_FG['C']}"
                 f"{canary}{ANSI_RESET}")
    lines.append(
        f"A:{PHASE_ANSI_FG['A']}{summary.get('phase_A',0)}{ANSI_RESET}  "
        f"B:{PHASE_ANSI_FG['B']}{summary.get('phase_B',0)}{ANSI_RESET}  "
        f"C:{PHASE_ANSI_FG['C']}{summary.get('phase_C',0)}{ANSI_RESET}  "
        f"D:{PHASE_ANSI_FG['D']}{summary.get('phase_D',0)}{ANSI_RESET}  "
        f"ghost_rate={vp_data['ghost_inject_rate']:.2f}"
    )
    lines.append("")

    # X-axis header
    x_header = f"       " + "".join(f"{x:6.1f}" for x in xs)
    lines.append(f"{ANSI_DIM}{x_header}{ANSI_RESET}")

    for y in ys:
        row_cells = []
        for x in xs:
            p = grid.get((x, y))
            if p is None:
                row_cells.append("  ?  ")
                continue
            phase = p["phase"]
            marker = f" {phase} "
            if p["is_boundary"]:
                cell = (f"{ANSI_BOLD}"
                        f"{PHASE_ANSI_BG[phase]}\x1b[30m"
                        f" {phase}* "
                        f"{ANSI_RESET}")
            else:
                cell = (f"{PHASE_ANSI_BG[phase]}\x1b[30m"
                        f" {phase}  "
                        f"{ANSI_RESET}")
            row_cells.append(cell)
        lines.append(f"{ANSI_DIM}{y:5.1f}{ANSI_RESET}  " + " ".join(row_cells))

    lines.append(f"\n{ANSI_DIM}       {''.join(f'{x:6.1f}' for x in xs)}{ANSI_RESET}")
    lines.append(f"{ANSI_DIM}       ↑ {ax0}{ANSI_RESET}  {ANSI_DIM}(↓ {ax1}){ANSI_RESET}")

    # Per-phase legend with visual parameters
    lines.append("")
    lines.append(f"{ANSI_BOLD}Visual Parameters:{ANSI_RESET}")
    for ph in "ABCD":
        ppts = [p for p in points if p["phase"] == ph]
        if not ppts:
            continue
        mean_bright = sum(p["brightness"] for p in ppts) / len(ppts)
        mean_glitch = sum(p["glitch_freq"] for p in ppts) / len(ppts)
        mean_noise  = sum(p["noise_level"] for p in ppts) / len(ppts)
        mean_ic     = sum(p["signal_integrity"] for p in ppts) / len(ppts)
        glitch_bar  = "█" * int(mean_glitch * 10) + "░" * (10 - int(mean_glitch * 10))
        lines.append(
            f"  {PHASE_ANSI_FG[ph]}{ANSI_BOLD}Phase {ph}{ANSI_RESET} ({len(ppts):3d}pt) "
            f"bright={mean_bright:.2f}  "
            f"glitch=[{PHASE_ANSI_FG[ph]}{glitch_bar}{ANSI_RESET}] {mean_glitch:.2f}  "
            f"noise={mean_noise:.2f}  "
            f"IC={mean_ic:.2f}"
        )

    # World boundary annotation
    wb = summary.get("world_break_coords")
    if wb:
        lines.append(
            f"\n  {PHASE_ANSI_FG['C']}World boundary onset:{ANSI_RESET} {wb}"
        )

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="phase_map_renderer.py v0.1 — SIPMG output → visual parameters + PNG/GIF"
    )
    ap.add_argument("--input",  required=True,
                    help="sipmg output JSON file")
    ap.add_argument("--params-out", default=None,
                    help="Write visual parameters JSON to this path")
    ap.add_argument("--png",    default=None,
                    help="Render 2D phase map PNG to this path")
    ap.add_argument("--gif",    default=None,
                    help="Render animated GIF to this path")
    ap.add_argument("--frames", type=int, default=30,
                    help="Number of animation frames (default 30)")
    ap.add_argument("--title",  default=None,
                    help="Custom plot title for PNG")
    ap.add_argument("--terminal", action="store_true",
                    help="Print ANSI-colored phase map to stdout (no deps required)")
    args = ap.parse_args(argv)

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    vp_data = build_visual_params(data)

    if args.terminal:
        print(render_terminal(vp_data))
        return 0

    if args.params_out:
        Path(args.params_out).write_text(
            json.dumps(vp_data, indent=2), encoding="utf-8"
        )
        print(f"Visual params JSON → {args.params_out}")
    else:
        # Default: dump params to stdout as JSON
        json.dump(vp_data, sys.stdout, indent=2)
        sys.stdout.write("\n")

    if args.png:
        render_phase_map(vp_data, args.png, title=args.title)

    if args.gif:
        render_animation_frames(vp_data, args.gif, n_frames=args.frames)

    return 0


if __name__ == "__main__":
    from typing import Optional
    raise SystemExit(main())
