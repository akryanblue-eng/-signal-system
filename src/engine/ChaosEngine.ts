import type { Vec2 } from '../math/vector';
import { vec2Normalize } from '../math/vector';

export type ChaosEventType =
  | 'tension'    // orbital rotation around center — creates orbiting
  | 'release'    // centripetal collapse inward — pulls toward attractor
  | 'fracture'   // radial repulsion outward — splits the field
  | 'spiral'     // orbital + outward — expanding vortex
  | 'shockwave'; // strong radial pulse — pushes everything outward

export interface ChaosEvent {
  id:          string;
  type:        ChaosEventType;
  intensity:   number; // [0, 1]
  durationMs:  number;
  radius:      number; // influence radius in canvas units
  center:      Vec2;
  recoveryCurve: number; // [0.88, 1.0] — decay per frame; lower = faster decay
}

export interface ActiveChaosEvent {
  event:       ChaosEvent;
  elapsedMs:   number;
  intensity:   number; // current (decaying) intensity
}

/**
 * Computes the instantaneous force exerted by a chaos event at a canvas position.
 *
 * Force types:
 *   tension    → tangential ([-dy, dx]) — orbit around center
 *   release    → centripetal (toward center) — collapse to attractor
 *   fracture   → radial outward (away from center)
 *   spiral     → 70% tangential + 30% radial outward — expanding vortex
 *   shockwave  → strong radial outward pulse (exponential peak then decay)
 */
export function chaosForce(position: Vec2, event: ActiveChaosEvent): Vec2 {
  if (event.intensity === 0) return [0, 0];

  const dx = position[0] - event.event.center[0];
  const dy = position[1] - event.event.center[1];
  const dist = Math.sqrt(dx * dx + dy * dy) + 1e-6;

  const falloff   = event.intensity * Math.exp(-dist / event.event.radius);
  const radialDir = vec2Normalize([dx / dist, dy / dist] as const);
  const tangent   = vec2Normalize([-dy / dist, dx / dist] as const);

  switch (event.event.type) {
    case 'tension':
      return [tangent[0] * falloff, tangent[1] * falloff];

    case 'release':
      return [-radialDir[0] * falloff, -radialDir[1] * falloff]; // inward

    case 'fracture':
      return [radialDir[0] * falloff, radialDir[1] * falloff]; // outward

    case 'spiral': {
      const t = 0.7;
      const r = 0.3;
      return [
        (tangent[0] * t + radialDir[0] * r) * falloff,
        (tangent[1] * t + radialDir[1] * r) * falloff,
      ];
    }

    case 'shockwave': {
      // Single radial pulse that decays quickly at the wavefront
      const wavefrontDist = event.event.radius * (event.elapsedMs / event.event.durationMs);
      const wavefalloff   = Math.exp(-Math.abs(dist - wavefrontDist) / 0.5) * event.intensity;
      return [radialDir[0] * wavefalloff, radialDir[1] * wavefalloff];
    }
  }
}

/**
 * Manages active chaos events and accumulates their forces.
 * Inject events via `fire()`; call `tick(dt)` each frame to advance.
 */
export class ChaosEngine {
  private active: Map<string, ActiveChaosEvent> = new Map();

  fire(event: ChaosEvent): void {
    this.active.set(event.id, {
      event,
      elapsedMs: 0,
      intensity: Math.min(1, event.intensity),
    });
  }

  /** Advance all active events by dtMs. Returns ids of events that expired. */
  tick(dtMs: number): string[] {
    const expired: string[] = [];

    for (const [id, active] of this.active) {
      active.elapsedMs += dtMs;
      active.intensity *= active.event.recoveryCurve;

      if (active.elapsedMs >= active.event.durationMs || active.intensity < 0.005) {
        expired.push(id);
      }
    }

    for (const id of expired) this.active.delete(id);
    return expired;
  }

  /**
   * Accumulate all active chaos forces at a given canvas position.
   * Returns [0, 0] when no events are active.
   */
  sample(position: Vec2): Vec2 {
    let fx = 0;
    let fy = 0;

    for (const active of this.active.values()) {
      const [cfx, cfy] = chaosForce(position, active);
      fx += cfx;
      fy += cfy;
    }

    return [fx, fy];
  }

  activeCount(): number {
    return this.active.size;
  }

  isActive(): boolean {
    return this.active.size > 0;
  }

  getActive(): ReadonlyMap<string, ActiveChaosEvent> {
    return this.active;
  }
}
