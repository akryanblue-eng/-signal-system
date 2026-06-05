import { describe, it, expect } from 'vitest';
import {
  classifyStateSafety,
  gateActions,
  clampStyle,
  DEFAULT_STYLE_BOUNDS,
} from '../Constraints';
import { DEFAULT_PERFORMANCE_STATE } from '../../PerformanceState';
import type { PerformanceState } from '../../PerformanceState';
import { STYLES } from '../Style';
import type { PerformanceAction } from '../PerformanceAction';

const safe: PerformanceState  = { ...DEFAULT_PERFORMANCE_STATE, chaos: 0.3, stability: 0.7, drift: 0.1 };
const caution: PerformanceState = { ...DEFAULT_PERFORMANCE_STATE, chaos: 0.75, stability: 0.28, drift: 0.0 };
const critical: PerformanceState = { ...DEFAULT_PERFORMANCE_STATE, chaos: 0.95, stability: 0.1, drift: 0.0 };

const destabilizing: PerformanceAction[] = [
  { type: 'CHAOS_SPIKE',     amount: 0.4 },
  { type: 'DRIFT_INJECTION', amount: 0.2 },
  { type: 'TENSION_BUILD',   amount: 0.3 },
  { type: 'GROOVE_LOCK' },
];

describe('classifyStateSafety', () => {
  it('returns SAFE for healthy state', () => {
    expect(classifyStateSafety(safe)).toBe('SAFE');
  });
  it('returns CAUTION for elevated chaos', () => {
    expect(classifyStateSafety(caution)).toBe('CAUTION');
  });
  it('returns CRITICAL for extreme chaos', () => {
    expect(classifyStateSafety(critical)).toBe('CRITICAL');
  });
  it('returns CRITICAL when drift is very high', () => {
    expect(classifyStateSafety({ ...safe, drift: 0.9 })).toBe('CRITICAL');
  });
});

describe('gateActions', () => {
  it('SAFE state passes all actions unchanged', () => {
    const gated = gateActions(destabilizing, safe);
    expect(gated).toHaveLength(destabilizing.length);
    const spike = gated.find(a => a.type === 'CHAOS_SPIKE') as Extract<PerformanceAction, { type: 'CHAOS_SPIKE' }>;
    expect(spike.amount).toBeCloseTo(0.4);
  });

  it('CAUTION state halves destabilizing action amounts', () => {
    const gated = gateActions(destabilizing, caution);
    const spike = gated.find(a => a.type === 'CHAOS_SPIKE') as Extract<PerformanceAction, { type: 'CHAOS_SPIKE' }>;
    expect(spike.amount).toBeCloseTo(0.2);
  });

  it('CAUTION state leaves non-destabilizing actions unchanged', () => {
    const gated = gateActions(destabilizing, caution);
    expect(gated.find(a => a.type === 'GROOVE_LOCK')).toBeDefined();
  });

  it('CRITICAL state drops all destabilizing actions', () => {
    const gated = gateActions(destabilizing, critical);
    expect(gated.find(a => a.type === 'CHAOS_SPIKE')).toBeUndefined();
    expect(gated.find(a => a.type === 'DRIFT_INJECTION')).toBeUndefined();
    expect(gated.find(a => a.type === 'TENSION_BUILD')).toBeUndefined();
  });

  it('CRITICAL state injects STABILITY_RESTORE when not already present', () => {
    const gated = gateActions(destabilizing, critical);
    expect(gated.find(a => a.type === 'STABILITY_RESTORE')).toBeDefined();
    expect(gated.find(a => a.type === 'TENSION_RELEASE')).toBeDefined();
  });

  it('CRITICAL state does not duplicate recovery if already present', () => {
    const withRestore: PerformanceAction[] = [{ type: 'STABILITY_RESTORE', amount: 0.2 }];
    const gated = gateActions(withRestore, critical);
    expect(gated.filter(a => a.type === 'STABILITY_RESTORE')).toHaveLength(1);
  });
});

describe('clampStyle', () => {
  it('clamps aggression to bounds', () => {
    const extreme = { ...STYLES.aggressive, aggression: 3.0 };
    const clamped = clampStyle(extreme, DEFAULT_STYLE_BOUNDS);
    expect(clamped.aggression).toBeLessThanOrEqual(DEFAULT_STYLE_BOUNDS.aggression.max);
  });

  it('clamps aggression minimum', () => {
    const extreme = { ...STYLES.minimal, aggression: -0.5 };
    const clamped = clampStyle(extreme, DEFAULT_STYLE_BOUNDS);
    expect(clamped.aggression).toBeGreaterThanOrEqual(DEFAULT_STYLE_BOUNDS.aggression.min);
  });

  it('passes through values already within bounds', () => {
    const clamped = clampStyle(STYLES.cinematic, DEFAULT_STYLE_BOUNDS);
    expect(clamped.aggression).toBeCloseTo(STYLES.cinematic.aggression);
    expect(clamped.precision).toBeCloseTo(STYLES.cinematic.precision);
  });
});
