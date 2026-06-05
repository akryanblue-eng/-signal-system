import type { LatentState } from '../core/types/latent';
import { PerformanceKernel, type KernelOutput } from '../core/kernel/PerformanceKernel';

export interface GPUAttractor {
  x:        number;
  y:        number;
  strength: number;
}

export interface SceneUniforms {
  attractors: GPUAttractor[];
  state: {
    drift:            number;
    energy:           number;
    stability:        number;
    cumulative_drift: number;
  };
}

/**
 * Bridges the PerformanceKernel → Three.js shader uniforms.
 *
 * The kernel computes intent; the bridge translates that intent
 * into GPU-readable uniform data without coupling the two layers.
 */
export class FlowKernelBridge {
  private kernel: PerformanceKernel;
  private updateUniforms: (uniforms: SceneUniforms) => void;

  constructor(kernel: PerformanceKernel, updateUniforms: (uniforms: SceneUniforms) => void) {
    this.kernel = kernel;
    this.updateUniforms = updateUniforms;
  }

  tick(state: LatentState): KernelOutput {
    const output = this.kernel.tick(state);
    this.updateUniforms({
      attractors: this.buildGPUAttractors(output),
      state: {
        drift:            state.drift_mean,
        energy:           state.energy,
        stability:        state.stability,
        cumulative_drift: state.cumulative_drift,
      },
    });
    return output;
  }

  private buildGPUAttractors(output: KernelOutput): GPUAttractor[] {
    // Primary flow-state attractor strength scales with confidence
    return [
      { x: 0.3, y: 0.7, strength: output.mode === 'PERFORMING' ? 1.2 : 0.8 },
      { x: 0.5, y: 0.5, strength: output.metrics.confidence },
    ];
  }
}
