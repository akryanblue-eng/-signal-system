import type { CanvasPoint } from '../types/latent';
import type { Attractor } from '../types/attractor';

export interface SteeringVector {
  forceX: number;
  forceY: number;
  magnitude: number;
}

/**
 * Computes the steering force at a canvas point due to attractor influence.
 *
 * Each attractor exerts an inverse-square pull toward its center.
 * Burner attractors additionally repel once inside their radius.
 */
export class SteeringField {
  /**
   * Sample the total steering force at (x, y) from all active attractors.
   */
  sample(point: CanvasPoint, attractors: Attractor[]): SteeringVector {
    let fx = 0;
    let fy = 0;

    for (const a of attractors) {
      const dx = a.center.x - point.x;
      const dy = a.center.y - point.y;
      const distSq = dx * dx + dy * dy + 1e-6; // avoid division by zero

      const influence = (a.strength * a.influenceRadius ** 2) / distSq;
      const sign = a.type === 'burner' ? -1 : 1;

      fx += sign * dx * influence;
      fy += sign * dy * influence;
    }

    const magnitude = Math.sqrt(fx * fx + fy * fy);
    return { forceX: fx, forceY: fy, magnitude };
  }

  /** Normalize a steering vector to unit length. */
  normalize(v: SteeringVector): SteeringVector {
    if (v.magnitude === 0) return v;
    return {
      forceX: v.forceX / v.magnitude,
      forceY: v.forceY / v.magnitude,
      magnitude: v.magnitude,
    };
  }
}
