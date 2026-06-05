import { describe, it, expect } from 'vitest';
import {
  BASE_META_POLICY,
  MetaObserver,
  scoreOutcomeWithPolicy,
  evaluatePolicyPerformance,
  updateMetaPolicy,
  computeIdentityQuality,
  computeStyleDrift,
  computeInstability,
} from '../MetaPolicy';
import { DEFAULT_PERFORMANCE_STATE } from '../../PerformanceState';
import type { PerformanceState } from '../../PerformanceState';
import type { IntentMemory } from '../IntentMemory';
import { STYLES } from '../Style';
import { PerformanceRuntime } from '../PerformanceRuntime';

const s = DEFAULT_PERFORMANCE_STATE;

const mkMemory = (after: Partial<PerformanceState>, score?: number): IntentMemory => ({
  intent: 'test', embeddingKey: 'general_control',
  actions: [], before: s,
  after: { ...s, ...after },
  delta: { tension: 0, chaos: 0, groove: 0, energy: 0 },
  score: score ?? 0.5,
  timestamp: Date.now(),
});

describe('scoreOutcomeWithPolicy', () => {
  it('returns a value in [0, 1]', () => {
    const score = scoreOutcomeWithPolicy(s, BASE_META_POLICY);
    expect(score).toBeGreaterThanOrEqual(0);
    expect(score).toBeLessThanOrEqual(1);
  });

  it('high groove + high stability + low chaos → high score', () => {
    const good: PerformanceState = { ...s, groove: 1, stability: 1, chaos: 0, energy: 1 };
    const score = scoreOutcomeWithPolicy(good, BASE_META_POLICY);
    expect(score).toBeGreaterThan(0.8);
  });

  it('low groove + low stability + high chaos → low score', () => {
    const bad: PerformanceState = { ...s, groove: 0, stability: 0, chaos: 1, energy: 0 };
    const score = scoreOutcomeWithPolicy(bad, BASE_META_POLICY);
    expect(score).toBeLessThan(0.2);
  });

  it('responds to policy weight changes', () => {
    const state = { ...s, groove: 1, stability: 0, energy: 0, chaos: 0.5 };
    const groovedPolicy = {
      ...BASE_META_POLICY,
      scoringWeights: { ...BASE_META_POLICY.scoringWeights, groove: 0.7, stability: 0.1 },
    };
    const normalScore = scoreOutcomeWithPolicy(state, BASE_META_POLICY);
    const groovedScore = scoreOutcomeWithPolicy(state, groovedPolicy);
    expect(groovedScore).toBeGreaterThan(normalScore);
  });
});

describe('evaluatePolicyPerformance', () => {
  it('returns 0.5 for empty memories', () => {
    expect(evaluatePolicyPerformance([], BASE_META_POLICY)).toBe(0.5);
  });

  it('returns high value when policy closely predicts actual scores', () => {
    const goodState: PerformanceState = { ...s, groove: 1, stability: 1, chaos: 0 };
    const mem = mkMemory(goodState, 0.95); // score ≈ what policy would predict
    const perf = evaluatePolicyPerformance([mem], BASE_META_POLICY);
    expect(perf).toBeGreaterThan(0.6);
  });
});

describe('updateMetaPolicy', () => {
  it('increases weights when policy performs well (reward > 0.7)', () => {
    // Create memories where policy predictions match actual scores closely
    const goodState: PerformanceState = { ...s, groove: 0.9, stability: 0.9, chaos: 0.1 };
    const memories = Array.from({ length: 10 }, () =>
      mkMemory(goodState, scoreOutcomeWithPolicy(goodState, BASE_META_POLICY)),
    );
    const updated = updateMetaPolicy(BASE_META_POLICY, memories);
    const sumBefore = Object.values(BASE_META_POLICY.scoringWeights).reduce((a, b) => a + b);
    const sumAfter  = Object.values(updated.scoringWeights).reduce((a, b) => a + b);
    expect(sumAfter).toBeGreaterThan(sumBefore);
  });

  it('keeps weights within [0.05, 0.70]', () => {
    let policy = { ...BASE_META_POLICY };
    // Run many updates with bad performance to push weights down
    const badMemories = Array.from({ length: 5 }, () =>
      mkMemory({ groove: 0, stability: 0 }, 0.9), // actual=0.9, predicted≈0.1 → large error
    );
    for (let i = 0; i < 100; i++) {
      policy = updateMetaPolicy(policy, badMemories);
    }
    for (const w of Object.values(policy.scoringWeights)) {
      expect(w).toBeGreaterThanOrEqual(0.05);
      expect(w).toBeLessThanOrEqual(0.70);
    }
  });

  it('preserves non-weight fields', () => {
    const memories = [mkMemory({})];
    const updated = updateMetaPolicy(BASE_META_POLICY, memories);
    expect(updated.driftInterpretation).toEqual(BASE_META_POLICY.driftInterpretation);
    expect(updated.environmentPreferences).toEqual(BASE_META_POLICY.environmentPreferences);
  });
});

describe('computeIdentityQuality', () => {
  it('returns 0.5 for empty observation list', () => {
    expect(computeIdentityQuality([])).toBe(0.5);
  });

  it('returns high quality for consistent high scores with low drift + instability', () => {
    const obs = Array.from({ length: 10 }, () => ({
      timestamp: Date.now(), environment: 'cinematic',
      score: 0.9, drift: 0.1, instability: 0.0, intentKey: 'energy_control',
    }));
    expect(computeIdentityQuality(obs)).toBeGreaterThan(0.7);
  });

  it('penalizes drift > 0.3', () => {
    const lowDrift  = Array.from({ length: 10 }, () => ({ timestamp: 0, environment: 'cinematic', score: 0.7, drift: 0.1, instability: 0.1, intentKey: 'g' }));
    const highDrift = Array.from({ length: 10 }, () => ({ timestamp: 0, environment: 'cinematic', score: 0.7, drift: 0.8, instability: 0.1, intentKey: 'g' }));
    expect(computeIdentityQuality(lowDrift)).toBeGreaterThan(computeIdentityQuality(highDrift));
  });
});

describe('computeStyleDrift', () => {
  it('returns 0 for identical styles', () => {
    expect(computeStyleDrift(STYLES.neutral, STYLES.neutral)).toBe(0);
  });

  it('returns positive value for different styles', () => {
    expect(computeStyleDrift(STYLES.cinematic, STYLES.aggressive)).toBeGreaterThan(0);
  });

  it('is capped at 1', () => {
    const extreme = { name: 'x', aggression: 10, precision: 10, grooveBias: 10 };
    expect(computeStyleDrift(extreme, STYLES.minimal)).toBeLessThanOrEqual(1);
  });
});

describe('computeInstability', () => {
  it('returns 0 for fewer than 2 states', () => {
    expect(computeInstability([])).toBe(0);
    expect(computeInstability([s])).toBe(0);
  });

  it('returns higher value for chaotic state transitions', () => {
    const stable: PerformanceState[] = [
      { ...s, chaos: 0.3 }, { ...s, chaos: 0.3 }, { ...s, chaos: 0.3 },
    ];
    const wild: PerformanceState[] = [
      { ...s, chaos: 0.0 }, { ...s, chaos: 1.0 }, { ...s, chaos: 0.0 },
    ];
    expect(computeInstability(wild)).toBeGreaterThan(computeInstability(stable));
  });
});

describe('MetaObserver', () => {
  it('log() stores observations; size reflects count', () => {
    const obs = new MetaObserver();
    obs.log({ timestamp: 0, environment: 'cinematic', score: 0.7, drift: 0.1, instability: 0.0, intentKey: 'g' });
    expect(obs.size).toBe(1);
  });

  it('evaluate() returns a quality value in [0, 1]', () => {
    const obs = new MetaObserver();
    for (let i = 0; i < 5; i++) {
      obs.log({ timestamp: i, environment: 'cinematic', score: 0.8, drift: 0.1, instability: 0.05, intentKey: 'g' });
    }
    const q = obs.evaluate();
    expect(q).toBeGreaterThanOrEqual(0);
    expect(q).toBeLessThanOrEqual(1);
  });

  it('recent(n) returns last n observations', () => {
    const obs = new MetaObserver();
    for (let i = 0; i < 5; i++) {
      obs.log({ timestamp: i, environment: 'cinematic', score: i * 0.1, drift: 0, instability: 0, intentKey: 'g' });
    }
    expect(obs.recent(3)).toHaveLength(3);
  });

  it('clear() empties history', () => {
    const obs = new MetaObserver();
    obs.log({ timestamp: 0, environment: 'c', score: 0.5, drift: 0, instability: 0, intentKey: 'g' });
    obs.clear();
    expect(obs.size).toBe(0);
  });
});

describe('PerformanceRuntime meta-policy integration', () => {
  it('getMetaObserver().size grows each tick', () => {
    const rt = new PerformanceRuntime({ ...s }, { systems: [] });
    rt.tickStep(0.016);
    rt.tickStep(0.016);
    expect(rt.getMetaObserver().size).toBe(2);
  });

  it('meta-policy updates at frame 50 once memory is populated', () => {
    const rt = new PerformanceRuntime({ ...s }, { systems: [] });
    // Populate memory via handleInput
    for (let i = 0; i < 5; i++) {
      rt.handleInput('add chaos');
      rt.tickStep(0.016);
    }
    const policyBefore = { ...rt.getMetaPolicy().scoringWeights };
    // Advance to frame 50
    for (let i = rt.getState().frameIndex; i < 50; i++) {
      rt.tickStep(0.016);
    }
    const policyAfter = rt.getMetaPolicy().scoringWeights;
    // At least one weight should have changed
    const changed = Object.keys(policyBefore).some(
      k => policyBefore[k as keyof typeof policyBefore] !== policyAfter[k as keyof typeof policyAfter],
    );
    expect(changed).toBe(true);
  });

  it('getIdentityQuality() returns a value in [0, 1]', () => {
    const rt = new PerformanceRuntime({ ...s }, { systems: [] });
    for (let i = 0; i < 5; i++) rt.tickStep(0.016);
    const q = rt.getIdentityQuality();
    expect(q).toBeGreaterThanOrEqual(0);
    expect(q).toBeLessThanOrEqual(1);
  });
});
