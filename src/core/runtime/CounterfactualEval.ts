import type { PerformanceState } from '../PerformanceState';
import type { PerformanceAction } from './PerformanceAction';
import type { IntentMemory } from './IntentMemory';
import type { StyleEnvironment } from './Environment';
import type { MetaPolicy } from './MetaPolicy';
import { performanceReducer } from './performanceReducer';
import { mergeStyleWithBias } from './Environment';
import { applyStyle } from './Style';
import { scoreOutcomeWithPolicy } from './MetaPolicy';

// ─── Types ─────────────────────────────────────────────────────────────────────

export interface CounterfactualCase {
  environment:    StyleEnvironment;
  simulatedState: PerformanceState;
  score:          number;  // policy-scored outcome under this env
  delta:          number;  // score − baseline (positive = better than current)
}

// ─── Simulation ────────────────────────────────────────────────────────────────

/**
 * Apply a candidate environment's compiler bias to an action sequence, then
 * run it through the reducer from the given state.
 *
 * This is a pure projection — it does NOT touch the live runtime.
 */
export function simulate(
  state:   PerformanceState,
  actions: PerformanceAction[],
  env:     StyleEnvironment,
): PerformanceState {
  const biasedStyle  = mergeStyleWithBias(env.style, env.compilerBias);
  const biasedActions = applyStyle(actions, biasedStyle);
  let simState = state;
  for (const action of biasedActions) {
    simState = performanceReducer(simState, action);
  }
  return simState;
}

// ─── Counterfactual evaluation ─────────────────────────────────────────────────

/**
 * Score each candidate environment by simulating the given action sequence
 * from the current state under that environment's bias.
 *
 * Returns one CounterfactualCase per environment, sorted by descending score.
 * The baseline is the score of the first environment in the list (typically
 * the currently active one).
 */
export function evaluateCounterfactual(
  state:       PerformanceState,
  actions:     PerformanceAction[],
  policy:      MetaPolicy,
  environments: StyleEnvironment[],
): CounterfactualCase[] {
  if (environments.length === 0) return [];

  const cases = environments.map((env): CounterfactualCase => {
    const simState = simulate(state, actions, env);
    return {
      environment:    env,
      simulatedState: simState,
      score:          scoreOutcomeWithPolicy(simState, policy),
      delta:          0,
    };
  });

  const baseline = cases[0]!.score;
  for (const c of cases) {
    c.delta = c.score - baseline;
  }

  return cases.sort((a, b) => b.score - a.score);
}

/**
 * Pick the best-scoring environment from a set of counterfactual cases.
 * Returns null when the baseline (index 0 before sort, i.e. current env) is
 * already optimal or no improvement exceeds the threshold.
 */
export function recommendEnvironment(
  cases:               CounterfactualCase[],
  currentEnvName:      string,
  improvementThreshold = 0.05,
): StyleEnvironment | null {
  if (cases.length === 0) return null;
  const best = cases[0]!;
  if (best.environment.name === currentEnvName) return null;
  if (best.delta < improvementThreshold) return null;
  return best.environment;
}
