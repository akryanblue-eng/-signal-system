import type * as THREE_TYPES from 'three';
import type { ManifoldState } from '../core/manifold/ManifoldRuntime';
import type { FieldFeedbackSignal } from '../engine/FieldFeedback';
import type { FlowArrowScene } from './FlowArrowScene';
import { generateFlowField }  from './generateFlowField';
import { renderFlowField }    from './renderFlowField';

export interface RenderPayload {
  state:    ManifoldState;
  chaos:    number;
  damping:  number;
  feedback: FieldFeedbackSignal | null;
}

/**
 * Translates a physics snapshot into a visual update on the FlowArrowScene.
 *
 * Separates rendering concerns from the runtime loop — the renderer does not
 * know how state was produced, only how to display it.
 */
export class FlowFieldRenderer {
  constructor(
    private readonly scene:      FlowArrowScene,
    private readonly THREE:      typeof THREE_TYPES,
    private readonly resolution: number = 10,
  ) {}

  render({ state, chaos, feedback }: RenderPayload): void {
    const field = generateFlowField(state, this.resolution);

    renderFlowField(this.scene, field, this.THREE, cell => {
      // Pressure = local drift magnitude + feedback overlay
      const distFactor = Math.sqrt(cell.pos[0] ** 2 + cell.pos[1] ** 2) / 7;
      const feedbackPressure = feedback ? feedback.driftPressure * 0.3 : 0;
      return Math.min(Math.abs(state.drift) * 0.5 + distFactor * 0.3 + feedbackPressure + chaos * 0.2, 1);
    });

    this.scene.render();
  }
}
