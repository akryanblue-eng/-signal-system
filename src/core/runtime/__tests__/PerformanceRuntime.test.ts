import { describe, it, expect } from 'vitest';
import { PerformanceRuntime, ChaosSystem, GovernorSystem } from '../PerformanceRuntime';
import type { PerformanceSystem } from '../PerformanceRuntime';
import type { PerformanceState } from '../../PerformanceState';
import { DEFAULT_PERFORMANCE_STATE } from '../../PerformanceState';
import type { Dispatch } from '../PerformanceAction';

const mkState = (overrides: Partial<PerformanceState> = {}): PerformanceState => ({
  ...DEFAULT_PERFORMANCE_STATE,
  ...overrides,
});

describe('PerformanceRuntime', () => {
  it('tickStep advances frameIndex and timestamp', () => {
    const rt = new PerformanceRuntime(mkState());
    rt.tickStep(0.016);
    expect(rt.getState().frameIndex).toBe(1);
    expect(rt.getState().timestamp).toBeCloseTo(16, 0);
  });

  it('high tension causes ChaosSystem to dispatch CHAOS_SPIKE', () => {
    const rt = new PerformanceRuntime(mkState({ tension: 0.9, chaos: 0.1 }), [new ChaosSystem()]);
    rt.tickStep(0.016);
    expect(rt.getState().chaos).toBeGreaterThan(0.1);
    expect(rt.getState().lastEvent).toBe('CHAOS_SPIKE');
  });

  it('high chaos causes GovernorSystem to dispatch TENSION_RELEASE', () => {
    const rt = new PerformanceRuntime(mkState({ chaos: 0.9, tension: 0.8 }), [new GovernorSystem()]);
    rt.tickStep(0.016);
    expect(rt.getState().tension).toBeLessThan(0.8);
    expect(rt.getState().lastEvent).toBe('TENSION_RELEASE');
  });

  it('external dispatch is processed within the same tickStep', () => {
    const rt = new PerformanceRuntime(mkState({ energy: 0.3 }), []);
    rt.dispatch({ type: 'ENERGY_PULSE', amount: 0.3 });
    rt.tickStep(0.016);
    expect(rt.getState().energy).toBeCloseTo(0.6);
  });

  it('systems run with no-op array → state advances but is otherwise unchanged', () => {
    const rt = new PerformanceRuntime(mkState({ chaos: 0.5 }), []);
    const before = rt.getState().chaos;
    rt.tickStep(0.016);
    expect(rt.getState().chaos).toBe(before);
    expect(rt.getState().frameIndex).toBe(1);
  });

  it('custom system can observe and dispatch', () => {
    const witnessed: string[] = [];
    const spy: PerformanceSystem = {
      tick(state: PerformanceState, dispatch: Dispatch) {
        witnessed.push(`chaos=${state.chaos.toFixed(2)}`);
        dispatch({ type: 'GROOVE_LOCK' });
      },
    };
    const rt = new PerformanceRuntime(mkState({ chaos: 0.5, groove: 0.2 }), [spy]);
    rt.tickStep(0.016);
    expect(witnessed).toHaveLength(1);
    expect(rt.getState().groove).toBeCloseTo(0.32);
  });
});
