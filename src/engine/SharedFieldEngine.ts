import type { LatentState } from '../core/types/latent';
import type { Attractor } from '../core/types/attractor';
import { PerformanceKernel, type KernelOutput } from '../core/kernel/PerformanceKernel';

export interface PerformerState {
  id:     string;
  latent: LatentState;
  phase:  number; // rhythmic phase [0, 2π]
  energy: number; // [0, 1]
}

export interface PhaseCoupling {
  couplingStrength: number; // [0, 1]
  syncPull:         boolean;
}

export interface SharedFieldState {
  globalAttractors: Attractor[];
  performers:       Map<string, PerformerState>;
  phaseLockIndex:   number; // [0, 1] — 1 = fully synchronized
  coherence:        number; // [0, 1]
  entropy:          number; // [0, 1]
}

/**
 * Manages a unified latent field for multiple simultaneous performers.
 *
 * Performers are phase-locked oscillators inside a shared space.
 * Synchronization, divergence, and re-entrainment emerge from the math —
 * no performer is explicitly designated "leader" or "follower".
 */
export class SharedFieldEngine {
  private state: SharedFieldState = {
    globalAttractors: [],
    performers:       new Map(),
    phaseLockIndex:   0,
    coherence:        1,
    entropy:          0,
  };

  private kernels: Map<string, PerformanceKernel> = new Map();

  registerPerformer(id: string): void {
    if (!this.state.performers.has(id)) {
      this.state.performers.set(id, {
        id,
        latent: { drift_mean: 0, energy: 0.5, stability: 0.7, adaptation: 0.5, cumulative_drift: 0 },
        phase:  0,
        energy: 0.5,
      });
      this.kernels.set(id, new PerformanceKernel());
    }
  }

  /** Update a single performer's latent state and advance their phase. */
  updatePerformer(id: string, latent: LatentState, phaseDelta: number): KernelOutput | null {
    const performer = this.state.performers.get(id);
    const kernel    = this.kernels.get(id);
    if (!performer || !kernel) return null;

    performer.latent = latent;
    performer.phase  = (performer.phase + phaseDelta) % (2 * Math.PI);
    performer.energy = latent.energy;

    const output = kernel.tick(latent);
    this.recomputeField();
    return output;
  }

  /** Compute phase coupling between two performers. */
  computePhaseCoupling(idA: string, idB: string): PhaseCoupling | null {
    const a = this.state.performers.get(idA);
    const b = this.state.performers.get(idB);
    if (!a || !b) return null;

    const rhythmDiff     = Math.abs(a.phase - b.phase);
    const energyAlignment = 1 - Math.abs(a.energy - b.energy);

    return {
      couplingStrength: energyAlignment * Math.exp(-rhythmDiff),
      syncPull:         rhythmDiff < 0.2,
    };
  }

  getState(): Readonly<SharedFieldState> {
    return this.state;
  }

  private recomputeField(): void {
    const performers = Array.from(this.state.performers.values());
    if (performers.length === 0) return;

    this.state.phaseLockIndex = this.computePhaseLock(performers);
    this.state.coherence      = this.computeCoherence(performers);
    this.state.entropy        = 1 - this.state.coherence;
  }

  private computePhaseLock(performers: PerformerState[]): number {
    if (performers.length < 2) return 1;
    // Kuramoto order parameter: |Σ e^(iφ)| / N
    let sumCos = 0;
    let sumSin = 0;
    for (const p of performers) {
      sumCos += Math.cos(p.phase);
      sumSin += Math.sin(p.phase);
    }
    return Math.sqrt(sumCos ** 2 + sumSin ** 2) / performers.length;
  }

  private computeCoherence(performers: PerformerState[]): number {
    if (performers.length === 0) return 1;
    const avgStability = performers.reduce((s, p) => s + p.latent.stability, 0) / performers.length;
    const avgEnergy    = performers.reduce((s, p) => s + p.energy, 0)           / performers.length;
    const phaseLock    = this.state.phaseLockIndex;
    return (avgStability * 0.4 + avgEnergy * 0.3 + phaseLock * 0.3);
  }
}
