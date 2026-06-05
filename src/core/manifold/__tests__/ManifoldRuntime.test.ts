import { describe, it, expect } from 'vitest';
import { step, manifoldGovernor } from '../ManifoldRuntime';
import type { ManifoldState } from '../ManifoldRuntime';

const neutral: ManifoldState = { drift: 0, energy: 0.5, coherence: 0.5 };

describe('step', () => {
  it('advances state by dt', () => {
    const next = step(neutral, 0.1, [1, 0]);
    expect(next.drift).toBeCloseTo(0.1);
    expect(next.energy).toBeCloseTo(0.5);
  });

  it('clamps drift to [−1, 1]', () => {
    const s = step(neutral, 1, [999, 0]);
    expect(s.drift).toBe(1);
    const s2 = step(neutral, 1, [-999, 0]);
    expect(s2.drift).toBe(-1);
  });

  it('clamps energy to [0, 1]', () => {
    const s = step(neutral, 1, [0, 999]);
    expect(s.energy).toBe(1);
    const s2 = step(neutral, 1, [0, -999]);
    expect(s2.energy).toBe(0);
  });

  it('coherence = 1 − |drift|', () => {
    const s = step(neutral, 1, [0.5, 0]);
    expect(s.coherence).toBeCloseTo(1 - Math.abs(s.drift));
  });

  it('is frame-rate independent — same result for different dt splits', () => {
    const singleStep = step(neutral, 0.1, [0.3, -0.1]);
    const half1 = step(neutral, 0.05, [0.3, -0.1]);
    const half2 = step(half1,   0.05, [0.3, -0.1]);
    // Not exactly equal due to clamping/coherence recalc, but very close
    expect(singleStep.drift).toBeCloseTo(half2.drift, 5);
    expect(singleStep.energy).toBeCloseTo(half2.energy, 5);
  });
});

describe('manifoldGovernor', () => {
  it('returns high stability when drift is high', () => {
    const policy = manifoldGovernor({ drift: 0.8, energy: 0.5, coherence: 0.2 });
    expect(policy.stability).toBeGreaterThanOrEqual(0.7);
    expect(policy.chaos).toBeLessThan(0.3);
  });

  it('returns high chaos when energy is low', () => {
    const policy = manifoldGovernor({ drift: 0.1, energy: 0.3, coherence: 0.9 });
    expect(policy.chaos).toBeGreaterThanOrEqual(0.6);
  });

  it('policy values sum to 1', () => {
    const states: ManifoldState[] = [
      { drift: 0,   energy: 0.5, coherence: 0.5 },
      { drift: 0.8, energy: 0.8, coherence: 0.2 },
      { drift: 0.1, energy: 0.2, coherence: 0.9 },
    ];
    for (const s of states) {
      const p = manifoldGovernor(s);
      expect(p.stability + p.chaos + p.sparsity).toBeCloseTo(1.0);
    }
  });
});
