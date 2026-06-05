import type { LiveAttractor } from './MidiAttractorController';

export interface FieldState {
  attractors: LiveAttractor[];
  fieldBias: { x: number; y: number };
  turbulence: number;   // [0, 1]
  stability:  number;   // [0, 1]
  entropy:    number;   // [0, 1]
}

/**
 * Maintains the current state of the steering field and applies
 * attractor mutations from the MIDI controller.
 */
export class SteeringFieldEngine {
  private state: FieldState = {
    attractors: [],
    fieldBias:  { x: 0.1, y: 0.5 }, // center of the raw projection range
    turbulence: 0,
    stability:  1,
    entropy:    0,
  };

  applyAttractors(attractors: LiveAttractor[]): FieldState {
    this.state.attractors = attractors;
    this.state.fieldBias  = this.computeGlobalBias(attractors);
    this.state.turbulence = this.computeTurbulence(attractors);
    this.state.stability  = Math.max(0, 1 - this.state.turbulence);
    this.state.entropy    = this.computeEntropy(attractors);
    return { ...this.state };
  }

  getState(): Readonly<FieldState> {
    return this.state;
  }

  private computeGlobalBias(attractors: LiveAttractor[]): { x: number; y: number } {
    if (attractors.length === 0) return { x: 0.1, y: 0.5 };
    const totalStrength = attractors.reduce((s, a) => s + a.strength, 0) || 1;
    return {
      x: attractors.reduce((s, a) => s + a.x * a.strength, 0) / totalStrength,
      y: attractors.reduce((s, a) => s + a.y * a.strength, 0) / totalStrength,
    };
  }

  private computeTurbulence(attractors: LiveAttractor[]): number {
    if (attractors.length < 2) return 0;
    // turbulence = spread of attractor positions weighted by strength
    const bias = this.computeGlobalBias(attractors);
    const totalStrength = attractors.reduce((s, a) => s + a.strength, 0) || 1;
    const spread = attractors.reduce((s, a) => {
      const dx = a.x - bias.x;
      const dy = a.y - bias.y;
      return s + Math.sqrt(dx * dx + dy * dy) * a.strength;
    }, 0) / totalStrength;
    return Math.min(1, spread * 2);
  }

  private computeEntropy(attractors: LiveAttractor[]): number {
    if (attractors.length === 0) return 0;
    const burnerCount = attractors.filter(a => a.type === 'burner').length;
    return burnerCount / attractors.length;
  }
}
