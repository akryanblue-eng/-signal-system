import { describe, it, expect } from 'vitest';
import { pressureToColor } from '../colorMap';

describe('pressureToColor', () => {
  it('returns blue at zero pressure', () => {
    expect(pressureToColor(0)).toBe('hsl(220, 80%, 55%)');
  });

  it('returns red at ceiling pressure', () => {
    expect(pressureToColor(1)).toBe('hsl(0, 80%, 50%)');
  });

  it('clamps values above ceiling to red', () => {
    expect(pressureToColor(999)).toBe(pressureToColor(1));
  });

  it('returns a valid hsl() string for all sample values', () => {
    const hslPattern = /^hsl\(\d+, \d+%, \d+%\)$/;
    for (const t of [0, 0.1, 0.25, 0.33, 0.5, 0.67, 0.75, 1.0]) {
      expect(pressureToColor(t)).toMatch(hslPattern);
    }
  });

  it('transitions smoothly — midpoint blends between stops', () => {
    // At t=0.33 the output should equal the green stop exactly
    expect(pressureToColor(0.33)).toBe('hsl(140, 70%, 45%)');
    // At t=0.67 the output should equal the yellow stop exactly
    expect(pressureToColor(0.67)).toBe('hsl(50, 90%, 50%)');
  });

  it('respects a custom ceiling parameter', () => {
    // With ceiling=2, pressure=1 should map to ~midpoint (green/yellow region)
    const half = pressureToColor(1, 2);
    expect(half).not.toBe(pressureToColor(1, 1));
    expect(half).toMatch(/^hsl\(\d+, \d+%, \d+%\)$/);
  });
});
