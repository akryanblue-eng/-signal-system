import type { AudioFeatures } from './AudioInputEngine';
import type { MIDIState } from './MIDIInputEngine';
import type { LiveAttractor } from './MidiAttractorController';

export interface FlowMapping {
  attractors: LiveAttractor[];
  fieldDynamics: {
    turbulence: number;  // [0, 1]
    damping:    number;  // [0, 1]
    flowBias:   number;  // [0, 1]
  };
}

/**
 * Translates real-time audio + MIDI signals into flow field parameters.
 *
 * Audio:   bass → low attractor pull,  treble → turbulence,  energy → field intensity
 * MIDI:    velocity → force magnitude,  modulation → field bias
 */
export class SignalToFlowMapper {
  map(audio: AudioFeatures, midi: MIDIState): FlowMapping {
    return {
      attractors: [
        {
          id:       'audio_bass',
          x:        audio.bass   * 0.4 - 0.2, // map bass to left side of X range
          y:        audio.energy,
          strength: audio.energy * 1.4,
          radius:   0.2 + audio.bass * 0.1,
          type:     'pocket',
          decay:    1.0,
        },
        {
          id:       'midi_velocity',
          x:        midi.velocity  * 0.4 + 0.1, // map velocity to right side
          y:        midi.modulation > 0 ? midi.modulation : audio.centroid,
          strength: midi.velocity  * 1.2,
          radius:   0.15,
          type:     midi.modulation > 0.7 ? 'burner' : 'pocket',
          decay:    1.0,
        },
      ],
      fieldDynamics: {
        turbulence: audio.treble,
        damping:    Math.max(0.2, 1 - audio.energy * 0.5),
        flowBias:   midi.modulation,
      },
    };
  }
}
