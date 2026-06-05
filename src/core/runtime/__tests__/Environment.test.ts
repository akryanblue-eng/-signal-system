import { describe, it, expect } from 'vitest';
import {
  ENVIRONMENTS,
  EnvironmentManager,
  detectEnvironment,
  mergeStyleWithBias,
  scoreEnvironmentFromMemory,
} from '../Environment';
import { DEFAULT_PERFORMANCE_STATE } from '../../PerformanceState';
import type { PerformanceState } from '../../PerformanceState';
import { PerformanceRuntime } from '../PerformanceRuntime';
import type { IntentMemory } from '../IntentMemory';

const safeState: PerformanceState = {
  ...DEFAULT_PERFORMANCE_STATE,
  chaos: 0.2, stability: 0.8, drift: 0.1,
};
const chaosState: PerformanceState = {
  ...DEFAULT_PERFORMANCE_STATE,
  chaos: 0.85, stability: 0.3, drift: 0.6,
};
const precisionState: PerformanceState = {
  ...DEFAULT_PERFORMANCE_STATE,
  chaos: 0.1, stability: 0.9, drift: 0.0,
};

const mkMemory = (key: string): IntentMemory => ({
  intent: key, embeddingKey: key,
  actions: [], before: safeState, after: safeState,
  delta: { tension: 0, chaos: 0, groove: 0, energy: 0 },
  score: 0.5, timestamp: Date.now(),
});

const mkEnvMemory = (env: string, score: number): IntentMemory => ({
  intent: 'test', embeddingKey: 'general_control',
  environment: env,
  actions: [], before: safeState, after: safeState,
  delta: { tension: 0, chaos: 0, groove: 0, energy: 0 },
  score, timestamp: Date.now(),
});

describe('ENVIRONMENTS', () => {
  it('has cinematic, precision, and chaosJam presets', () => {
    expect(ENVIRONMENTS.cinematic).toBeDefined();
    expect(ENVIRONMENTS.precision).toBeDefined();
    expect(ENVIRONMENTS.chaosJam).toBeDefined();
  });

  it('chaosJam has higher aggression than cinematic', () => {
    expect(ENVIRONMENTS.chaosJam.style.aggression).toBeGreaterThan(
      ENVIRONMENTS.cinematic.style.aggression,
    );
  });

  it('precision has lower aggression than cinematic', () => {
    expect(ENVIRONMENTS.precision.style.aggression).toBeLessThan(
      ENVIRONMENTS.cinematic.style.aggression,
    );
  });
});

describe('mergeStyleWithBias', () => {
  it('multiplies aggression by chaosWeight', () => {
    const style   = { ...ENVIRONMENTS.cinematic.style, aggression: 0.5 };
    const bias    = ENVIRONMENTS.chaosJam.compilerBias; // chaosWeight = 1.6
    const merged  = mergeStyleWithBias(style, bias);
    expect(merged.aggression).toBeCloseTo(0.5 * 1.6);
  });

  it('multiplies precision by stabilityWeight', () => {
    const style  = { ...ENVIRONMENTS.cinematic.style, precision: 0.8 };
    const bias   = ENVIRONMENTS.precision.compilerBias; // stabilityWeight = 1.8
    const merged = mergeStyleWithBias(style, bias);
    expect(merged.precision).toBeCloseTo(0.8 * 1.8);
  });
});

describe('detectEnvironment', () => {
  it('returns chaosJam for high chaos state', () => {
    const result = detectEnvironment(chaosState, [], ENVIRONMENTS.cinematic);
    expect(result?.name).toBe('chaosJam');
  });

  it('returns precision for high-stability low-chaos state with 2+ precision intents', () => {
    const memories = [
      mkMemory('stability_control'),
      mkMemory('rhythm_control'),
    ];
    const result = detectEnvironment(precisionState, memories, ENVIRONMENTS.cinematic);
    expect(result?.name).toBe('precision');
  });

  it('returns null when current env already matches detected', () => {
    const result = detectEnvironment(chaosState, [], ENVIRONMENTS.chaosJam);
    expect(result).toBeNull();
  });

  it('returns cinematic for a balanced state with no strong signals', () => {
    const result = detectEnvironment(safeState, [], ENVIRONMENTS.chaosJam);
    expect(result?.name).toBe('cinematic');
  });

  it('detects chaosJam from 3+ entropy intents in recent history', () => {
    const memories = [
      mkMemory('entropy_control'),
      mkMemory('entropy_control'),
      mkMemory('entropy_control'),
    ];
    const result = detectEnvironment(safeState, memories, ENVIRONMENTS.cinematic);
    expect(result?.name).toBe('chaosJam');
  });
});

describe('EnvironmentManager', () => {
  it('starts in the initial environment', () => {
    const mgr = new EnvironmentManager(ENVIRONMENTS.precision);
    expect(mgr.get().name).toBe('precision');
  });

  it('switch() changes environment immediately', () => {
    const mgr = new EnvironmentManager(ENVIRONMENTS.cinematic);
    mgr.switch(ENVIRONMENTS.chaosJam);
    expect(mgr.get().name).toBe('chaosJam');
  });

  it('autoSelect respects cooldown (default 60 frames)', () => {
    const mgr = new EnvironmentManager(ENVIRONMENTS.cinematic, 60);
    for (let i = 0; i < 59; i++) mgr.autoSelect(chaosState, []);
    expect(mgr.get().name).toBe('cinematic'); // not yet switched
    const switched = mgr.autoSelect(chaosState, []); // 60th call
    expect(switched).toBe(true);
    expect(mgr.get().name).toBe('chaosJam');
  });

  it('autoSelect does nothing when locked', () => {
    const mgr = new EnvironmentManager(ENVIRONMENTS.cinematic, 1);
    mgr.lock();
    mgr.autoSelect(chaosState, []);
    expect(mgr.get().name).toBe('cinematic');
  });

  it('unlock() re-enables auto-select', () => {
    const mgr = new EnvironmentManager(ENVIRONMENTS.cinematic, 1);
    mgr.lock();
    mgr.unlock();
    mgr.autoSelect(chaosState, []);
    expect(mgr.get().name).toBe('chaosJam');
  });
});

describe('scoreEnvironmentFromMemory', () => {
  it('returns 0.5 when no memories match the env', () => {
    const mems = [mkEnvMemory('cinematic', 0.8), mkEnvMemory('cinematic', 0.9)];
    expect(scoreEnvironmentFromMemory('chaosJam', mems)).toBe(0.5);
  });

  it('returns the score when only one matching memory exists', () => {
    expect(scoreEnvironmentFromMemory('chaosJam', [mkEnvMemory('chaosJam', 0.8)])).toBeCloseTo(0.8);
  });

  it('scores higher when the most recent memories are high quality', () => {
    // Identical older entries — only the most-recent score differs
    const lowRecent  = [0.5, 0.5, 0.5, 0.1].map(s => mkEnvMemory('cinematic', s));
    const highRecent = [0.5, 0.5, 0.5, 0.9].map(s => mkEnvMemory('cinematic', s));
    expect(scoreEnvironmentFromMemory('cinematic', highRecent)).toBeGreaterThan(
      scoreEnvironmentFromMemory('cinematic', lowRecent),
    );
  });

  it('returns 0.5 for empty memory list', () => {
    expect(scoreEnvironmentFromMemory('cinematic', [])).toBe(0.5);
  });
});

describe('detectEnvironment (memory-weighted)', () => {
  it('favors env with strong historical memory scores even from a neutral state', () => {
    const mems = Array.from({ length: 5 }, () => mkEnvMemory('chaosJam', 0.9));
    const result = detectEnvironment(safeState, mems, ENVIRONMENTS.cinematic);
    expect(result?.name).toBe('chaosJam');
  });

  it('avoids env whose memories show poor outcomes, deferring to neutral fallback', () => {
    const mems = Array.from({ length: 10 }, () => mkEnvMemory('chaosJam', 0.1));
    // Even a chaotic state with bad chaosJam history should not select chaosJam
    const result = detectEnvironment(chaosState, mems, ENVIRONMENTS.cinematic);
    expect(result?.name).not.toBe('chaosJam');
  });

  it('selects based on memory over state when evidence is dense', () => {
    // cinematic has consistently good memory; state would normally suggest chaosJam
    const mems = Array.from({ length: 10 }, () => mkEnvMemory('cinematic', 0.95));
    const result = detectEnvironment(chaosState, mems, ENVIRONMENTS.chaosJam);
    expect(result?.name).toBe('cinematic');
  });
});

describe('PerformanceRuntime environment integration', () => {
  it('switchEnvironment() changes the active environment', () => {
    const rt = new PerformanceRuntime(safeState, { systems: [] });
    expect(rt.getEnvironment().get().name).toBe('cinematic');
    rt.switchEnvironment(ENVIRONMENTS.chaosJam);
    expect(rt.getEnvironment().get().name).toBe('chaosJam');
  });

  it('auto-selects chaosJam after 60 ticks with persistent chaos state', () => {
    const rt = new PerformanceRuntime(
      { ...DEFAULT_PERFORMANCE_STATE, chaos: 0.85, drift: 0.6 },
      { systems: [], environment: new EnvironmentManager(ENVIRONMENTS.cinematic, 1) },
    );
    rt.tickStep(0.016);
    expect(rt.getEnvironment().get().name).toBe('chaosJam');
  });
});
