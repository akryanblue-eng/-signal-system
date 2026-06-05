import { describe, it, expect } from 'vitest';
import { generateFlowField } from '../generateFlowField';
import type { ManifoldState } from '../../core/manifold/ManifoldRuntime';

const neutral: ManifoldState = { drift: 0, energy: 0.5, coherence: 0.8 };

describe('generateFlowField', () => {
  it('produces (resolution+1)² cells by default', () => {
    const field = generateFlowField(neutral, 10, 5);
    // x from −5 to 5 in steps of 1 → 11 values; same for y → 121 cells
    expect(field.length).toBe(121);
  });

  it('all direction vectors have approximately unit length', () => {
    const field = generateFlowField(neutral, 6, 3);
    for (const cell of field) {
      const mag = Math.sqrt(cell.dir[0] ** 2 + cell.dir[1] ** 2);
      expect(mag).toBeCloseTo(1, 5);
    }
  });

  it('spans the full extent in both axes', () => {
    const field = generateFlowField(neutral, 10, 5);
    const xs    = field.map(c => c.pos[0]);
    const ys    = field.map(c => c.pos[1]);
    expect(Math.min(...xs)).toBeCloseTo(-5);
    expect(Math.max(...xs)).toBeCloseTo(5);
    expect(Math.min(...ys)).toBeCloseTo(-5);
    expect(Math.max(...ys)).toBeCloseTo(5);
  });

  it('changes direction when drift changes (deterministic)', () => {
    const highDrift: ManifoldState = { drift: 1,  energy: 0.5, coherence: 0 };
    const lowDrift:  ManifoldState = { drift: -1, energy: 0.5, coherence: 1 };
    const a = generateFlowField(highDrift, 4, 2);
    const b = generateFlowField(lowDrift,  4, 2);
    const differs = a.some((cell, i) =>
      Math.abs(cell.dir[0] - (b[i]?.dir[0] ?? 0)) > 0.001 ||
      Math.abs(cell.dir[1] - (b[i]?.dir[1] ?? 0)) > 0.001,
    );
    expect(differs).toBe(true);
  });
});
