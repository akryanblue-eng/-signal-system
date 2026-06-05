import { describe, it, expect } from 'vitest';
import {
  IntentMemoryStore,
  normalizeIntentKey,
  embedActions,
  vectorSimilarity,
  mergeActions,
} from '../IntentMemory';
import { DEFAULT_PERFORMANCE_STATE } from '../../PerformanceState';
import type { PerformanceAction } from '../PerformanceAction';

const s = DEFAULT_PERFORMANCE_STATE;
const acts: PerformanceAction[] = [
  { type: 'CHAOS_SPIKE', amount: 0.2 },
  { type: 'GROOVE_LOCK' },
];

describe('normalizeIntentKey', () => {
  it('maps energy keywords to energy_control', () => {
    expect(normalizeIntentKey('lift the energy')).toBe('energy_control');
  });
  it('maps chaos keywords to entropy_control', () => {
    expect(normalizeIntentKey('add some glitch chaos')).toBe('entropy_control');
  });
  it('maps calm to stability_control', () => {
    expect(normalizeIntentKey('calm it down')).toBe('stability_control');
  });
  it('maps groove to rhythm_control', () => {
    expect(normalizeIntentKey('tighten the groove')).toBe('rhythm_control');
  });
  it('falls back to general_control for unknown phrases', () => {
    expect(normalizeIntentKey('do the thing')).toBe('general_control');
  });
});

describe('IntentMemoryStore', () => {
  it('record() stores memory with correct embeddingKey and delta', () => {
    const store = new IntentMemoryStore();
    const after = { ...s, chaos: s.chaos + 0.2 };
    const mem = store.record('add chaos', acts, s, after);
    expect(mem.embeddingKey).toBe('entropy_control');
    expect(mem.delta.chaos).toBeCloseTo(0.2);
    expect(store.size).toBe(1);
  });

  it('query() returns only memories matching the key', () => {
    const store = new IntentMemoryStore();
    store.record('energy up',   acts, s, s);
    store.record('chaos spike', acts, s, s);
    store.record('energy kick', acts, s, s);
    expect(store.query('energy_control')).toHaveLength(2);
    expect(store.query('entropy_control')).toHaveLength(1);
  });

  it('recent(n) returns the last n memories in insertion order', () => {
    const store = new IntentMemoryStore();
    for (let i = 0; i < 5; i++) store.record(`intent ${i}`, acts, s, s);
    const last3 = store.recent(3);
    expect(last3).toHaveLength(3);
    expect(last3.at(-1)?.intent).toBe('intent 4');
  });

  it('getBestPatterns() returns rated memories sorted by rating desc', () => {
    const store = new IntentMemoryStore();
    store.record('energy', acts, s, s, 0.3);
    store.record('energy', acts, s, s, 0.9);
    store.record('energy', acts, s, s, 0.6);
    const best = store.getBestPatterns('energy_control');
    expect(best[0]?.rating).toBe(0.9);
    expect(best[1]?.rating).toBe(0.6);
  });

  it('getBestPatterns() excludes unrated memories', () => {
    const store = new IntentMemoryStore();
    store.record('energy', acts, s, s);         // no rating
    store.record('energy', acts, s, s, 0.8);    // rated
    expect(store.getBestPatterns('energy_control')).toHaveLength(1);
  });

  it('rateLast() updates the most recent matching memory', () => {
    const store = new IntentMemoryStore();
    store.record('groove lock', acts, s, s);
    store.rateLast('rhythm_control', 0.75);
    expect(store.query('rhythm_control')[0]?.rating).toBe(0.75);
  });

  it('clear() empties the store and resets size', () => {
    const store = new IntentMemoryStore();
    store.record('test', acts, s, s);
    store.clear();
    expect(store.size).toBe(0);
  });
});

describe('embedActions', () => {
  it('returns [tension, chaos, groove] feature vector', () => {
    const vec = embedActions([
      { type: 'TENSION_BUILD', amount: 0.5 },
      { type: 'CHAOS_SPIKE',   amount: 0.4 },
      { type: 'GROOVE_LOCK' },
    ]);
    expect(vec[0]).toBeCloseTo(0.5); // tension
    expect(vec[1]).toBeCloseTo(0.4); // chaos
    expect(vec[2]).toBeCloseTo(0.2); // groove
  });

  it('caps values at 1 when actions sum over 1', () => {
    const vec = embedActions([
      { type: 'CHAOS_SPIKE', amount: 0.8 },
      { type: 'CHAOS_SPIKE', amount: 0.8 },
    ]);
    expect(vec[1]).toBeLessThanOrEqual(1);
  });
});

describe('vectorSimilarity', () => {
  it('identical vectors return 1', () => {
    expect(vectorSimilarity([0.5, 0.3, 0.2], [0.5, 0.3, 0.2])).toBeCloseTo(1);
  });
  it('distant vectors return < 1', () => {
    expect(vectorSimilarity([0, 0, 0], [1, 1, 1])).toBeLessThan(1);
  });
});

describe('mergeActions', () => {
  it('learned action takes precedence over base for same type', () => {
    const base:    PerformanceAction[] = [{ type: 'CHAOS_SPIKE', amount: 0.1 }];
    const learned: PerformanceAction[] = [{ type: 'CHAOS_SPIKE', amount: 0.5 }];
    const merged = mergeActions(base, learned);
    expect(merged).toHaveLength(1);
    const spike = merged.find(a => a.type === 'CHAOS_SPIKE');
    expect((spike as Extract<PerformanceAction, { type: 'CHAOS_SPIKE' }>).amount).toBe(0.5);
  });

  it('base actions with unique types are preserved', () => {
    const base:    PerformanceAction[] = [{ type: 'ENERGY_PULSE', amount: 0.2 }];
    const learned: PerformanceAction[] = [{ type: 'GROOVE_LOCK' }];
    const merged = mergeActions(base, learned);
    const types = merged.map(a => a.type);
    expect(types).toContain('ENERGY_PULSE');
    expect(types).toContain('GROOVE_LOCK');
  });
});
