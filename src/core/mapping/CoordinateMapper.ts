import type { CanvasPoint, CanvasRegion, LatentState, SteeringForce } from '../types/latent';
import { DEFAULT_BOUNDS, PROJECTION_AXES } from './ProjectionAxes';
import { normalizeDimension } from './normalization';

export interface NormalizationBounds {
  drift_mean: number;
  energy: number;
  stability: number;
  adaptation: number;
  cumulative_drift: number;
}

/**
 * Deterministic projection: 5D latent performance space → 2D control canvas.
 *
 * Geometry contract (locked):
 *   X = 0.6 · norm(stability)  − 0.4 · norm(drift_mean)   → behavioral control axis
 *   Y = 0.7 · norm(energy)     + 0.3 · norm(adaptation)   → vitality axis
 *
 * Normalization bounds are initialized to theoretical maxima and can be
 * updated at runtime as the system observes actual data ranges — allowing
 * the geometry to adapt without changing the projection weights.
 */
export class CoordinateMapper {
  private bounds: NormalizationBounds;

  constructor(bounds: Partial<NormalizationBounds> = {}) {
    this.bounds = { ...DEFAULT_BOUNDS, ...bounds };
  }

  /**
   * Project a LatentState to a 2D CanvasPoint.
   *
   * @returns  { x, y } raw projected coordinates, color ∈ [0, 1], intensity ∈ [0, 1]
   */
  public project(state: LatentState): CanvasPoint {
    const { drift_mean, energy, stability, adaptation, cumulative_drift } = state;

    const x =
      PROJECTION_AXES.X.stability  * normalizeDimension(stability,  this.bounds.stability)  +
      PROJECTION_AXES.X.drift_mean * normalizeDimension(drift_mean, this.bounds.drift_mean);

    const y =
      PROJECTION_AXES.Y.energy     * normalizeDimension(energy,     this.bounds.energy)     +
      PROJECTION_AXES.Y.adaptation * normalizeDimension(adaptation, this.bounds.adaptation);

    const color     = normalizeDimension(cumulative_drift, this.bounds.cumulative_drift) * 0.5 + 0.5;
    const intensity = this.computeCoherence(state);

    return { x, y, color, intensity };
  }

  /**
   * Project a 5D SteeringForce to 2D canvas force components.
   * The same linear weights apply to velocity as to position.
   */
  public projectForce(f: SteeringForce): { forceX: number; forceY: number } {
    return {
      forceX:
        PROJECTION_AXES.X.stability  * normalizeDimension(f.d_stability,  this.bounds.stability)  +
        PROJECTION_AXES.X.drift_mean * normalizeDimension(f.d_drift_mean, this.bounds.drift_mean),
      forceY:
        PROJECTION_AXES.Y.energy     * normalizeDimension(f.d_energy,     this.bounds.energy)     +
        PROJECTION_AXES.Y.adaptation * normalizeDimension(f.d_adaptation, this.bounds.adaptation),
    };
  }

  /** Classify the 2D canvas region for a projected point. */
  public classify(point: CanvasPoint): CanvasRegion {
    const xMid = (0.6 * 1 + -0.4 * 0) / 2; // midpoint of [−0.4, 0.6] = 0.1
    const yMid = (0.7 * 1 + 0.3 * 1) / 2;  // midpoint of [0.0, 1.0]  = 0.5
    if (point.x >= xMid && point.y >= yMid) return 'FLOW_STATE';
    if (point.x >= xMid)                    return 'RECOVERY_POCKET';
    if (point.y >= yMid)                    return 'CREATIVE_CHAOS';
    return 'COLLAPSE_BASIN';
  }

  /**
   * Update normalization bounds as new data is observed.
   * Call this when actual dimension ranges exceed the defaults.
   */
  public updateBounds(observed: Partial<NormalizationBounds>): void {
    this.bounds = { ...this.bounds, ...observed };
  }

  public getBounds(): Readonly<NormalizationBounds> {
    return { ...this.bounds };
  }

  /**
   * Confidence proxy for state coherence.
   * High variance across key dimensions signals incoherence.
   * Will be replaced with a learned model in a future layer.
   */
  private computeCoherence(state: LatentState): number {
    const instability = normalizeDimension(state.drift_mean,       this.bounds.drift_mean);
    const entropy     = 1 - normalizeDimension(state.stability,    this.bounds.stability);
    const pressure    = normalizeDimension(state.cumulative_drift, this.bounds.cumulative_drift);
    const variance    = Math.abs(instability) + entropy + Math.abs(pressure);
    return Math.max(0, 1 - variance * 0.33);
  }
}
