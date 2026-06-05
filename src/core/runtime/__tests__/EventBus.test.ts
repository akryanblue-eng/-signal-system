import { describe, it, expect } from 'vitest';
import { EventBus } from '../EventBus';
import type { PerformanceAction } from '../PerformanceAction';

describe('EventBus', () => {
  it('dispatch queues actions; flush drains them in order', () => {
    const bus = new EventBus<PerformanceAction>();
    bus.dispatch({ type: 'CHAOS_SPIKE',   amount: 0.1 });
    bus.dispatch({ type: 'GROOVE_LOCK' });
    bus.dispatch({ type: 'ENERGY_PULSE',  amount: 0.2 });
    const actions = bus.flush();
    expect(actions).toHaveLength(3);
    expect(actions[0]?.type).toBe('CHAOS_SPIKE');
    expect(actions[2]?.type).toBe('ENERGY_PULSE');
  });

  it('flush leaves the queue empty', () => {
    const bus = new EventBus<PerformanceAction>();
    bus.dispatch({ type: 'TENSION_RELEASE' });
    bus.flush();
    expect(bus.size).toBe(0);
    expect(bus.flush()).toHaveLength(0);
  });

  it('size reflects pending count between dispatches', () => {
    const bus = new EventBus<PerformanceAction>();
    expect(bus.size).toBe(0);
    bus.dispatch({ type: 'DRIFT_INJECTION', amount: 0.05 });
    expect(bus.size).toBe(1);
    bus.dispatch({ type: 'GROOVE_LOCK' });
    expect(bus.size).toBe(2);
    bus.flush();
    expect(bus.size).toBe(0);
  });
});
