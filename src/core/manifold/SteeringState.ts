import type { Vec2 } from '../../math/vector';
import { vec2Add } from '../../math/vector';

/**
 * Separates the contribution of each force source for inspection and rendering.
 *
 * Render convention:
 *   performerForce → blue   (what the DJ is doing)
 *   kernelForce    → green  (what the system is correcting)
 *   finalForce     → white  (what actually moves the field)
 *
 * If performer and kernel forces are pointing the same way, the system agrees.
 * If they point opposite ways, the system is fighting the performer.
 */
export interface SteeringState {
  performerForce: Vec2; // raw force from MIDI / audio injection
  kernelForce:    Vec2; // correction from manifoldGovernor policy
  finalForce:     Vec2; // blended = performerForce + kernelForce
}

export function blendSteeringState(performer: Vec2, kernel: Vec2): SteeringState {
  return {
    performerForce: performer,
    kernelForce:    kernel,
    finalForce:     vec2Add(performer, kernel),
  };
}

/** Returns the alignment score ∈ [−1, 1]: 1 = fully aligned, −1 = opposing. */
export function forceAlignment(s: SteeringState): number {
  const pm = Math.sqrt(s.performerForce[0] ** 2 + s.performerForce[1] ** 2);
  const km = Math.sqrt(s.kernelForce[0]    ** 2 + s.kernelForce[1]    ** 2);
  if (pm === 0 || km === 0) return 0;
  const dot = s.performerForce[0] * s.kernelForce[0] + s.performerForce[1] * s.kernelForce[1];
  return dot / (pm * km);
}
