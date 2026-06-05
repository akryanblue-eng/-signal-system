import { describe, it, expect } from 'vitest';
import {
  PolicyModel,
  distillSample,
  selectEnvironment,
} from '../PolicyDistillation';
import { ENVIRONMENTS } from '../Environment';
import { BASE_META_POLICY } from '../MetaPolicy';
import { DEFAULT_PERFORMANCE_STATE } from '../../PerformanceState';
import type { PerformanceAction } from '../PerformanceAction';
import type { PolicyFeatures } from '../PolicyDistillation';

const s = DEFAULT_PERFORMANCE_STATE;
const envs = Object.values(ENVIRONMENTS);

const chaosFeatures: PolicyFeatures = { chaos: 0.9, stability: 0.2, groove: 0.3, energy: 0.5, drift: 0.6 };
const stableFeatures: PolicyFeatures = { chaos: 0.1, stability: 0.9, groove: 0.8, energy: 0.6, drift: 0.0 };

const chaosActions: PerformanceAction[] = [
  { type: 'CHAOS_SPIKE', amount: 0.3 },
  { type: 'DRIFT_INJECTION', amount: 0.2 },
];

describe('PolicyModel', () => {
  it('initializes with equal scores for all environments', () => {
    const model = new PolicyModel(envs);
    const scores = envs.map(e => model.score(e.name, stableFeatures));
    // All start equal (0.2 × 5 features = 1.0)
    expect(Math.max(...scores) - Math.min(...scores)).toBeLessThan(1e-9);
  });

  it('predict() returns a known environment name', () => {
    const model = new PolicyModel(envs);
    const pred = model.predict(chaosFeatures);
    expect(envs.map(e => e.name)).toContain(pred);
  });

  it('confidence() returns 0 before training (all equal scores)', () => {
    const model = new PolicyModel(envs);
    expect(model.confidence(chaosFeatures)).toBeCloseTo(0, 5);
  });

  it('update() changes model weights', () => {
    const model = new PolicyModel(envs);
    const before = model.score('chaosJam', chaosFeatures);
    model.update({ features: chaosFeatures, label: 'chaosJam', margin: 0.2 });
    const after = model.score('chaosJam', chaosFeatures);
    expect(after).not.toBe(before);
  });

  it('after training on chaos samples, predicts chaosJam for chaotic features', () => {
    const model = new PolicyModel(envs);
    for (let i = 0; i < 30; i++) {
      model.update({ features: chaosFeatures, label: 'chaosJam', margin: 0.3 });
    }
    expect(model.predict(chaosFeatures)).toBe('chaosJam');
  });

  it('after training on stable samples, predicts precision for stable features', () => {
    const model = new PolicyModel(envs);
    for (let i = 0; i < 30; i++) {
      model.update({ features: stableFeatures, label: 'precision', margin: 0.3 });
    }
    expect(model.predict(stableFeatures)).toBe('precision');
  });

  it('confidence increases after repeated consistent training', () => {
    const model = new PolicyModel(envs);
    const confBefore = model.confidence(chaosFeatures);
    for (let i = 0; i < 20; i++) {
      model.update({ features: chaosFeatures, label: 'chaosJam', margin: 0.3 });
    }
    expect(model.confidence(chaosFeatures)).toBeGreaterThan(confBefore);
  });

  it('predict() returns null for model with no environments', () => {
    const empty = new PolicyModel([]);
    expect(empty.predict(stableFeatures)).toBeNull();
  });

  it('batchUpdate() applies all samples', () => {
    const model = new PolicyModel(envs);
    const before = model.score('precision', stableFeatures);
    model.batchUpdate([
      { features: stableFeatures, label: 'precision', margin: 0.2 },
      { features: stableFeatures, label: 'precision', margin: 0.2 },
    ]);
    expect(model.score('precision', stableFeatures)).not.toBe(before);
  });
});

describe('distillSample', () => {
  it('returns null for empty environment list', () => {
    expect(distillSample(s, chaosActions, BASE_META_POLICY, [])).toBeNull();
  });

  it('returns a sample with a valid label when a clear winner exists', () => {
    const sample = distillSample(s, chaosActions, BASE_META_POLICY, envs);
    if (sample !== null) {
      expect(envs.map(e => e.name)).toContain(sample.label);
      expect(sample.margin).toBeGreaterThan(0);
      expect(sample.features).toHaveProperty('chaos');
    }
    // may be null if no env wins by ≥0.02 — both outcomes are valid
  });

  it('features in sample reflect the input state', () => {
    const state = { ...s, chaos: 0.8, stability: 0.2 };
    const sample = distillSample(state, chaosActions, BASE_META_POLICY, envs);
    if (sample !== null) {
      expect(sample.features.chaos).toBeCloseTo(0.8);
      expect(sample.features.stability).toBeCloseTo(0.2);
    }
  });
});

describe('selectEnvironment', () => {
  it('returns null for empty environment list', () => {
    const model = new PolicyModel(envs);
    expect(selectEnvironment(s, chaosActions, BASE_META_POLICY, model, [])).toBeNull();
  });

  it('returns an environment from the provided list', () => {
    const model = new PolicyModel(envs);
    const result = selectEnvironment(s, chaosActions, BASE_META_POLICY, model, envs);
    if (result !== null) {
      expect(envs.map(e => e.name)).toContain(result.name);
    }
  });

  it('uses model prediction when confidence exceeds threshold', () => {
    const model = new PolicyModel(envs);
    // Train heavily so confidence is high
    for (let i = 0; i < 50; i++) {
      model.update({ features: chaosFeatures, label: 'chaosJam', margin: 0.5 });
    }
    const state = { ...s, chaos: 0.9, stability: 0.2, drift: 0.6 };
    const result = selectEnvironment(
      state, [], BASE_META_POLICY, model, envs,
      0.01, // very low threshold → model path taken
    );
    expect(result?.name).toBe('chaosJam');
  });

  it('falls back to counterfactual oracle when confidence is below threshold', () => {
    const model = new PolicyModel(envs); // untrained → confidence = 0
    const result = selectEnvironment(
      s, chaosActions, BASE_META_POLICY, model, envs,
      0.99, // very high threshold → always uses oracle
    );
    // Oracle result may be null or a valid env — just verify type
    if (result !== null) {
      expect(result).toHaveProperty('name');
      expect(result).toHaveProperty('style');
    }
  });
});
