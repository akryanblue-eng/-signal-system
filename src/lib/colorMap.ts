import { PRESSURE_CEILING } from '../constants/manifold';

type Hsl = readonly [number, number, number];

/**
 * Maps cumulative_drift pressure to an HSL color string.
 *
 * Color stops:
 *   t = 0.00 → hsl(220, 80%, 55%)  — blue   (low pressure)
 *   t = 0.33 → hsl(140, 70%, 45%)  — green  (moderate)
 *   t = 0.67 → hsl( 50, 90%, 50%)  — yellow (elevated)
 *   t = 1.00 → hsl(  0, 80%, 50%)  — red    (collapse risk)
 *
 * @param cumulative_drift  raw pressure value ∈ [0, ∞)
 * @param ceiling           value that saturates the scale to full red (default: PRESSURE_CEILING)
 */
export function pressureToColor(cumulative_drift: number, ceiling = PRESSURE_CEILING): string {
  const t = Math.min(Math.max(cumulative_drift / ceiling, 0), 1);

  if (t <= 0.33) {
    return lerpHsl([220, 80, 55], [140, 70, 45], t / 0.33);
  }
  if (t <= 0.67) {
    return lerpHsl([140, 70, 45], [50, 90, 50], (t - 0.33) / 0.34);
  }
  return lerpHsl([50, 90, 50], [0, 80, 50], Math.min((t - 0.67) / 0.33, 1));
}

function lerpHsl(from: Hsl, to: Hsl, t: number): string {
  const h = Math.round(from[0] + (to[0] - from[0]) * t);
  const s = Math.round(from[1] + (to[1] - from[1]) * t);
  const l = Math.round(from[2] + (to[2] - from[2]) * t);
  return `hsl(${h}, ${s}%, ${l}%)`;
}
