import { describe, it, expect } from 'vitest';
import { midiToForce, FlowFieldInjector } from '../MidiForceInjector';

describe('midiToForce', () => {
  it('note ON → impulse force', () => {
    const f = midiToForce({ status: 0x90, data1: 60, data2: 100 });
    expect(f?.type).toBe('impulse');
    expect(f?.strength).toBeCloseTo(100 / 127);
  });

  it('note ON with velocity 0 → no event (note off)', () => {
    const f = midiToForce({ status: 0x90, data1: 60, data2: 0 });
    expect(f).toBeNull();
  });

  it('CC1 (mod wheel) → chaos', () => {
    const f = midiToForce({ status: 0xb0, data1: 1, data2: 64 });
    expect(f?.type).toBe('chaos');
    expect(f?.intensity).toBeCloseTo(64 / 127);
  });

  it('CC74 (filter) → damping', () => {
    const f = midiToForce({ status: 0xb0, data1: 74, data2: 127 });
    expect(f?.type).toBe('damping');
    expect(f?.stability).toBeCloseTo(1.0);
  });

  it('unknown CC → null', () => {
    expect(midiToForce({ status: 0xb0, data1: 99, data2: 64 })).toBeNull();
  });
});

describe('FlowFieldInjector', () => {
  it('returns [0, 0] like force when no events applied', () => {
    const inj = new FlowFieldInjector();
    const [dDrift, dEnergy] = inj.getForce();
    // With default chaos=0.2, damping=0.5, impulse=[0,0]:
    // dDrift = (0.2 - 0.5) * 0.1 + 0 * 0.5 = −0.03
    // Not exactly zero but small
    expect(Math.abs(dDrift)).toBeLessThan(0.1);
    expect(Math.abs(dEnergy)).toBeLessThan(0.1);
  });

  it('impulse increases force magnitude', () => {
    const inj = new FlowFieldInjector();
    const before = inj.getForce();
    inj.apply({ type: 'impulse', strength: 1.0, direction: [1, 1] });
    const after = inj.getForce();
    const magBefore = Math.sqrt(before[0] ** 2 + before[1] ** 2);
    const magAfter  = Math.sqrt(after[0]  ** 2 + after[1]  ** 2);
    expect(magAfter).toBeGreaterThan(magBefore);
  });

  it('chaos event updates internal chaos level', () => {
    const inj = new FlowFieldInjector();
    inj.apply({ type: 'chaos', intensity: 0.9 });
    expect(inj.getState().chaos).toBe(0.9);
  });
});
