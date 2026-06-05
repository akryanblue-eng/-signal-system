import { describe, it, expect } from 'vitest';
import { parseIntent, compileIntent, handleIntent } from '../IntentCompiler';
import { PerformanceRuntime } from '../PerformanceRuntime';
import { DEFAULT_PERFORMANCE_STATE } from '../../PerformanceState';

describe('parseIntent', () => {
  it('extracts high intensity from "hard"', () => {
    const intent = parseIntent('push energy up hard');
    expect(intent.intensity).toBeGreaterThan(0.5);
  });

  it('extracts low intensity from "subtle"', () => {
    const intent = parseIntent('subtle groove lock');
    expect(intent.intensity).toBeLessThan(0.5);
  });

  it('identifies "energy" target', () => {
    const intent = parseIntent('lift the energy');
    expect(intent.targets).toContain('energy');
  });

  it('identifies "chaos" target', () => {
    const intent = parseIntent('add some glitch chaos');
    expect(intent.targets).toContain('chaos');
  });

  it('identifies multiple targets', () => {
    const intent = parseIntent('energy up and tighten groove');
    expect(intent.targets).toContain('energy');
    expect(intent.targets).toContain('groove');
  });
});

describe('compileIntent', () => {
  it('"energy" target produces TENSION_BUILD and GROOVE_LOCK', () => {
    const actions = compileIntent({ raw: 'energy', intensity: 0.5, targets: ['energy'] });
    const types = actions.map(a => a.type);
    expect(types).toContain('TENSION_BUILD');
    expect(types).toContain('GROOVE_LOCK');
  });

  it('"chaos" target produces CHAOS_SPIKE and DRIFT_INJECTION', () => {
    const actions = compileIntent({ raw: 'chaos', intensity: 0.5, targets: ['chaos'] });
    const types = actions.map(a => a.type);
    expect(types).toContain('CHAOS_SPIKE');
    expect(types).toContain('DRIFT_INJECTION');
  });

  it('"calm" target produces TENSION_RELEASE and STABILITY_RESTORE', () => {
    const actions = compileIntent({ raw: 'calm', intensity: 0.5, targets: ['calm'] });
    const types = actions.map(a => a.type);
    expect(types).toContain('TENSION_RELEASE');
    expect(types).toContain('STABILITY_RESTORE');
  });

  it('deduplicates actions when multiple targets produce the same type', () => {
    // 'energy' and 'groove' both produce GROOVE_LOCK — should appear once
    const actions = compileIntent({ raw: '', intensity: 0.5, targets: ['energy', 'groove'] });
    const lockCount = actions.filter(a => a.type === 'GROOVE_LOCK').length;
    expect(lockCount).toBe(1);
  });
});

describe('handleIntent integration', () => {
  it('dispatches actions into runtime; state reflects change', () => {
    const rt = new PerformanceRuntime({ ...DEFAULT_PERFORMANCE_STATE, chaos: 0.1 }, []);
    handleIntent('add glitch chaos', rt.dispatch);
    rt.tickStep(0.016);
    expect(rt.getState().chaos).toBeGreaterThan(0.1);
  });

  it('calm intent reduces tension after tick', () => {
    const rt = new PerformanceRuntime({ ...DEFAULT_PERFORMANCE_STATE, tension: 0.8 }, []);
    handleIntent('calm it down', rt.dispatch);
    rt.tickStep(0.016);
    expect(rt.getState().tension).toBeLessThan(0.8);
  });
});
