import type { CanvasPoint, LatentState } from '../types/latent';

/** A snapshot of the artist's position on the manifold at a point in time. */
export interface ManifoldSnapshot {
  timestamp: number;
  latent: LatentState;
  projected: CanvasPoint;
}
