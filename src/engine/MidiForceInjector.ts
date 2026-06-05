import type { ManifoldForce } from '../core/manifold/ManifoldRuntime';

export type MidiForceType = 'impulse' | 'chaos' | 'damping';

export interface MidiForceEvent {
  type:       MidiForceType;
  strength?:  number;
  intensity?: number;
  stability?: number;
  direction?: [number, number];
}

/**
 * Translates raw MIDI messages into force events for the ManifoldRuntime.
 *
 * Semantic map:
 *   Note ON         → impulse force (pitch → direction, velocity → strength)
 *   CC 1 (mod wheel)→ chaos intensity
 *   CC 74 (filter)  → stability / damping
 */
export function midiToForce(msg: { status: number; data1: number; data2: number }): MidiForceEvent | null {
  const { status, data1, data2 } = msg;
  const msgType = status & 0xf0;

  if (msgType === 0x90 && data2 > 0) {
    // Note ON — convert pitch class to direction, velocity to strength
    const velocity = data2 / 127;
    return {
      type:      'impulse',
      strength:  velocity,
      direction: [(data1 % 12) / 11 - 0.5, velocity - 0.5],
    };
  }

  if (msgType === 0xb0) {
    if (data1 === 1)  return { type: 'chaos',   intensity: data2 / 127 };
    if (data1 === 74) return { type: 'damping',  stability: data2 / 127 };
  }

  return null;
}

/**
 * Accumulates MIDI force events and exposes a ManifoldForce vector for the runtime step.
 *
 * The injector is the injection point between MIDIInputEngine and ManifoldRuntime.
 * Update it each tick by calling `apply()` with fresh MIDI events, then pass
 * `injector.getForce(state)` as the `getForce` callback in `bindRuntimeToScene`.
 */
export class FlowFieldInjector {
  private chaos:   number           = 0.2;
  private damping: number           = 0.5;
  private impulse: [number, number] = [0, 0];

  /**
   * Apply a MIDI force event.
   *
   * @param event    the force event to apply
   * @param smoothed when true, chaos and damping use lerp(α=0.05) to prevent
   *                 feedback runaway. Pass true for feedback-driven calls,
   *                 false (default) for direct MIDI input.
   */
  apply(event: MidiForceEvent | null, smoothed = false): void {
    if (!event) return;
    const alpha = smoothed ? 0.05 : 1.0;

    if (event.type === 'chaos' && event.intensity !== undefined) {
      this.chaos   = lerp(this.chaos,   event.intensity,   alpha);
    }
    if (event.type === 'damping' && event.stability !== undefined) {
      this.damping = lerp(this.damping, event.stability,   alpha);
    }
    if (event.type === 'impulse' && event.direction && event.strength !== undefined) {
      const s = event.strength;
      this.impulse = [event.direction[0] * s, event.direction[1] * s];
    }
  }

  /** Returns a ManifoldForce [dDrift, dEnergy] for the current tick. */
  getForce(): ManifoldForce {
    const scaledChaos = (this.chaos - 0.5) * 0.1;
    const dDrift      = scaledChaos    + this.impulse[0] * (1 - this.damping);
    const dEnergy     = this.impulse[1] * this.damping   + (this.chaos - 0.2) * 0.05;
    return [dDrift, dEnergy];
  }

  getState(): Readonly<{ chaos: number; damping: number; impulse: readonly [number, number] }> {
    return { chaos: this.chaos, damping: this.damping, impulse: this.impulse };
  }
}

function lerp(a: number, b: number, alpha: number): number {
  if (alpha >= 1) return b;
  return a + (b - a) * alpha;
}
