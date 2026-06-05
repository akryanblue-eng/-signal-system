/**
 * Axis projection weights — locked geometry for the coordinate mapping layer.
 *
 * X (behavioral control):  0.6 * stability  - 0.4 * drift_mean
 * Y (vitality):             0.7 * energy     + 0.3 * adaptation
 */
export const AXIS_WEIGHTS = {
  X: { stability: 0.6, drift_mean: -0.4 },
  Y: { energy: 0.7, adaptation: 0.3 },
} as const;

/**
 * Theoretical bounds of the raw projection, derived from inputs ∈ [0, 1].
 *
 * X_raw ∈ [0.6·0 − 0.4·1,  0.6·1 − 0.4·0] = [−0.4, 0.6],  center = 0.1,  halfRange = 0.5
 * Y_raw ∈ [0.7·0 + 0.3·0,  0.7·1 + 0.3·1] = [ 0.0, 1.0],  center = 0.5,  halfRange = 0.5
 *
 * Normalizing by (raw − center) / halfRange maps both axes to [−1, 1].
 */
export const PROJECTION_BOUNDS = {
  X: { min: -0.4, max: 0.6, center: 0.1, halfRange: 0.5 },
  Y: { min:  0.0, max: 1.0, center: 0.5, halfRange: 0.5 },
} as const;

/** cumulative_drift value that maps to full-red (collapse risk) on the pressure color scale. */
export const PRESSURE_CEILING = 1.0;

/** Fractional margin on each canvas edge (10% → actual data occupies 80% of canvas). */
export const CANVAS_MARGIN = 0.1;
