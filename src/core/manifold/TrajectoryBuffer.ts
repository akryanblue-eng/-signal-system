import type { ManifoldState } from './ManifoldRuntime';
import type { Vec2 } from '../../math/vector';

export interface TrailPoint {
  position: Vec2;      // [x, y] in manifold canvas coords
  drift:    number;    // |drift| — used for pressure coloring
  energy:   number;
  frame:    number;
}

/**
 * Circular buffer of the last N manifold positions.
 *
 * Used to render trajectory trails in the visualization layer.
 * Points are automatically aged out when the buffer is full.
 */
export class TrajectoryBuffer {
  private buffer: TrailPoint[] = [];
  private frameCount = 0;

  constructor(private readonly maxSize = 300) {}

  /**
   * Push the current state as a trail point.
   * @param x  manifold x coordinate (canvas space)
   * @param y  manifold y coordinate (canvas space)
   */
  push(x: number, y: number, state: ManifoldState): void {
    this.buffer.push({
      position: [x, y],
      drift:    Math.abs(state.drift),
      energy:   state.energy,
      frame:    this.frameCount++,
    });
    if (this.buffer.length > this.maxSize) this.buffer.shift();
  }

  /** All retained trail points, oldest first. */
  points(): readonly TrailPoint[] {
    return this.buffer;
  }

  /** How full the buffer is [0, 1]. */
  fillRatio(): number {
    return this.buffer.length / this.maxSize;
  }

  clear(): void {
    this.buffer = [];
    this.frameCount = 0;
  }
}
