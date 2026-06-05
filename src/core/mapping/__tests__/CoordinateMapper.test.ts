import { describe, it, expect } from 'vitest';
import { CoordinateMapper } from '../CoordinateMapper';
import type { LatentState } from '../../types/latent';

const mapper = new CoordinateMapper();

const fullyControlled: LatentState = {
  drift_mean: 0, energy: 1, stability: 1, adaptation: 1, cumulative_drift: 0,
};

const collapsed: LatentState = {
  drift_mean: 1, energy: 0, stability: 0, adaptation: 0, cumulative_drift: 1,
};

describe('CoordinateMapper.project', () => {
  it('fully controlled state → max x, max y (FLOW_STATE)', () => {
    const p = mapper.project(fullyControlled);
    // X = 0.6·norm(1) - 0.4·norm(0) = 0.6
    expect(p.x).toBeCloseTo(0.6);
    // Y = 0.7·norm(1) + 0.3·norm(1) = 1.0
    expect(p.y).toBeCloseTo(1.0);
    expect(mapper.classify(p)).toBe('FLOW_STATE');
  });

  it('collapsed state → min x, min y (COLLAPSE_BASIN)', () => {
    const p = mapper.project(collapsed);
    // X = 0.6·norm(0) - 0.4·norm(1) = -0.4
    expect(p.x).toBeCloseTo(-0.4);
    // Y = 0.7·norm(0) + 0.3·norm(0) = 0.0
    expect(p.y).toBeCloseTo(0.0);
    expect(mapper.classify(p)).toBe('COLLAPSE_BASIN');
  });

  it('color reflects cumulative_drift pressure [0, 1]', () => {
    const low   = mapper.project({ ...fullyControlled, cumulative_drift: 0 }).color;
    const high  = mapper.project({ ...fullyControlled, cumulative_drift: 1 }).color;
    expect(low).toBeCloseTo(0.5);  // norm(0, 1) * 0.5 + 0.5 = 0.5
    expect(high).toBeCloseTo(1.0); // norm(1, 1) * 0.5 + 0.5 = 1.0
    expect(high).toBeGreaterThan(low);
  });

  it('intensity is 1 for a perfectly stable state', () => {
    const p = mapper.project({ ...fullyControlled, cumulative_drift: 0 });
    expect(p.intensity).toBeGreaterThan(0.9);
  });

  it('intensity decreases as instability grows', () => {
    const stable   = mapper.project(fullyControlled).intensity;
    const unstable = mapper.project(collapsed).intensity;
    expect(stable).toBeGreaterThan(unstable);
  });
});

describe('CoordinateMapper.projectForce', () => {
  it('projects only the stability/drift/energy/adaptation components', () => {
    const { forceX, forceY } = mapper.projectForce({
      d_drift_mean: 0, d_energy: 1, d_stability: 1, d_adaptation: 0, d_cumulative_drift: 999,
    });
    expect(forceX).toBeCloseTo(0.6);  // 0.6·1 + (−0.4)·0
    expect(forceY).toBeCloseTo(0.7);  // 0.7·1 +   0.3·0
  });
});

describe('CoordinateMapper.classify', () => {
  it('correctly identifies all four quadrants', () => {
    // upper-right
    expect(mapper.classify({ x: 0.4, y: 0.7, color: 0, intensity: 1 })).toBe('FLOW_STATE');
    // lower-right
    expect(mapper.classify({ x: 0.4, y: 0.1, color: 0, intensity: 1 })).toBe('RECOVERY_POCKET');
    // upper-left
    expect(mapper.classify({ x: -0.2, y: 0.7, color: 0, intensity: 1 })).toBe('CREATIVE_CHAOS');
    // lower-left
    expect(mapper.classify({ x: -0.2, y: 0.1, color: 0, intensity: 1 })).toBe('COLLAPSE_BASIN');
  });
});

describe('CoordinateMapper.updateBounds', () => {
  it('adapts projection when cumulative_drift ceiling is increased', () => {
    const m = new CoordinateMapper();
    const before = m.project({ ...fullyControlled, cumulative_drift: 0.5 }).color;
    m.updateBounds({ cumulative_drift: 2.0 }); // double the ceiling
    const after = m.project({ ...fullyControlled, cumulative_drift: 0.5 }).color;
    expect(after).toBeLessThan(before); // same drift reads as lower pressure
  });
});
