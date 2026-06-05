import type { LatentState } from '../types/latent';

export type PerformanceMode = 'PERFORMING' | 'RECOVERING' | 'TRANSITIONING' | 'IDLE';

export interface KernelOutput {
  mode: PerformanceMode;
  metrics: {
    confidence: number;   // [0, 1]
    stability:  number;   // [0, 1]
    energy:     number;   // [0, 1]
    pressure:   number;   // [0, 1]
  };
  steeringIntensity: number; // how strongly the kernel wants to steer
}

/**
 * Core decision layer — reads latent state, emits steering intent.
 *
 * The kernel is READ-ONLY with respect to audio until Stage 4.
 * It observes and advises; it does not command.
 */
export class PerformanceKernel {
  private history: LatentState[] = [];
  private readonly windowSize = 16;

  tick(state: LatentState): KernelOutput {
    this.history.push(state);
    if (this.history.length > this.windowSize) {
      this.history.shift();
    }

    const confidence = this.computeConfidence();
    const mode = this.classifyMode(state, confidence);
    const steeringIntensity = this.computeSteeringIntensity(state, confidence);

    return {
      mode,
      metrics: {
        confidence,
        stability: state.stability,
        energy:    state.energy,
        pressure:  Math.min(state.cumulative_drift, 1),
      },
      steeringIntensity,
    };
  }

  private computeConfidence(): number {
    if (this.history.length < 2) return 0.5;
    const stabilities = this.history.map(s => s.stability);
    const mean = stabilities.reduce((a, b) => a + b, 0) / stabilities.length;
    const variance = stabilities.reduce((s, v) => s + (v - mean) ** 2, 0) / stabilities.length;
    return Math.max(0, 1 - variance * 4);
  }

  private classifyMode(state: LatentState, confidence: number): PerformanceMode {
    if (state.energy < 0.2 || state.stability < 0.2) return 'RECOVERING';
    if (confidence > 0.7 && state.energy > 0.5)       return 'PERFORMING';
    if (state.cumulative_drift > 0.7)                  return 'TRANSITIONING';
    return 'IDLE';
  }

  private computeSteeringIntensity(state: LatentState, confidence: number): number {
    const urgency = state.cumulative_drift * 0.4 + (1 - state.stability) * 0.4 + (1 - confidence) * 0.2;
    return Math.min(1, urgency);
  }
}
