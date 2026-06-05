import type { CanvasPoint } from '../types/latent';
import type { Attractor } from '../types/attractor';

/**
 * Computes the damping coefficient λ ∈ [0, 1] at a given canvas point.
 *
 *   λ = 0  → JARVIS is fully hands-off (creative autonomy zone)
 *   λ = 1  → full steering pressure applied
 *
 * Damping is low near attractor influence radii and in the CREATIVE_CHAOS region,
 * where the system intentionally defers to performer judgment.
 */
export class DampingEngine {
  private readonly baseLevel: number;

  constructor(baseLevel = 0.7) {
    this.baseLevel = baseLevel;
  }

  compute(point: CanvasPoint, attractors: Attractor[]): number {
    let damping = this.baseLevel;

    for (const a of attractors) {
      const dx = point.x - a.center.x;
      const dy = point.y - a.center.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < a.influenceRadius) {
        const proximity = 1 - dist / a.influenceRadius;
        if (a.type === 'pocket' || a.type === 'reset') {
          // Near anchoring attractors: increase damping (more steering)
          damping = Math.min(1, damping + proximity * 0.3);
        } else if (a.type === 'burner') {
          // Near energy attractors: reduce damping (allow creative expression)
          damping = Math.max(0, damping - proximity * 0.4);
        }
      }
    }

    return damping;
  }
}
