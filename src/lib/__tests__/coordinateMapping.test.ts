import { describe, it, expect } from 'vitest';
import { projectToManifold, toCanvasCoords, fromCanvasCoords, projectForce } from '../coordinateMapping';
import type { LatentVector, SteeringForce } from '../../types/latent';

const fullyControlled: LatentVector = {
  drift_mean: 0, energy: 1, stability: 1, adaptation: 1, cumulative_drift: 0,
};

const collapsed: LatentVector = {
  drift_mean: 1, energy: 0, stability: 0, adaptation: 0, cumulative_drift: 2,
};

describe('projectToManifold — region classification', () => {
  it('fully controlled state → (1, 1) in FLOW_STATE', () => {
    const p = projectToManifold(fullyControlled);
    expect(p.x).toBeCloseTo(1.0);
    expect(p.y).toBeCloseTo(1.0);
    expect(p.region).toBe('FLOW_STATE');
  });

  it('collapsed state → (−1, −1) in COLLAPSE_BASIN', () => {
    const p = projectToManifold(collapsed);
    expect(p.x).toBeCloseTo(-1.0);
    expect(p.y).toBeCloseTo(-1.0);
    expect(p.region).toBe('COLLAPSE_BASIN');
  });

  it('energetic but unstable → CREATIVE_CHAOS (x < 0, y > 0)', () => {
    const state: LatentVector = {
      drift_mean: 1, energy: 1, stability: 0, adaptation: 1, cumulative_drift: 0.3,
    };
    const p = projectToManifold(state);
    expect(p.x).toBeLessThan(0);
    expect(p.y).toBeGreaterThan(0);
    expect(p.region).toBe('CREATIVE_CHAOS');
  });

  it('stable but low-energy → RECOVERY_POCKET (x > 0, y < 0)', () => {
    const state: LatentVector = {
      drift_mean: 0, energy: 0, stability: 1, adaptation: 0, cumulative_drift: 0.1,
    };
    const p = projectToManifold(state);
    expect(p.x).toBeGreaterThan(0);
    expect(p.y).toBeLessThan(0);
    expect(p.region).toBe('RECOVERY_POCKET');
  });
});

describe('toCanvasCoords / fromCanvasCoords round-trip', () => {
  it('round-trips exactly through canvas conversion', () => {
    const state: LatentVector = {
      drift_mean: 0.3, energy: 0.7, stability: 0.8, adaptation: 0.5, cumulative_drift: 0.2,
    };
    const point = projectToManifold(state);
    const { cx, cy } = toCanvasCoords(point, 800, 600);
    const back = fromCanvasCoords(cx, cy, 800, 600);
    expect(back.x).toBeCloseTo(point.x, 10);
    expect(back.y).toBeCloseTo(point.y, 10);
  });

  it('FLOW_STATE point lands in upper-right canvas quadrant', () => {
    const { cx, cy } = toCanvasCoords(projectToManifold(fullyControlled), 800, 600);
    expect(cx).toBeGreaterThan(400); // right half
    expect(cy).toBeLessThan(300);    // top half (canvas Y inverted)
  });

  it('COLLAPSE_BASIN point lands in lower-left canvas quadrant', () => {
    const { cx, cy } = toCanvasCoords(projectToManifold(collapsed), 800, 600);
    expect(cx).toBeLessThan(400);    // left half
    expect(cy).toBeGreaterThan(300); // bottom half
  });
});

describe('projectForce — linear projection of velocity', () => {
  it('applies correct weights to stability and energy components', () => {
    const f: SteeringForce = {
      d_drift_mean: 0, d_energy: 1, d_stability: 1, d_adaptation: 0, d_cumulative_drift: 0,
    };
    const { forceX, forceY } = projectForce(f);
    expect(forceX).toBeCloseTo(0.6); // 0.6·1 + (−0.4)·0
    expect(forceY).toBeCloseTo(0.7); // 0.7·1 +   0.3·0
  });

  it('handles opposing component directions correctly', () => {
    const f: SteeringForce = {
      d_drift_mean: 1, d_energy: 0, d_stability: 0, d_adaptation: 1, d_cumulative_drift: 0,
    };
    const { forceX, forceY } = projectForce(f);
    expect(forceX).toBeCloseTo(-0.4); // 0.6·0 + (−0.4)·1
    expect(forceY).toBeCloseTo(0.3);  // 0.7·0 +   0.3·1
  });

  it('cumulative_drift component has no effect on 2D force', () => {
    const fBase: SteeringForce = {
      d_drift_mean: 0.5, d_energy: 0.5, d_stability: 0.5, d_adaptation: 0.5, d_cumulative_drift: 0,
    };
    const fWithDrift: SteeringForce = { ...fBase, d_cumulative_drift: 999 };
    expect(projectForce(fBase)).toEqual(projectForce(fWithDrift));
  });
});
