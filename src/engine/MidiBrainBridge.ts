import type { FlowFieldInjector } from './MidiForceInjector';
import { midiToForce } from './MidiForceInjector';

/**
 * Listens to WebMIDI inputs and routes messages through midiToForce()
 * directly into a FlowFieldInjector.
 *
 * This is the "performer brain port" — raw MIDI events become physics forces.
 */
export class MidiBrainBridge {
  private injector: FlowFieldInjector;

  constructor(injector: FlowFieldInjector) {
    this.injector = injector;
  }

  async init(): Promise<void> {
    const access = await navigator.requestMIDIAccess();
    access.inputs.forEach(input => {
      input.onmidimessage = msg => {
        if (!msg.data) return;
        const [s, d1, d2] = msg.data;
        const force = midiToForce({
          status: s ?? 0,
          data1:  d1 ?? 0,
          data2:  d2 ?? 0,
        });
        if (force) this.injector.apply(force);
      };
    });
  }
}
