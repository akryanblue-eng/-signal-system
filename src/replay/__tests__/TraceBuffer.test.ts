import { describe, it, expect } from 'vitest';
import { TraceBuffer } from '../TraceBuffer';
import { DEFAULT_PERFORMANCE_STATE } from '../../core/PerformanceState';
import type { Frame } from '../TraceBuffer';

const s = DEFAULT_PERFORMANCE_STATE;

const mkFrame = (t: number, input = 'test'): Frame => ({
  t, input,
  state:               { ...s },
  env:                 'cinematic',
  policyEnv:           'cinematic',
  oracleEnv:           'cinematic',
  usedPolicy:          false,
  counterfactualDelta: 0,
  identityScore:       0.5,
  thought:             'oracle simulation fallback',
});

describe('TraceBuffer', () => {
  it('starts empty', () => {
    expect(new TraceBuffer().size).toBe(0);
  });

  it('push() increases size', () => {
    const tb = new TraceBuffer();
    tb.push(mkFrame(1));
    tb.push(mkFrame(2));
    expect(tb.size).toBe(2);
  });

  it('recent(n) returns last n frames, most-recent-last', () => {
    const tb = new TraceBuffer();
    for (let i = 0; i < 10; i++) tb.push(mkFrame(i));
    const r = tb.recent(3);
    expect(r).toHaveLength(3);
    expect(r[0]!.t).toBe(7);
    expect(r[2]!.t).toBe(9);
  });

  it('getAll() returns a copy of all frames', () => {
    const tb = new TraceBuffer();
    tb.push(mkFrame(1));
    tb.push(mkFrame(2));
    const all = tb.getAll();
    expect(all).toHaveLength(2);
    // mutating the copy should not affect the buffer
    all.pop();
    expect(tb.size).toBe(2);
  });

  it('evicts oldest frame once capacity is exceeded', () => {
    const tb = new TraceBuffer(3);
    tb.push(mkFrame(1));
    tb.push(mkFrame(2));
    tb.push(mkFrame(3));
    tb.push(mkFrame(4)); // evicts frame 1
    expect(tb.size).toBe(3);
    expect(tb.getAll()[0]!.t).toBe(2);
  });

  it('clear() empties the buffer', () => {
    const tb = new TraceBuffer();
    for (let i = 0; i < 5; i++) tb.push(mkFrame(i));
    tb.clear();
    expect(tb.size).toBe(0);
  });

  it('recent(n) on a buffer smaller than n returns all frames', () => {
    const tb = new TraceBuffer();
    tb.push(mkFrame(0));
    expect(tb.recent(100)).toHaveLength(1);
  });

  it('frames carry all required fields', () => {
    const tb = new TraceBuffer();
    tb.push(mkFrame(99, 'chaos'));
    const f = tb.recent(1)[0]!;
    expect(f.t).toBe(99);
    expect(f.input).toBe('chaos');
    expect(f.env).toBe('cinematic');
    expect(typeof f.identityScore).toBe('number');
    expect(typeof f.usedPolicy).toBe('boolean');
    expect(typeof f.thought).toBe('string');
  });
});

describe('PerformanceRuntime trace integration', () => {
  it('getTrace().size grows each tick', async () => {
    const { PerformanceRuntime } = await import('../../core/runtime/PerformanceRuntime');
    const rt = new PerformanceRuntime({ ...s }, { systems: [] });
    for (let i = 0; i < 5; i++) rt.tickStep(0.016);
    expect(rt.getTrace().size).toBe(5);
  });

  it('trace frames carry consistent env name', async () => {
    const { PerformanceRuntime } = await import('../../core/runtime/PerformanceRuntime');
    const rt = new PerformanceRuntime({ ...s }, { systems: [] });
    rt.tickStep(0.016);
    const frame = rt.getTrace().recent(1)[0]!;
    expect(typeof frame.env).toBe('string');
    expect(frame.env.length).toBeGreaterThan(0);
  });

  it('identityScore is in [0, 1] on every frame', async () => {
    const { PerformanceRuntime } = await import('../../core/runtime/PerformanceRuntime');
    const rt = new PerformanceRuntime({ ...s }, { systems: [] });
    for (let i = 0; i < 10; i++) rt.tickStep(0.016);
    for (const f of rt.getTrace().getAll()) {
      expect(f.identityScore).toBeGreaterThanOrEqual(0);
      expect(f.identityScore).toBeLessThanOrEqual(1);
    }
  });

  it('thought is set to expected strings', async () => {
    const { PerformanceRuntime } = await import('../../core/runtime/PerformanceRuntime');
    const rt = new PerformanceRuntime({ ...s }, { systems: [] });
    rt.tickStep(0.016);
    const thought = rt.getTrace().recent(1)[0]!.thought;
    expect(['fast-path intuition', 'oracle simulation fallback']).toContain(thought);
  });

  it('policyEnv tracks model prediction when PolicyModel is provided', async () => {
    const { PerformanceRuntime } = await import('../../core/runtime/PerformanceRuntime');
    const { PolicyModel }        = await import('../../core/runtime/PolicyDistillation');
    const { ENVIRONMENTS }       = await import('../../core/runtime/Environment');

    const model = new PolicyModel(Object.values(ENVIRONMENTS));
    // Train toward chaosJam for high-chaos features
    for (let i = 0; i < 50; i++) {
      model.update({ features: { chaos: 0.9, stability: 0.1, groove: 0.2, energy: 0.5, drift: 0.7 }, label: 'chaosJam', margin: 0.5 });
    }
    const rt = new PerformanceRuntime(
      { ...s, chaos: 0.9, stability: 0.1, drift: 0.7 },
      { systems: [], policyModel: model },
    );
    rt.tickStep(0.016);
    const frame = rt.getTrace().recent(1)[0]!;
    expect(frame.usedPolicy).toBe(true);
    expect(frame.policyEnv).toBe('chaosJam');
  });
});
