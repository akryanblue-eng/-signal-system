import type { CanvasPoint, CanvasRegion, LatentVector, ManifoldPoint, SteeringForce } from '../types/latent';
import { AXIS_WEIGHTS, CANVAS_MARGIN, PROJECTION_BOUNDS } from '../constants/manifold';
import { pressureToColor } from './colorMap';

/**
 * Project a 5D LatentVector onto the 2D manifold canvas.
 *
 *   X = 0.6 · stability  − 0.4 · drift_mean   → normalized to [−1, 1]
 *   Y = 0.7 · energy     + 0.3 · adaptation    → normalized to [−1, 1]
 *
 * Both axes normalize perfectly because their theoretical input ranges map
 * exactly to [−0.4, 0.6] and [0, 1.0] respectively — each has halfRange = 0.5.
 */
export function projectToManifold(v: LatentVector): ManifoldPoint {
  const xRaw =
    AXIS_WEIGHTS.X.stability  * v.stability  +
    AXIS_WEIGHTS.X.drift_mean * v.drift_mean;
  const yRaw =
    AXIS_WEIGHTS.Y.energy     * v.energy     +
    AXIS_WEIGHTS.Y.adaptation * v.adaptation;

  const x = (xRaw - PROJECTION_BOUNDS.X.center) / PROJECTION_BOUNDS.X.halfRange;
  const y = (yRaw - PROJECTION_BOUNDS.Y.center) / PROJECTION_BOUNDS.Y.halfRange;

  return {
    x,
    y,
    color: pressureToColor(v.cumulative_drift),
    magnitude: 0,
    region: classifyRegion(x, y),
  };
}

/**
 * Project a 5D steering force vector to 2D canvas force components.
 *
 * Because the position projection is linear, the same weights apply to
 * the force (velocity) components: d/dt(x) = Wx · d/dt(latent).
 */
export function projectForce(f: SteeringForce): { forceX: number; forceY: number } {
  return {
    forceX:
      AXIS_WEIGHTS.X.stability  * f.d_stability  +
      AXIS_WEIGHTS.X.drift_mean * f.d_drift_mean,
    forceY:
      AXIS_WEIGHTS.Y.energy     * f.d_energy     +
      AXIS_WEIGHTS.Y.adaptation * f.d_adaptation,
  };
}

/**
 * Convert a ManifoldPoint in normalized [−1, 1] space to canvas pixel coordinates.
 *
 * Canvas Y is inverted: manifold y=1 (high vitality) → cy near 0 (top of canvas).
 */
export function toCanvasCoords(
  point: ManifoldPoint,
  width: number,
  height: number,
  margin = CANVAS_MARGIN,
): CanvasPoint {
  const scale = 1 - 2 * margin;
  return {
    cx: (margin + ((point.x + 1) / 2) * scale) * width,
    cy: (margin + ((1 - point.y) / 2) * scale) * height,
  };
}

/**
 * Inverse of toCanvasCoords — convert canvas pixel coords back to normalized manifold space.
 * Used when sampling grid cells for the flow field renderer.
 */
export function fromCanvasCoords(
  cx: number,
  cy: number,
  width: number,
  height: number,
  margin = CANVAS_MARGIN,
): { x: number; y: number } {
  const scale = 1 - 2 * margin;
  return {
    x: ((cx / width  - margin) / scale) * 2 - 1,
    y: 1 - ((cy / height - margin) / scale) * 2,
  };
}

function classifyRegion(x: number, y: number): CanvasRegion {
  if (x >= 0 && y >= 0) return 'FLOW_STATE';
  if (x >= 0)           return 'RECOVERY_POCKET';
  if (y >= 0)           return 'CREATIVE_CHAOS';
  return 'COLLAPSE_BASIN';
}
