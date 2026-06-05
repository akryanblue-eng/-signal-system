import type { FlowFieldCell } from '../core/types/flow';

/** Maps a (x, y) canvas position to a raw force vector. */
export type ForceFunction = (x: number, y: number) => { forceX: number; forceY: number };

/**
 * Maps a (x, y) canvas position to a damping coefficient λ ∈ [0, 1].
 *   λ = 0 → JARVIS hands off  (render as transparent / near-invisible arrows)
 *   λ = 1 → full steering active
 */
export type DampingFunction = (x: number, y: number) => number;

const FULL_DAMPING: DampingFunction = () => 1;

/**
 * Samples the control canvas on a uniform grid and produces FlowFieldCell[].
 *
 * The engine is a pure sampler — it owns no state beyond resolution.
 * Force and damping functions are injected by the caller, allowing
 * attractor physics, trajectory history, and any other domain logic
 * to plug in without coupling to the rendering layer.
 */
export class FlowFieldEngine {
  readonly resolution: number;

  constructor(resolution = 20) {
    this.resolution = resolution;
  }

  /**
   * Sample the flow field across the [xMin, xMax] × [yMin, yMax] region.
   * Defaults to the raw projection bounds: x ∈ [−0.4, 0.6], y ∈ [0, 1].
   *
   * @returns  resolution² FlowFieldCells in row-major order (x outer, y inner)
   */
  sample(
    forceFunction: ForceFunction,
    dampingFunction: DampingFunction = FULL_DAMPING,
    xRange: [number, number] = [-0.4, 0.6],
    yRange: [number, number] = [0.0, 1.0],
  ): FlowFieldCell[] {
    const cells: FlowFieldCell[] = [];
    const n = this.resolution;
    const [x0, x1] = xRange;
    const [y0, y1] = yRange;

    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const x = n > 1 ? x0 + ((x1 - x0) * i) / (n - 1) : (x0 + x1) / 2;
        const y = n > 1 ? y0 + ((y1 - y0) * j) / (n - 1) : (y0 + y1) / 2;

        const { forceX, forceY } = forceFunction(x, y);
        const magnitude = Math.sqrt(forceX ** 2 + forceY ** 2);
        const damping = Math.min(Math.max(dampingFunction(x, y), 0), 1);

        cells.push({ x, y, forceX, forceY, magnitude, damping });
      }
    }

    return cells;
  }

  /**
   * Return a copy of cells with force vectors normalized to unit length.
   * Use for rendering arrow direction independently of magnitude.
   * Zero-magnitude cells pass through unchanged.
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
