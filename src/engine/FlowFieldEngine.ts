import type { LatentState } from '../core/types/latent';

export interface Vector2 {
  x: number;
  y: number;
}

export interface FlowCell {
  position: Vector2;
  vector: Vector2;
  magnitude: number;
}

export interface AttractorNode {
  x: number;
  y: number;
  weight: number;
}

/**
 * Computes attractor-driven force vectors over the latent canvas.
 *
 * Each attractor exerts an inverse-square pull. The damping function
 * scales the total force — at λ=0 the field goes intentionally quiet.
 */
export class FlowFieldEngine {
  constructor(
    private readonly getAttractors: () => AttractorNode[],
    private readonly dampingFn: (state: LatentState) => number,
  ) {}

  /**
   * Sample the steering force at a canvas point.
   * @param state  a LatentState (or partial with x/y canvas coords)
   */
  public sampleField(state: Pick<LatentState, 'drift_mean' | 'energy' | 'stability' | 'adaptation' | 'cumulative_drift'> & { x?: number; y?: number }): Vector2 {
    const attractors = this.getAttractors();
    const px = (state as { x?: number }).x ?? 0;
    const py = (state as { y?: number }).y ?? 0;

    let fx = 0;
    let fy = 0;

    for (const a of attractors) {
      const dx = a.x - px;
      const dy = a.y - py;
      const distSq = dx * dx + dy * dy + 1e-6;
      const influence = a.weight / distSq;
      fx += dx * influence;
      fy += dy * influence;
    }

    const damping = this.dampingFn(state as LatentState);
    return { x: fx * damping, y: fy * damping };
  }

  /**
   * Generate a grid of FlowCells for the visualization layer.
   */
  public generateGrid(
    bounds: { minX: number; maxX: number; minY: number; maxY: number },
    step: number,
  ): FlowCell[] {
    const grid: FlowCell[] = [];

    for (let x = bounds.minX; x <= bounds.maxX; x += step) {
      for (let y = bounds.minY; y <= bounds.maxY; y += step) {
        const vector = this.sampleField({ x, y } as Parameters<typeof this.sampleField>[0]);
        const magnitude = Math.sqrt(vector.x ** 2 + vector.y ** 2);
        grid.push({ position: { x, y }, vector, magnitude });
      }
    }

    return grid;
  }
}
