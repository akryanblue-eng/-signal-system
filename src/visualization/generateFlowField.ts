import type { Vec2 } from '../math/vector';
import type { ManifoldState } from '../core/manifold/ManifoldRuntime';

export interface FieldCell {
  pos: Vec2;
  dir: Vec2; // unit vector (pre-normalized for rendering)
}

/**
 * Convert a ManifoldState snapshot into a 2D vector field over the canvas.
 *
 * The field is a sinusoidal surface perturbed by drift and energy —
 * drift shifts the horizontal wave phase, energy shifts the vertical.
 * Both effects are continuous and produce smooth, readable arrows.
 *
 * @param state       current manifold snapshot
 * @param resolution  grid step divisor — higher = denser grid (default 10 → 1 unit step)
 * @param extent      world-space half-extent on each axis (default 5 → [−5, 5])
 */
export function generateFlowField(
  state:      ManifoldState,
  resolution = 10,
  extent     = 5,
): FieldCell[] {
  const field: FieldCell[] = [];
  const gridStep = extent * 2 / resolution;

  const driftInfluence  = state.drift  * 0.6;
  const energyInfluence = state.energy * 0.4;

  for (let x = -extent; x <= extent + 1e-9; x += gridStep) {
    for (let y = -extent; y <= extent + 1e-9; y += gridStep) {
      const dx = Math.sin(x + driftInfluence);
      const dy = Math.cos(y + energyInfluence);
      const mag = Math.sqrt(dx * dx + dy * dy) || 1;

      field.push({
        pos: [x, y],
        dir: [dx / mag, dy / mag],
      });
    }
  }

  return field;
}
