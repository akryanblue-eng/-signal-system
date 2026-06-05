export type Vec2 = readonly [number, number];

export function vec2Add(a: Vec2, b: Vec2): Vec2 {
  return [a[0] + b[0], a[1] + b[1]];
}

export function vec2Scale(v: Vec2, s: number): Vec2 {
  return [v[0] * s, v[1] * s];
}

export function vec2Magnitude(v: Vec2): number {
  return Math.sqrt(v[0] ** 2 + v[1] ** 2);
}

export function vec2Normalize(v: Vec2): Vec2 {
  const mag = vec2Magnitude(v);
  return mag === 0 ? [0, 0] : [v[0] / mag, v[1] / mag];
}

export function vec2Dot(a: Vec2, b: Vec2): number {
  return a[0] * b[0] + a[1] * b[1];
}
