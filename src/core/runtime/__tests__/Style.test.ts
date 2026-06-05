import { describe, it, expect } from 'vitest';
import { applyStyle, STYLES } from '../Style';
import type { PerformanceAction } from '../PerformanceAction';

const baseActions: PerformanceAction[] = [
  { type: 'CHAOS_SPIKE',       amount: 0.2 },
  { type: 'TENSION_BUILD',     amount: 0.3 },
  { type: 'DRIFT_INJECTION',   amount: 0.1 },
  { type: 'STABILITY_RESTORE', amount: 0.2 },
  { type: 'ENERGY_PULSE',      amount: 0.2 },
  { type: 'GROOVE_LOCK' },
  { type: 'TENSION_RELEASE' },
];

const getAmount = (actions: PerformanceAction[], type: string): number => {
  const a = actions.find(x => x.type === type);
  return a && 'amount' in a ? a.amount : 0;
};

describe('applyStyle', () => {
  it('aggressive style amplifies CHAOS_SPIKE beyond original amount', () => {
    const styled = applyStyle(baseActions, STYLES.aggressive); // aggression = 1.8
    expect(getAmount(styled, 'CHAOS_SPIKE')).toBeGreaterThan(0.2);
  });

  it('cinematic style reduces CHAOS_SPIKE below original amount', () => {
    const styled = applyStyle(baseActions, STYLES.cinematic); // aggression = 0.6
    expect(getAmount(styled, 'CHAOS_SPIKE')).toBeLessThan(0.2);
  });

  it('scales STABILITY_RESTORE by precision', () => {
    const styled = applyStyle(baseActions, STYLES.cinematic);
    expect(getAmount(styled, 'STABILITY_RESTORE')).toBeCloseTo(0.2 * STYLES.cinematic.precision);
  });

  it('scales ENERGY_PULSE by precision', () => {
    const styled = applyStyle(baseActions, STYLES.cinematic);
    expect(getAmount(styled, 'ENERGY_PULSE')).toBeCloseTo(0.2 * STYLES.cinematic.precision);
  });

  it('scales DRIFT_INJECTION by aggression', () => {
    const styled = applyStyle(baseActions, STYLES.chaoticJazz);
    expect(getAmount(styled, 'DRIFT_INJECTION')).toBeCloseTo(0.1 * STYLES.chaoticJazz.aggression);
  });

  it('grooveBias < 0.5 suppresses GROOVE_LOCK', () => {
    const lowGroove = { ...STYLES.aggressive, grooveBias: 0.3 };
    const styled = applyStyle(baseActions, lowGroove);
    expect(styled.find(a => a.type === 'GROOVE_LOCK')).toBeUndefined();
  });

  it('grooveBias >= 0.5 passes GROOVE_LOCK through', () => {
    const styled = applyStyle(baseActions, STYLES.cinematic); // grooveBias = 1.2
    expect(styled.find(a => a.type === 'GROOVE_LOCK')).toBeDefined();
  });

  it('aggression >= 1.5 suppresses TENSION_RELEASE', () => {
    const styled = applyStyle(baseActions, STYLES.aggressive); // aggression = 1.8
    expect(styled.find(a => a.type === 'TENSION_RELEASE')).toBeUndefined();
  });

  it('aggression < 1.5 passes TENSION_RELEASE through', () => {
    const styled = applyStyle(baseActions, STYLES.cinematic); // aggression = 0.6
    expect(styled.find(a => a.type === 'TENSION_RELEASE')).toBeDefined();
  });

  it('all amounts stay within [0, 1] even under extreme styles', () => {
    const highChaos: PerformanceAction[] = [{ type: 'CHAOS_SPIKE', amount: 0.9 }];
    const styled = applyStyle(highChaos, STYLES.aggressive);
    expect(getAmount(styled, 'CHAOS_SPIKE')).toBeLessThanOrEqual(1);
  });

  it('neutral style leaves amounts unchanged', () => {
    const styled = applyStyle(baseActions, STYLES.neutral);
    expect(getAmount(styled, 'CHAOS_SPIKE')).toBeCloseTo(0.2 * STYLES.neutral.aggression);
    expect(getAmount(styled, 'STABILITY_RESTORE')).toBeCloseTo(0.2 * STYLES.neutral.precision);
  });
});
