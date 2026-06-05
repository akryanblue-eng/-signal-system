/**
 * 5D latent state vector.
 * All input dimensions are normalized to [0, 1] except cumulative_drift which is [0, ∞).
 */
export interface LatentVector {
  drift_mean: number;       // mean behavioral drift
  energy: number;           // performance energy level
  stability: number;        // behavioral stability
  adaptation: number;       // adaptive response capacity
  cumulative_drift: number; // total accumulated pressure (unbounded)
}

/**
 * Quadrant regions of the projected 2D manifold canvas.
 *
 *   CREATIVE_CHAOS  |  FLOW_STATE
 *   ----------------+----------------  (y=0)
 *   COLLAPSE_BASIN  |  RECOVERY_POCKET
 *                   |
 *                (x=0)
 */
export type CanvasRegion =
  | 'FLOW_STATE'       // upper-right: high stability, high energy  — primary attractor
  | 'RECOVERY_POCKET'  // lower-right: stable, low energy           — rest attractor
  | 'CREATIVE_CHAOS'   // upper-left:  energetic but unstable       — often acceptable
  | 'COLLAPSE_BASIN';  // lower-left:  low energy, high instability — danger zone

/** A point projected from latent space onto the 2D manifold. */
export interface ManifoldPoint {
  x: number;          // [-1, 1] behavioral control axis (right = controlled)
  y: number;          // [-1, 1] vitality axis (up = energized)
  color: string;      // CSS hsl() string encoding temporal pressure
  magnitude: number;  // ||F_final|| — steering force magnitude at this point
  region: CanvasRegion;
}

/** A single cell in the flow field grid. */
export interface FlowFieldCell {
  x: number;        // normalized [-1, 1] position
  y: number;        // normalized [-1, 1] position
  forceX: number;   // projected force component along control axis
  forceY: number;   // projected force component along vitality axis
  magnitude: number;
  damping: number;  // λ ∈ [0, 1] — 0 = hands-off zone, 1 = full steering active
}

/** A 5D steering force vector (rate of change of the LatentVector dimensions). */
export interface SteeringForce {
  d_drift_mean: number;
  d_energy: number;
  d_stability: number;
  d_adaptation: number;
  d_cumulative_drift: number;
}

/** Canvas pixel coordinates. */
export interface CanvasPoint {
  cx: number; // pixels from left edge
  cy: number; // pixels from top edge
}
