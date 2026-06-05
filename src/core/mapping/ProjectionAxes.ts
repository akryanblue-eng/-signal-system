/**
 * Locked axis weights for the latent → canvas projection.
 *
 *   X (behavioral control): 0.6 · stability − 0.4 · drift_mean
 *   Y (vitality):            0.7 · energy    + 0.3 · adaptation
 *
 * These weights are the geometry contract of the system.
 * Do not change without versioning the manifold.
 */
export const PROJECTION_AXES = {
  X: { stability: 0.6, drift_mean: -0.4 },
  Y: { energy: 0.7, adaptation: 0.3 },
} as const;

/**
 * Theoretical bounds of the raw projection when inputs ∈ [0, 1].
 * Used by renderers that need to map raw canvas coords to pixel space.
 *
 *   X_raw ∈ [−0.4, 0.6]   center = 0.1   halfRange = 0.5
 *   Y_raw ∈ [ 0.0, 1.0]   center = 0.5   halfRange = 0.5
 */
export const RAW_PROJECTION_BOUNDS = {
  X: { min: -0.4, max: 0.6, center: 0.1, halfRange: 0.5 },
  Y: { min:  0.0, max: 1.0, center: 0.5, halfRange: 0.5 },
} as const;

/**
 * Default normalization bounds for each LatentState dimension.
 * These can be updated at runtime as the system observes actual data ranges.
 */
export const DEFAULT_BOUNDS = {
  drift_mean:       1.0,
  energy:           1.0,
  stability:        1.0,
  adaptation:       1.0,
  cumulative_drift: 1.0,
} as const;
