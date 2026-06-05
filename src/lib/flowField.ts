import type { FlowFieldCell } from '../types/latent';

/** Maps a normalized (x, y) position to a raw force vector. */
export type ForceFunction = (x: number, y: number) => { forceX: number; forceY: number };

/**
 * Maps a normalized (x, y) position to a damping coefficient λ ∈ [0, 1].
 *   λ = 0 → JARVIS hands off (rendered as transparent / low-opacity arrows)
 *   λ = 1 → full steering active
 */
export type DampingFunction = (x: number, y: number) => number;

const FULL_DAMPING: DampingFunction = () => 1;

/**
 * Samples the latent manifold on a uniform grid and produces FlowFieldCell[].
 *
 * The engine owns nothing beyond resolution — it is a pure sampler.
 * Callers supply the force and damping functions; those can incorporate
 * attractor physics, trajectory history, or any other domain logic.
 */
export class FlowFieldEngine {
  readonly resolution: number;

  constructor(resolution = 20) {
    this.resolution = resolution;
  }

  /**
   * Sample the flow field across the full [−1, 1] × [−1, 1] manifold.
   *
   * @param forceFunction    computes (forceX, forceY) at each grid point
   * @param dampingFunction  computes λ at each grid point (default: 1 everywhere)
   * @returns                resolution² cells in row-major order (x outer, y inner)
   */
  sample(forceFunction: ForceFunction, dampingFunction: DampingFunction = FULL_DAMPING): FlowFieldCell[] {
    const cells: FlowFieldCell[] = [];
    const n = this.resolution;

    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const x = n > 1 ? -1 + (2 * i) / (n - 1) : 0;
        const y = n > 1 ? -1 + (2 * j) / (n - 1) : 0;

        const { forceX, forceY } = forceFunction(x, y);
        const magnitude = Math.sqrt(forceX ** 2 + forceY ** 2);
        const damping = Math.min(Math.max(dampingFunction(x, y), 0), 1);

        cells.push({ x, y, forceX, forceY, magnitude, damping });
      }
    }

    return cells;
  }

  /**
   * Return a copy of cells with force vectors scaled to unit length.
   * Use for rendering arrow direction independent of magnitude.
   * Zero-magnitude cells are passed through unchanged.
   */
  static normalizeForces(cells: FlowFieldCell[]): FlowFieldCell[] {
    return cells.map(cell => {
      if (cell.magnitude === 0) return cell;
      return {
        ...cell,
        forceX: cell.forceX / cell.magnitude,
        forceY: cell.forceY / cell.magnitude,
      };
    });
  }
}
