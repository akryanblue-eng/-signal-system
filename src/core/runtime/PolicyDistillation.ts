import type { PerformanceState } from '../PerformanceState';
import type { StyleEnvironment } from './Environment';
import type { PerformanceAction } from './PerformanceAction';
import type { MetaPolicy } from './MetaPolicy';
import { ENVIRONMENTS } from './Environment';
import { evaluateCounterfactual } from './CounterfactualEval';

// ─── Feature extraction ────────────────────────────────────────────────────────

export interface PolicyFeatures {
  chaos:      number; // [0, 1]
  stability:  number; // [0, 1]
  groove:     number; // [0, 1]
  energy:     number; // [0, 1]
  drift:      number; // [0, 1]
}

export function extractFeatures(state: PerformanceState): PolicyFeatures {
  return {
    chaos:     state.chaos,
    stability: state.stability,
    groove:    state.groove,
    energy:    state.energy,
    drift:     state.drift,
  };
}

// ─── Policy sample ─────────────────────────────────────────────────────────────

/** One training observation: features → winning environment label. */
export interface PolicySample {
  features: PolicyFeatures;
  label:    string; // winning environment name
  margin:   number; // score delta between winner and runner-up
}

// ─── Model ────────────────────────────────────────────────────────────────────

type FeatureKey = keyof PolicyFeatures;

const FEATURE_KEYS: FeatureKey[] = ['chaos', 'stability', 'groove', 'energy', 'drift'];

/**
 * Lightweight linear model: for each environment, a weight per feature.
 * `predict(features)` returns the env whose dot-product score is highest.
 *
 * Learned via online gradient descent from counterfactual samples.
 * Learning rate α = 0.05; weights initialized to uniform (all 0.2).
 */
export class PolicyModel {
  private weights: Record<string, Record<FeatureKey, number>>;
  private readonly alpha: number;

  constructor(
    environments: StyleEnvironment[] = Object.values(ENVIRONMENTS),
    alpha = 0.05,
  ) {
    this.alpha   = alpha;
    this.weights = {};
    for (const env of environments) {
      this.weights[env.name] = {
        chaos:     0.2,
        stability: 0.2,
        groove:    0.2,
        energy:    0.2,
        drift:     0.2,
      };
    }
  }

  /** Linear score for an environment given a feature vector. */
  score(envName: string, features: PolicyFeatures): number {
    const w = this.weights[envName];
    if (!w) return 0;
    return FEATURE_KEYS.reduce((sum, k) => sum + w[k] * features[k], 0);
  }

  /**
   * Return the highest-scoring environment name.
   * Returns null when the model has no environments.
   */
  predict(features: PolicyFeatures): string | null {
    const envNames = Object.keys(this.weights);
    if (envNames.length === 0) return null;

    let best     = envNames[0]!;
    let bestScore = this.score(best, features);
    for (const name of envNames.slice(1)) {
      const s = this.score(name, features);
      if (s > bestScore) { bestScore = s; best = name; }
    }
    return best;
  }

  /** Confidence gap between the top-1 and top-2 predicted environments. */
  confidence(features: PolicyFeatures): number {
    const envNames = Object.keys(this.weights);
    if (envNames.length < 2) return 1;

    const scores = envNames
      .map(n => this.score(n, features))
      .sort((a, b) => b - a);
    return (scores[0]! - scores[1]!) / Math.max(1e-6, scores[0]!);
  }

  /**
   * Online update from a single PolicySample.
   * Pushes the winning env's weights up toward sample features,
   * and pushes all losing envs' weights down proportional to their score.
   */
  update(sample: PolicySample): void {
    const { features, label, margin } = sample;
    const lr = this.alpha * Math.max(0.1, margin);

    for (const [name, w] of Object.entries(this.weights)) {
      if (name === label) {
        for (const k of FEATURE_KEYS) w[k] += lr * features[k];
      } else {
        for (const k of FEATURE_KEYS) w[k] -= lr * 0.5 * features[k];
      }
    }
  }

  /** Batch update from multiple samples. */
  batchUpdate(samples: PolicySample[]): void {
    for (const s of samples) this.update(s);
  }
}

// ─── Distillation from counterfactuals ────────────────────────────────────────

/**
 * Run counterfactual evaluation and convert the result to a PolicySample
 * for online learning.  Returns null when no clear winner exists (delta < 0.02).
 */
export function distillSample(
  state:        PerformanceState,
  actions:      PerformanceAction[],
  policy:       MetaPolicy,
  environments: StyleEnvironment[],
): PolicySample | null {
  const cases = evaluateCounterfactual(state, actions, policy, environments);
  if (cases.length < 2) return null;

  const winner   = cases[0]!;
  const runnerUp = cases[1]!;
  const margin   = winner.score - runnerUp.score;
  if (margin < 0.02) return null; // too close to call

  return {
    features: extractFeatures(state),
    label:    winner.environment.name,
    margin,
  };
}

// ─── Hybrid environment selection ─────────────────────────────────────────────

/**
 * Select an environment using the PolicyModel when confidence is above the
 * threshold, falling back to the counterfactual oracle otherwise.
 *
 * This is the runtime-hot path: cheap linear prediction most of the time,
 * expensive simulation only when the model is unsure.
 */
export function selectEnvironment(
  state:               PerformanceState,
  actions:             PerformanceAction[],
  policy:              MetaPolicy,
  model:               PolicyModel,
  environments:        StyleEnvironment[],
  confidenceThreshold = 0.3,
): StyleEnvironment | null {
  if (environments.length === 0) return null;

  const features    = extractFeatures(state);
  const conf        = model.confidence(features);
  const envMap      = Object.fromEntries(environments.map(e => [e.name, e]));

  if (conf >= confidenceThreshold) {
    const predicted = model.predict(features);
    return predicted ? (envMap[predicted] ?? null) : null;
  }

  // Fall back to counterfactual oracle + distill a new sample
  const cases = evaluateCounterfactual(state, actions, policy, environments);
  return cases.length > 0 ? (cases[0]!.environment) : null;
}
