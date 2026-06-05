import type { LatentState } from '../core/types/latent';
import type { KernelOutput } from '../core/kernel/PerformanceKernel';
import { PerformanceKernel } from '../core/kernel/PerformanceKernel';
import type { FieldState } from './SteeringFieldEngine';
import { SteeringFieldEngine } from './SteeringFieldEngine';
import type { MidiAttractorController } from './MidiAttractorController';

export interface PerformerFeedback {
  suggestedEnergyShift:    number;         // positive = push energy up
  attractorPullDirection:  { x: number; y: number };
  confidenceZoneHint:      'stable' | 'risky' | 'explosive';
  timingBias:              number;         // [−0.1, 0.1] seconds
}

export interface BrainLoopOutput {
  field:    FieldState;
  kernel:   KernelOutput;
  feedback: PerformerFeedback;
}

/**
 * Closes the performer–field–kernel loop into a bidirectional feedback system.
 *
 * Three channels:
 *   A. Performer → Field   (MIDI shapes attractor landscape)
 *   B. Field → Kernel      (field pressure signals inform prediction)
 *   C. Kernel → Performer  (kernel emits coaching hints, not commands)
 */
export class BidirectionalBrainLoop {
  constructor(
    private readonly kernel:   PerformanceKernel,
    private readonly field:    SteeringFieldEngine,
    private readonly midiCtrl: MidiAttractorController,
  ) {}

  tick(latentState: LatentState): BrainLoopOutput {
    // A: MIDI controller already updated attractors via processEvents()
    const attractors = this.midiCtrl.getAttractors();
    const fieldState = this.field.applyAttractors(attractors);

    // B: Fold field pressure signals into latent state before kernel sees it
    const enriched: LatentState = {
      ...latentState,
      cumulative_drift: latentState.cumulative_drift + fieldState.turbulence * 0.1,
    };
    const kernelOutput = this.kernel.tick(enriched);

    // C: Generate performer feedback
    const feedback = this.generateFeedback(kernelOutput, fieldState);

    return { field: fieldState, kernel: kernelOutput, feedback };
  }

  private generateFeedback(kernel: KernelOutput, field: FieldState): PerformerFeedback {
    const hint: PerformerFeedback['confidenceZoneHint'] =
      kernel.mode === 'PERFORMING' ? 'stable' :
      kernel.mode === 'RECOVERING' ? 'risky' : 'explosive';

    return {
      suggestedEnergyShift:   kernel.metrics.confidence > 0.8 ? 0.1 : -0.15,
      attractorPullDirection: field.fieldBias,
      confidenceZoneHint:     hint,
      timingBias:             field.stability > 0.7 ? -0.02 : 0.03,
    };
  }
}
