import { describe, it, expect } from 'vitest';
import {
  dominates,
  paretoFrontier,
  selectEquilibrium,
  scoreWithControl,
  selectWithControl,
  CONTROL_SCENES,
} from '../ParetoSolver';
import type { ObjectiveVector, ControlSurface } from '../ParetoSolver';

const v = (stability: number, performance: number, exploration: number, coherence: number): ObjectiveVector =>
  ({ stability, performance, exploration, coherence });

describe('dominates', () => {
  it('a strictly dominates b when a > b in all dimensions', () => {
    expect(dominates(v(0.8, 0.8, 0.8, 0.8), v(0.5, 0.5, 0.5, 0.5))).toBe(true);
  });

  it('does not dominate when a < b in any dimension', () => {
    expect(dominates(v(0.8, 0.8, 0.8, 0.3), v(0.5, 0.5, 0.5, 0.5))).toBe(false);
  });

  it('does not dominate equal vectors (requires strictly better in ≥1)', () => {
    expect(dominates(v(0.5, 0.5, 0.5, 0.5), v(0.5, 0.5, 0.5, 0.5))).toBe(false);
  });

  it('a dominates b when a >= b in all dims and > in at least one', () => {
    expect(dominates(v(0.8, 0.5, 0.5, 0.5), v(0.5, 0.5, 0.5, 0.5))).toBe(true);
  });
});

describe('paretoFrontier', () => {
  it('returns all vectors when none dominate each other', () => {
    const states = [
      v(0.9, 0.1, 0.5, 0.5), // high stability, low performance
      v(0.1, 0.9, 0.5, 0.5), // low stability, high performance
    ];
    expect(paretoFrontier(states)).toHaveLength(2);
  });

  it('removes dominated vectors', () => {
    const states = [
      v(0.9, 0.9, 0.9, 0.9), // dominates all others
      v(0.5, 0.5, 0.5, 0.5),
      v(0.3, 0.3, 0.3, 0.3),
    ];
    expect(paretoFrontier(states)).toHaveLength(1);
    expect(paretoFrontier(states)[0]).toEqual(v(0.9, 0.9, 0.9, 0.9));
  });

  it('returns empty array for empty input', () => {
    expect(paretoFrontier([])).toHaveLength(0);
  });

  it('returns a single vector unchanged', () => {
    expect(paretoFrontier([v(0.5, 0.5, 0.5, 0.5)])).toHaveLength(1);
  });
});

describe('selectEquilibrium', () => {
  it('returns null for empty frontier', () => {
    expect(selectEquilibrium([])).toBeNull();
  });

  it('returns the only vector when frontier has one element', () => {
    const only = v(0.5, 0.5, 0.5, 0.5);
    expect(selectEquilibrium([only])).toEqual(only);
  });

  it('prefers balanced vectors over performance spikes', () => {
    const balanced = v(0.7, 0.7, 0.7, 0.7);
    const spike    = v(1.0, 0.1, 0.1, 0.1);
    // neither dominates the other (spike has higher stability, balanced has higher others)
    const result = selectEquilibrium([spike, balanced]);
    expect(result).toEqual(balanced);
  });

  it('uniform vector has variance 0 — always selected as equilibrium', () => {
    const uniform = v(0.6, 0.6, 0.6, 0.6);
    const mixed   = v(0.9, 0.3, 0.7, 0.5);
    expect(selectEquilibrium([uniform, mixed])).toEqual(uniform);
  });
});

describe('scoreWithControl + selectWithControl', () => {
  it('scoreWithControl returns weighted dot product', () => {
    const state:   ObjectiveVector = v(1, 0, 0, 0);
    const control: ControlSurface  = { stability: 0.8, performance: 0.2, exploration: 0.5, coherence: 0.3 };
    expect(scoreWithControl(state, control)).toBeCloseTo(0.8);
  });

  it('selectWithControl returns null for empty frontier', () => {
    const control: ControlSurface = CONTROL_SCENES['cinematic']!;
    expect(selectWithControl([], control)).toBeNull();
  });

  it('selectWithControl picks the most control-aligned vector', () => {
    const precisionControl: ControlSurface = { stability: 1.0, performance: 0.5, exploration: 0.0, coherence: 1.0 };
    const highStability = v(0.9, 0.5, 0.1, 0.9);
    const highExplore   = v(0.1, 0.5, 0.9, 0.1);
    const result = selectWithControl([highStability, highExplore], precisionControl);
    expect(result).toEqual(highStability);
  });
});

describe('CONTROL_SCENES', () => {
  it('has cinematic, precision, chaosJam presets', () => {
    expect(CONTROL_SCENES['cinematic']).toBeDefined();
    expect(CONTROL_SCENES['precision']).toBeDefined();
    expect(CONTROL_SCENES['chaosJam']).toBeDefined();
  });

  it('chaosJam has higher exploration than precision', () => {
    expect(CONTROL_SCENES['chaosJam']!.exploration).toBeGreaterThan(
      CONTROL_SCENES['precision']!.exploration,
    );
  });

  it('precision has higher stability than chaosJam', () => {
    expect(CONTROL_SCENES['precision']!.stability).toBeGreaterThan(
      CONTROL_SCENES['chaosJam']!.stability,
    );
  });
});
