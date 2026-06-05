export interface MIDIState {
  velocity:    number;         // [0, 1] — last note velocity
  note:        number;         // 0–127
  modulation:  number;         // [0, 1] — CC1 (mod wheel)
  pitchBend:   number;         // [−1, 1]
  activeNotes: Set<number>;
}

export type MIDIEvent =
  | { type: 'note_on';  note: number; velocity: number; channel: number }
  | { type: 'note_off'; note: number; channel: number }
  | { type: 'cc';       cc: number;   value: number;    channel: number }
  | { type: 'pitch_bend'; value: number; channel: number };

/**
 * Listens to all MIDI inputs and maintains a live state snapshot.
 */
export class MIDIInputEngine {
  public state: MIDIState = {
    velocity:   0,
    note:       0,
    modulation: 0,
    pitchBend:  0,
    activeNotes: new Set(),
  };

  public readonly eventLog: MIDIEvent[] = [];
  private maxLog = 64;

  async init(): Promise<void> {
    const access = await navigator.requestMIDIAccess();
    access.inputs.forEach(input => {
      input.onmidimessage = msg => { if (msg.data) this.handle(msg.data); };
    });
  }

  private handle(data: Uint8Array): void {
    const status   = data[0] ?? 0;
    const param1   = data[1] ?? 0;
    const param2   = data[2] ?? 0;
    const channel  = (status & 0x0f) + 1;
    const msgType  = status & 0xf0;

    if (msgType === 0x90 && param2 > 0) {
      // Note ON
      this.state.activeNotes.add(param1);
      this.state.note     = param1;
      this.state.velocity = param2 / 127;
      this.pushEvent({ type: 'note_on', note: param1, velocity: param2 / 127, channel });
    } else if (msgType === 0x80 || (msgType === 0x90 && param2 === 0)) {
      // Note OFF
      this.state.activeNotes.delete(param1);
      this.pushEvent({ type: 'note_off', note: param1, channel });
    } else if (msgType === 0xb0) {
      // Control Change
      if (param1 === 1) {
        this.state.modulation = param2 / 127;
      }
      this.pushEvent({ type: 'cc', cc: param1, value: param2 / 127, channel });
    } else if (msgType === 0xe0) {
      // Pitch Bend — 14-bit value centered at 8192
      const bend = ((param2 << 7) | param1) - 8192;
      this.state.pitchBend = bend / 8192;
      this.pushEvent({ type: 'pitch_bend', value: bend / 8192, channel });
    }
  }

  /** Flush queued events (call once per tick). */
  drainEvents(): MIDIEvent[] {
    return this.eventLog.splice(0, this.eventLog.length);
  }

  private pushEvent(e: MIDIEvent): void {
    if (this.eventLog.length >= this.maxLog) this.eventLog.shift();
    this.eventLog.push(e);
  }
}
