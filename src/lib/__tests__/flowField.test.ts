import { describe, it, expect } from 'vitest';
import { FlowFieldEngine } from '../flowField';

describe('FlowFieldEngine', () => {
  it('produces resolution² cells', () => {
    const engine = new FlowFieldEngine(10);
    const cells = engine.sample(() => ({ forceX: 1, forceY: 0 }));
    expect(cells).toHaveLength(100);
  });

  it('cells span [−1, 1] in both axes', () => {
    const engine = new FlowFieldEngine(5);
    const cells = engine.sample(() => ({ forceX: 0, forceY: 0 }));
    const xs = cells.map(c => c.x);
    const ys = cells.map(c => c.y);
    expect(Math.min(...xs)).toBeCloseTo(-1);
    expect(Math.max(...xs)).toBeCloseTo(1);
    expect(Math.min(...ys)).toBeCloseTo(-1);
    expect(Math.max(...ys)).toBeCloseTo(1);
  });

  it('magnitude equals ||force||', () => {
    const engine = new FlowFieldEngine(3);
    const cells = engine.sample((x, y) => ({ forceX: x * 3, forceY: y * 4 }));
    for (const cell of cells) {
      const expected = Math.sqrt((cell.x * 3) ** 2 + (cell.y * 4) ** 2);
      expect(cell.magnitude).toBeCloseTo(expected);
    }
  });

  it('normalizeForces produces unit vectors for non-zero cells', () => {
    const engine = new FlowFieldEngine(4);
    const cells = engine.sample((x, y) => ({ forceX: x * 2, forceY: y * 3 }));
    const normalized = FlowFieldEngine.normalizeForces(cells.filter(c => c.magnitude > 0));
    for (const cell of normalized) {
      const len = Math.sqrt(cell.forceX ** 2 + cell.forceY ** 2);
      expect(len).toBeCloseTo(1);
    }
  });

  it('damping is clamped to [0, 1] even when function returns out-of-range values', () => {
    const engine = new FlowFieldEngine(3);
    const cells = engine.sample(
      () => ({ forceX: 1, forceY: 1 }),
      () => 5.0,
    );
    for (const cell of cells) {
      expect(cell.damping).toBeLessThanOrEqual(1);
      expect(cell.damping).toBeGreaterThanOrEqual(0);
    }
  });

  it('single-resolution engine returns one cell at origin', () => {
    const engine = new FlowFieldEngine(1);
    const cells = engine.sample(() => ({ forceX: 1, forceY: 1 }));
    expect(cells).toHaveLength(1);
    expect(cells[0]?.x).toBe(0);
    expect(cells[0]?.y).toBe(0);
  });
});
