/** 5D latent performance state vector. All inputs ∈ [0, 1] except cumulative_drift ∈ [0, ∞). */
export interface LatentState {
  drift_mean: number;       // mean behavioral drift
  energy: number;           // performance energy level
  stability: number;        // behavioral stability
  adaptation: number;       // adaptive response capacity
  cumulative_drift: number; // total accumulated pressure (unbounded)
}

/**
 * 2D projected point in control-canvas space.
 *
 *   x         — behavioral control axis  (right = controlled)
 *   y         — vitality axis            (up = energized)
 *   color     — temporal pressure        [0, 1] — 0 = low, 1 = collapse risk
 *   intensity — state coherence          [0, 1] — 0 = incoherent, 1 = clear
 */
export interface CanvasPoint {
  x: number;
  y: number;
  color: number;
  intensity: number;
}

/** Canvas pixel coordinates for final rendering. */
export interface CanvasPixel {
  cx: number; // pixels from left edge
  cy: number; // pixels from top edge
}

/**
 * Quadrant regions of the 2D control canvas.
 *
 *   CREATIVE_CHAOS  |  FLOW_STATE
 *   ----------------+------------   (y = vitality midpoint)
 *   COLLAPSE_BASIN  |  RECOVERY_POCKET
 *                   |
 *               (x = control midpoint)
 */
export type CanvasRegion =
  | 'FLOW_STATE'       // upper-right: high stability, high energy
  | 'RECOVERY_POCKET'  // lower-right: stable, low energy
  | 'CREATIVE_CHAOS'   // upper-left:  energetic but unstable
  | 'COLLAPSE_BASIN';  // lower-left:  low energy, high instability

/** A 5D steering force (rate of change of LatentState dimensions). */
export interface SteeringForce {
  d_drift_mean: number;
  d_energy: number;
  d_stability: number;
  d_adaptation: number;
  d_cumulative_drift: number;
}
