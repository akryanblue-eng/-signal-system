import type { MIDIEvent } from './MIDIInputEngine';

export type AttractorType = 'pocket' | 'burner' | 'reset';

export interface LiveAttractor {
  id: string;
  x: number;         // canvas-space position [−0.4, 0.6]
  y: number;         // canvas-space position [0.0,  1.0]
  strength: number;  // [0, 1]
  radius: number;    // influence radius in canvas units
  type: AttractorType;
  decay: number;     // multiplied each tick — 1.0 = persist, 0.0 = instant remove
}

const CHANNEL_TO_TYPE: Record<number, AttractorType> = {
  1: 'pocket',
  2: 'burner',
  3: 'reset',
};

/**
 * Maps MIDI gestures to live attractor mutations.
 *
 * Semantic mapping:
 *   Note pitch   → attractor X position (chromatic class = 0–11 across X axis)
 *   Octave       → attractor Y position
 *   Velocity     → strength + radius
 *   Channel      → attractor type (pocket / burner / reset)
 *   Note off     → slow fade (decay = 0.92), not hard delete
 */
export class MidiAttractorController {
  private attractors: Map<number, LiveAttractor> = new Map();

  processEvents(events: MIDIEvent[]): void {
    for (const e of events) {
      if (e.type === 'note_on')  this.onNoteOn(e.note, e.velocity, e.channel);
      if (e.type === 'note_off') this.onNoteOff(e.note);
    }
  }

  private onNoteOn(note: number, velocity: number, channel: number): void {
    // Chromatic position (0–11) → X axis [−0.4, 0.6]
    const xNorm = (note % 12) / 11;
    const x = -0.4 + xNorm * 1.0;

    // Octave (0–9) → Y axis [0, 1]
    const y = Math.min(Math.floor(note / 12) / 9, 1.0);

    const type = CHANNEL_TO_TYPE[channel] ?? 'pocket';
    const existing = this.attractors.get(note);

    if (existing) {
      // Morph in place — live steering
      existing.x        = x;
      existing.y        = y;
      existing.strength = velocity;
      existing.radius   = 0.1 + velocity * 0.15;
      existing.decay    = 1.0;
    } else {
      this.attractors.set(note, {
        id:       `midi_${note}`,
        x, y,
        strength: velocity,
        radius:   0.1 + velocity * 0.15,
        type,
        decay:    1.0,
      });
    }
  }

  private onNoteOff(note: number): void {
    const a = this.attractors.get(note);
    if (a) a.decay = 0.92; // slow fade rather than hard delete
  }

  /** Apply decay to all attractors and remove expired ones. */
  tick(): void {
    for (const [note, a] of this.attractors) {
      a.strength *= a.decay;
      if (a.strength < 0.01) this.attractors.delete(note);
    }
  }

  getAttractors(): LiveAttractor[] {
    return Array.from(this.attractors.values());
  }
}
