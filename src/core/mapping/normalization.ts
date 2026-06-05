import type { CanvasPixel, CanvasPoint } from '../types/latent';
import { RAW_PROJECTION_BOUNDS } from './ProjectionAxes';

/**
 * Clamp a value to [−1, 1] after dividing by its per-dimension bound.
 * Used inside CoordinateMapper to normalize raw dimension values.
 */
export function normalizeDimension(value: number, bound: number): number {
  return Math.max(-1, Math.min(1, value / bound));
}

/**
 * Convert a CanvasPoint (raw projected coordinates) to canvas pixel coordinates.
 *
 * X raw ∈ [−0.4, 0.6], Y raw ∈ [0, 1.0].
 * Canvas Y is inverted: high vitality (large Y) → small cy (near top).
 *
 * @param point   projected CanvasPoint from CoordinateMapper
 * @param width   canvas width in pixels
 * @param height  canvas height in pixels
 * @param margin  fractional edge padding on each side (default 10%)
 */
export function toCanvasPixel(
  point: CanvasPoint,
  width: number,
  height: number,
  margin = 0.1,
): CanvasPixel {
  const scale = 1 - 2 * margin;
  const { X, Y } = RAW_PROJECTION_BOUNDS;

  const xNorm = (point.x - X.min) / (X.max - X.min); // [0, 1]
  const yNorm = (point.y - Y.min) / (Y.max - Y.min); // [0, 1]

  return {
    cx: (margin + xNorm * scale) * width,
    cy: (margin + (1 - yNorm) * scale) * height, // flip Y
  };
}

/**
 * Inverse of toCanvasPixel — recover raw projected coordinates from canvas pixels.
 * Used for grid sampling in the flow field engine.
 */
export function fromCanvasPixel(
  cx: number,
  cy: number,
  width: number,
  height: number,
  margin = 0.1,
): CanvasPoint {
  const scale = 1 - 2 * margin;
  const { X, Y } = RAW_PROJECTION_BOUNDS;

  const xNorm = (cx / width - margin) / scale;
  const yNorm = 1 - (cy / height - margin) / scale;

  return {
    x: X.min + xNorm * (X.max - X.min),
    y: Y.min + yNorm * (Y.max - Y.min),
    color: 0,
    intensity: 1,
  };
}

/**
 * Map a normalized pressure value [0, 1] to an HSL color string.
 *
 *   0.00 → hsl(220, 80%, 55%)  — blue   (low)
 *   0.33 → hsl(140, 70%, 45%)  — green  (moderate)
 *   0.67 → hsl( 50, 90%, 50%)  — yellow (elevated)
 *   1.00 → hsl(  0, 80%, 50%)  — red    (collapse risk)
 */
export function pressureToHsl(pressure: number): string {
  const t = Math.min(Math.max(pressure, 0), 1);

  if (t <= 0.33) {
    return lerpHsl([220, 80, 55], [140, 70, 45], t / 0.33);
  }
  if (t <= 0.67) {
    return lerpHsl([140, 70, 45], [50, 90, 50], (t - 0.33) / 0.34);
  }
  return lerpHsl([50, 90, 50], [0, 80, 50], Math.min((t - 0.67) / 0.33, 1));
}

type Hsl = readonly [number, number, number];

function lerpHsl(from: Hsl, to: Hsl, t: number): string {
  const h = Math.round(from[0] + (to[0] - from[0]) * t);
  const s = Math.round(from[1] + (to[1] - from[1]) * t);
  const l = Math.round(from[2] + (to[2] - from[2]) * t);
  return `hsl(${h}, ${s}%, ${l}%)`;
}
