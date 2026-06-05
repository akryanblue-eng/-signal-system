import { describe, it, expect } from 'vitest';
import { SnapshotRecorder } from '../RuntimeSnapshot';
import type { ManifoldState } from '../ManifoldRuntime';
import type { FieldFeedbackSignal } from '../../../engine/FieldFeedback';

const state: ManifoldState = { drift: 0.1, energy: 0.8, coherence: 0.9 };

const feedback: FieldFeedbackSignal = {
  driftPressure:    0.1,
  attractorPull:    0.7,
  timingOffset:     2.5,
  energyGradient:   0.05,
  correctionVector: [-0.1, 0.06],
};

describe('SnapshotRecorder', () => {
  it('records and returns frames in order', () => {
    const rec = new SnapshotRecorder(10);
    const s1  = rec.record(state, feedback, 0.2);
    const s2  = rec.record({ ...state, drift: 0.5 }, feedback, 0.3);
    expect(s1.frame).toBe(0);
    expect(s2.frame).toBe(1);
    expect(rec.all()).toHaveLength(2);
  });

  it('evicts oldest when full', () => {
    const rec = new SnapshotRecorder(3);
    for (let i = 0; i < 5; i++) rec.record(state, feedback, 0.2);
    expect(rec.all()).toHaveLength(3);
    expect(rec.all()[0]?.frame).toBe(2); // frames 0,1 evicted
  });

  it('latest() returns the most recent snapshot', () => {
    const rec = new SnapshotRecorder(10);
    rec.record(state, feedback, 0.1);
    rec.record({ ...state, drift: 0.9 }, feedback, 0.8);
    expect(rec.latest()?.chaos).toBe(0.8);
  });

  it('isRunaway detects persistent high drift', () => {
    const rec = new SnapshotRecorder(20);
    const highDrift: ManifoldState = { drift: 0.9, energy: 0.5, coherence: 0.1 };
    for (let i = 0; i < 10; i++) rec.record(highDrift, feedback, 0.5);
    expect(rec.isRunaway(0.85, 10)).toBe(true);
  });

  it('isRunaway returns false for short spikes', () => {
    const rec = new SnapshotRecorder(20);
    const highDrift: ManifoldState = { drift: 0.9, energy: 0.5, coherence: 0.1 };
    for (let i = 0; i < 5; i++) rec.record(highDrift, feedback, 0.5);
    expect(rec.isRunaway(0.85, 10)).toBe(false);
  });

  it('clear() resets frame count', () => {
    const rec = new SnapshotRecorder(10);
    rec.record(state, feedback, 0.2);
    rec.clear();
    expect(rec.all()).toHaveLength(0);
    const fresh = rec.record(state, feedback, 0.2);
    expect(fresh.frame).toBe(0);
  });
});
