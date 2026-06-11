#!/usr/bin/env python3
"""
visualize/boot_sequence.py — Boot Sequence Renderer v0.1  CHI-0001

Consumes driver_frames_720.json (720 frames @ 24fps) and renders
Boot_Sequence_v0.1_CHI0001.mp4.

Every visual decision is driven by the driver file. No synthetic base,
no fallback color tables. driver_frames_720.json is the single source of truth.

Frame visual model:
  background    — BG_COLOR (#0a0a0a) always
  phase cell    — color_hex at full brightness*brightness, sized to fill frame
  glitch layer  — horizontal scanline corruption, probability = glitch_freq
  pulse ring    — centered ring that pulses at pulse_rate Hz
  noise overlay — pixel salt/pepper density = noise_level
  boundary flash — white border flash when is_boundary=True, period=1s
  HUD           — phase label, metrics bar, run_id, frame counter

Dependencies: moviepy, numpy, Pillow
Install:  pip install moviepy numpy pillow
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from moviepy.editor import ImageSequenceClip
    HAS_MOVIEPY = True
except ImportError:
    HAS_MOVIEPY = False


# ── Constants ──────────────────────────────────────────────────────────────────

WIDTH    = 1280
HEIGHT   = 720
FPS      = 24
BG_COLOR = (10, 10, 10)

PHASE_LABELS = {
    "A": "PHASE A — STABLE",
    "B": "PHASE B — INSTRUMENT DULLING",
    "C": "PHASE C — WORLD DEGRADING",
    "D": "PHASE D — JOINT COLLAPSE",
}

PHASE_HEX = {
    "A": "#00FF41",
    "B": "#FFB800",
    "C": "#FF4444",
    "D": "#FF00FF",
}


def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ── Frame renderer ─────────────────────────────────────────────────────────────

def render_frame(fd: Dict[str, Any], rng: random.Random) -> np.ndarray:
    """
    Render one frame from a driver_frames record.
    Returns an (H, W, 3) uint8 numpy array.
    """
    phase    = fd["phase"]
    color    = _hex_to_rgb(fd["color_hex"])
    bright   = fd["brightness"]
    glitch   = fd["glitch_freq"]
    pulse    = fd["pulse_rate"]
    noise    = fd["noise_level"]
    sig_int  = fd["signal_integrity"]
    boundary = fd["is_boundary"]
    t        = fd["time_sec"]
    frame_i  = fd["frame_index"]

    # ── Background ────────────────────────────────────────────────────────────
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    pixels = np.array(img, dtype=np.float32)

    # ── Phase fill: colored panel, brightness-scaled ──────────────────────────
    fill_col = tuple(int(c * bright) for c in color)
    # Central panel: 80% of frame width, full height
    px0, px1 = WIDTH // 10, WIDTH * 9 // 10
    pixels[0:HEIGHT, px0:px1] = fill_col

    # ── Glitch layer: horizontal scanline corruption ───────────────────────────
    if glitch > 0.0:
        n_lines = int(HEIGHT * glitch * 0.15)
        for _ in range(n_lines):
            if rng.random() < glitch:
                y    = rng.randint(0, HEIGHT - 1)
                xoff = rng.randint(-int(WIDTH * 0.05 * glitch), int(WIDTH * 0.05 * glitch))
                if xoff != 0:
                    row = pixels[y].copy()
                    if xoff > 0:
                        pixels[y, xoff:] = row[:WIDTH - xoff]
                        pixels[y, :xoff] = row[WIDTH - xoff:]
                    else:
                        xoff = -xoff
                        pixels[y, :WIDTH - xoff] = row[xoff:]
                        pixels[y, WIDTH - xoff:] = row[:xoff]
                # Intensity spike on the line
                spike = min(1.0, bright * (1.0 + glitch * rng.random()))
                pixels[y] = np.clip(pixels[y] * spike, 0, 255)

    # ── Pulse ring: expanding ring at pulse_rate Hz ───────────────────────────
    if pulse > 0.01:
        ring_phase = (t * pulse) % 1.0
        ring_r     = int(ring_phase * min(WIDTH, HEIGHT) * 0.6)
        ring_w     = max(2, int(min(WIDTH, HEIGHT) * 0.012))
        cx, cy     = WIDTH // 2, HEIGHT // 2
        # Draw ring as an annulus: vectorized distance check
        ys, xs = np.ogrid[:HEIGHT, :WIDTH]
        dist   = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2).astype(np.float32)
        ring_mask = (dist >= ring_r - ring_w) & (dist <= ring_r + ring_w)
        ring_alpha = np.clip(1.0 - abs(dist - ring_r) / ring_w, 0, 1) * 0.4 * bright
        for c_idx, c_val in enumerate(color):
            pixels[:, :, c_idx] = np.clip(
                pixels[:, :, c_idx] + ring_mask * ring_alpha * c_val,
                0, 255
            )

    # ── Noise overlay: salt/pepper at noise_level density ────────────────────
    if noise > 0.0:
        n_pixels = int(WIDTH * HEIGHT * noise * 0.01)
        for _ in range(n_pixels):
            nx = rng.randint(0, WIDTH - 1)
            ny = rng.randint(0, HEIGHT - 1)
            val = rng.choice([0, 255])
            pixels[ny, nx] = [val, val, val]

    # ── Boundary flash: white border when is_boundary ─────────────────────────
    if boundary:
        flash_cycle = math.sin(2 * math.pi * t * 1.0)
        if flash_cycle > 0.3:
            bw = 4
            pixels[:bw, :] = 255
            pixels[-bw:, :] = 255
            pixels[:, :bw] = 255
            pixels[:, -bw:] = 255

    img_out = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(img_out)

    # ── HUD overlay ───────────────────────────────────────────────────────────
    phase_col_hex = PHASE_HEX[phase]
    phase_col_rgb = _hex_to_rgb(phase_col_hex)

    # Phase label (top-left)
    draw.text((16, 14), PHASE_LABELS.get(phase, phase),
              fill=phase_col_rgb)

    # Metrics bar (top-right)
    metrics = (
        f"bright={fd['brightness']:.2f}  "
        f"glitch={fd['glitch_freq']:.2f}  "
        f"noise={fd['noise_level']:.2f}  "
        f"IC={fd['signal_integrity']:.2f}"
    )
    draw.text((WIDTH - 400, 14), metrics, fill=(100, 100, 100))

    # Spatial coords (middle-left)
    vis = fd.get("coord_visibility_window", 0)
    hdr = fd.get("coord_heat_decay_rate", 0)
    draw.text((16, 38),
              f"vis={vis:.1f}  hdr={hdr:.2f}  {fd['breakpoint']}",
              fill=(80, 80, 80))

    # Run ID + seed (bottom-left)
    draw.text((16, HEIGHT - 30),
              f"{fd['run_id']}  seed={fd['run_seed']}",
              fill=(50, 50, 50))

    # Frame counter (bottom-right)
    draw.text((WIDTH - 120, HEIGHT - 30),
              f"{frame_i:04d}/{FPS}fps",
              fill=(50, 50, 50))

    return np.array(img_out)


# ── Main renderer ──────────────────────────────────────────────────────────────

def render_boot_sequence(
    frames_path: str,
    output_path: str,
    seed: Optional[int] = None,
) -> None:
    if not HAS_PIL:
        print("ERROR: Pillow (PIL) not installed. Run: pip install pillow", file=sys.stderr)
        sys.exit(1)
    if not HAS_MOVIEPY:
        print("ERROR: moviepy not installed. Run: pip install moviepy", file=sys.stderr)
        sys.exit(1)

    frame_data = json.loads(Path(frames_path).read_text(encoding="utf-8"))
    print(f"Loaded {len(frame_data)} frame records from {frames_path}")

    # Use run_seed from the driver file unless overridden
    effective_seed = seed if seed is not None else frame_data[0].get("run_seed", 42)
    rng = random.Random(effective_seed)

    print(f"Rendering {len(frame_data)} frames at {FPS}fps  "
          f"(seed={effective_seed}, output={output_path})")

    rendered: List[np.ndarray] = []
    for fd in frame_data:
        frame = render_frame(fd, rng)
        rendered.append(frame)
        if fd["frame_index"] % 60 == 0:
            pct = fd["frame_index"] * 100 // len(frame_data)
            print(f"  {pct:3d}%  frame {fd['frame_index']:04d}  "
                  f"phase={fd['phase']}  t={fd['time_sec']:.1f}s")

    clip = ImageSequenceClip(rendered, fps=FPS)
    clip.write_videofile(output_path, codec="libx264", audio=False,
                         logger=None, fps=FPS)
    print(f"\nBoot_Sequence → {output_path}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="boot_sequence.py v0.1 — render Boot_Sequence_v0.1_CHI0001.mp4"
    )
    ap.add_argument("--frames",  required=True,
                    help="driver_frames_720.json (output of build_driver.py)")
    ap.add_argument("--output",  default="Boot_Sequence_v0.1_CHI0001.mp4",
                    help="Output MP4 path (default: Boot_Sequence_v0.1_CHI0001.mp4)")
    ap.add_argument("--seed",    type=int, default=None,
                    help="Override RNG seed (default: run_seed from driver file)")
    args = ap.parse_args(argv)

    render_boot_sequence(
        frames_path=args.frames,
        output_path=args.output,
        seed=args.seed,
    )
    return 0


if __name__ == "__main__":
    from typing import Optional
    raise SystemExit(main())
