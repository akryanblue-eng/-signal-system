import { describe, it, expect } from 'vitest';
import { ChaosEngine, chaosForce } from '../ChaosEngine';
import type { ChaosEvent, ActiveChaosEvent } from '../ChaosEngine';

const mkEvent = (type: ChaosEvent['type'], overrides: Partial<ChaosEvent> = {}): ChaosEvent => ({
  id:            'test',
  type,
  intensity:     0.8,
  durationMs:    500,
  radius:        1.0,
  center:        [0, 0],
  recoveryCurve: 0.98,
  ...overrides,
});

const mkActive = (event: ChaosEvent): ActiveChaosEvent => ({
  event,
  elapsedMs: 100,
  intensity: event.intensity,
});

describe('chaosForce', () => {
  it('tension produces a tangential (perpendicular) force', () => {
    const active = mkActive(mkEvent('tension'));
    const [fx, fy] = chaosForce([1, 0], active);
    // At position (1,0) relative to center (0,0), radial = [1,0], tangential = [0,1]
    expect(Math.abs(fx)).toBeLessThan(0.01); // near zero radial component
    expect(Math.abs(fy)).toBeGreaterThan(0); // tangential component present
  });

  it('fracture produces an outward (radial) force', () => {
    const active = mkActive(mkEvent('fracture'));
    const pos: [number, number] = [1, 0];
    const [fx] = chaosForce(pos, active);
    expect(fx).toBeGreaterThan(0); // pointing away from center
  });

  it('release produces an inward (centripetal) force', () => {
    const active = mkActive(mkEvent('release'));
    const pos: [number, number] = [1, 0];
    const [fx] = chaosForce(pos, active);
    expect(fx).toBeLessThan(0); // pointing toward center
  });

  it('force magnitude decays with distance (exponential falloff)', () => {
    const active = mkActive(mkEvent('fracture'));
    const [fx1] = chaosForce([0.5, 0], active);
    const [fx2] = chaosForce([2.0, 0], active);
    expect(Math.abs(fx1)).toBeGreaterThan(Math.abs(fx2));
  });

  it('zero intensity → zero force', () => {
    const active: ActiveChaosEvent = { ...mkActive(mkEvent('tension')), intensity: 0 };
    const [fx, fy] = chaosForce([1, 0], active);
    expect(fx).toBe(0);
    expect(fy).toBe(0);
  });
});

describe('ChaosEngine', () => {
  it('starts with no active events', () => {
    const engine = new ChaosEngine();
    expect(engine.isActive()).toBe(false);
    expect(engine.activeCount()).toBe(0);
  });

  it('fire() activates an event', () => {
    const engine = new ChaosEngine();
    engine.fire(mkEvent('tension', { id: 'e1' }));
    expect(engine.isActive()).toBe(true);
    expect(engine.activeCount()).toBe(1);
  });

  it('tick() expires events that exceed durationMs', () => {
    const engine = new ChaosEngine();
    engine.fire(mkEvent('tension', { id: 'e1', durationMs: 100 }));
    const expired = engine.tick(150);
    expect(expired).toContain('e1');
    expect(engine.isActive()).toBe(false);
  });

  it('sample() returns [0,0] when no events are active', () => {
    const engine = new ChaosEngine();
    const [fx, fy] = engine.sample([1, 0]);
    expect(fx).toBe(0);
    expect(fy).toBe(0);
  });

  it('sample() accumulates forces from multiple events', () => {
    const engine = new ChaosEngine();
    engine.fire(mkEvent('fracture', { id: 'a', center: [0, 0] }));
    engine.fire(mkEvent('fracture', { id: 'b', center: [0, 0] }));
    const [fx1] = engine.sample([1, 0]);
    engine.fire(mkEvent('fracture', { id: 'c', center: [0, 0] }));
    const [fx2] = engine.sample([1, 0]);
    expect(Math.abs(fx2)).toBeGreaterThan(Math.abs(fx1));
  });
});
