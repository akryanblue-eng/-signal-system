import type * as THREE_TYPES from 'three';
import type { ManifoldRuntime, ManifoldState, ManifoldForce } from '../core/manifold/ManifoldRuntime';
import { manifoldGovernor } from '../core/manifold/ManifoldRuntime';
import type { FlowArrowScene } from './FlowArrowScene';
import { generateFlowField }  from './generateFlowField';
import { renderFlowField }    from './renderFlowField';

/**
 * Wire ManifoldRuntime → FlowArrowScene.
 *
 * Runtime = physics source of truth (state evolves in time)
 * Scene   = visualization layer (pure projection, no state of its own)
 *
 * The optional `getForce` callback is the injection point for MIDI,
 * audio, or attractor-derived forces. When omitted, forces are derived
 * from the manifoldGovernor policy (stable neutral behavior).
 *
 * @param runtime   the physics loop instance
 * @param scene     the Three.js arrow scene to drive
 * @param THREE     Three.js module (passed in to avoid bundler coupling)
 * @param getForce  optional force provider — return [dDrift, dEnergy] per frame
 * @param resolution  flow field grid resolution (default 10)
 */
export function bindRuntimeToScene(
  runtime:    ManifoldRuntime,
  scene:      FlowArrowScene,
  THREE:      typeof THREE_TYPES,
  getForce?:  (state: ManifoldState) => ManifoldForce,
  resolution = 10,
): void {
  runtime.start(
    // Physics step — resolve forces then advance state
    (state: ManifoldState, dt: number) => {
      const force: ManifoldForce = getForce
        ? getForce(state)
        : defaultForce(state);
      runtime.forces = force;
      return runtime.step(state, dt, force);
    },
    // Render step — project state → vector field → arrows
    (state: ManifoldState) => {
      const field = generateFlowField(state, resolution);
      renderFlowField(scene, field, THREE, cell => {
        // Pressure proxy: distance from field center weighted by drift
        const distFromCenter = Math.sqrt(cell.pos[0] ** 2 + cell.pos[1] ** 2) / 7;
        return Math.min(Math.abs(state.drift) * 0.6 + distFromCenter * 0.4, 1);
      });
      scene.render();
    },
  );
}

/**
 * Default force when no external injection is provided.
 * Derived from manifoldGovernor: nudges toward stability without external input.
 */
function defaultForce(state: ManifoldState): ManifoldForce {
  const policy = manifoldGovernor(state);
  return [
    (policy.chaos - policy.stability) * 0.05,
    (policy.chaos - 0.3) * 0.05,
  ];
}
