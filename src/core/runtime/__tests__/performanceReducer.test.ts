import { describe, it, expect } from 'vitest';
import { performanceReducer } from '../performanceReducer';
import { DEFAULT_PERFORMANCE_STATE } from '../../PerformanceState';
import type { PerformanceState } from '../../PerformanceState';

const base: PerformanceState = {
  ...DEFAULT_PERFORMANCE_STATE,
  energy:    0.5,
  stability: 0.7,
  chaos:     0.2,
  tension:   0.4,
  groove:    0.4,
  drift:     0.1,
};

describe('performanceReducer', () => {
  it('CHAOS_SPIKE increases chaos and decreases stability', () => {
    const next = performanceReducer(base, { type: 'CHAOS_SPIKE', amount: 0.2 });
    expect(next.chaos).toBeCloseTo(0.4);
    expect(next.stability).toBeCloseTo(0.7 - 0.2 * 0.4);
    expect(next.lastEvent).toBe('CHAOS_SPIKE');
  });

  it('TENSION_BUILD increases tension and energy proportionally', () => {
    const next = performanceReducer(base, { type: 'TENSION_BUILD', amount: 0.2 });
    expect(next.tension).toBeCloseTo(0.6);
    expect(next.energy).toBeCloseTo(0.5 + 0.2 * 0.2);
    expect(next.lastEvent).toBe('TENSION_BUILD');
  });

  it('TENSION_RELEASE multiplies tension down and raises stability', () => {
    const next = performanceReducer(base, { type: 'TENSION_RELEASE' });
    expect(next.tension).toBeCloseTo(0.4 * 0.6);
    expect(next.stability).toBeCloseTo(0.7 + 0.1);
    expect(next.lastEvent).toBe('TENSION_RELEASE');
  });

  it('GROOVE_LOCK increases groove and decays chaos', () => {
    const next = performanceReducer(base, { type: 'GROOVE_LOCK' });
    expect(next.groove).toBeCloseTo(0.4 + 0.12);
    expect(next.chaos).toBeCloseTo(0.2 * 0.85);
    expect(next.lastEvent).toBe('GROOVE_LOCK');
  });

  it('DRIFT_INJECTION increases both drift and chaos', () => {
    const next = performanceReducer(base, { type: 'DRIFT_INJECTION', amount: 0.1 });
    expect(next.drift).toBeCloseTo(0.2);
    expect(next.chaos).toBeCloseTo(0.3);
    expect(next.lastEvent).toBe('DRIFT_INJECTION');
  });

  it('ENERGY_PULSE increases energy', () => {
    const next = performanceReducer(base, { type: 'ENERGY_PULSE', amount: 0.3 });
    expect(next.energy).toBeCloseTo(0.8);
    expect(next.lastEvent).toBe('ENERGY_PULSE');
  });

  it('STABILITY_RESTORE increases stability', () => {
    const next = performanceReducer(base, { type: 'STABILITY_RESTORE', amount: 0.2 });
    expect(next.stability).toBeCloseTo(0.9);
    expect(next.lastEvent).toBe('STABILITY_RESTORE');
  });

  it('clamps all values to [0, 1] on overflow', () => {
    const high: PerformanceState = { ...base, chaos: 0.95, stability: 0.05 };
    const next = performanceReducer(high, { type: 'CHAOS_SPIKE', amount: 0.2 });
    expect(next.chaos).toBeLessThanOrEqual(1);
    expect(next.stability).toBeGreaterThanOrEqual(0);
  });

  it('does not mutate the input state', () => {
    const snapshot = { ...base };
    performanceReducer(base, { type: 'CHAOS_SPIKE', amount: 0.5 });
    expect(base.chaos).toBe(snapshot.chaos);
    expect(base.stability).toBe(snapshot.stability);
  });
});
