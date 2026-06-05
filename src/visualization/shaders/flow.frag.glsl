precision highp float;

uniform float u_time;
uniform vec2  u_resolution;
uniform vec4  u_state;       // .x=drift  .y=energy  .z=stability  .w=cumulative_drift
uniform float u_turbulence;
uniform float u_damping;

varying vec2 vUv;

// ─── Attractor force field ────────────────────────────────────────────────────
struct Attractor {
  vec2  center;
  float strength;
};

vec2 attractorForce(vec2 pos, Attractor a) {
  vec2  delta   = a.center - pos;
  float distSq  = dot(delta, delta) + 1e-4;
  float falloff = a.strength / distSq;
  return delta * falloff;
}

// ─── Pressure → color ramp ────────────────────────────────────────────────────
vec3 pressureColor(float t) {
  t = clamp(t, 0.0, 1.0);
  if (t < 0.33) return mix(vec3(0.18, 0.40, 0.85), vec3(0.10, 0.72, 0.32), t / 0.33);
  if (t < 0.67) return mix(vec3(0.10, 0.72, 0.32), vec3(0.95, 0.85, 0.10), (t - 0.33) / 0.34);
  return           mix(vec3(0.95, 0.85, 0.10), vec3(0.90, 0.12, 0.12), (t - 0.67) / 0.33);
}

void main() {
  vec2 uv = vUv; // [0, 1] × [0, 1]

  // ── Two canonical attractors (kernel-driven positions are injected via uniforms) ──
  Attractor pocket;
  pocket.center   = vec2(0.65, 0.70 + u_state.y * 0.05);
  pocket.strength = 0.8 + u_state.z * 0.4;

  Attractor burner;
  burner.center   = vec2(0.25, 0.60 + u_state.x * 0.1);
  burner.strength = 0.5 * u_state.y;

  // ── Field force accumulation ──────────────────────────────────────────────
  vec2 force = attractorForce(uv, pocket) + attractorForce(uv, burner);
  float mag  = length(force);

  // ── Turbulence overlay ────────────────────────────────────────────────────
  float noise = sin(uv.x * 14.0 + u_time * 1.5 + u_state.x * 3.0)
              * cos(uv.y * 11.0 + u_time * 1.2 + u_state.w * 2.0)
              * u_turbulence * 0.25;

  float fieldIntensity = clamp(mag * 2.0 + noise, 0.0, 1.0);

  // ── Direction visualization (flow lines) ─────────────────────────────────
  vec2  dir     = mag > 0.0 ? force / mag : vec2(0.0);
  float flowVis = sin((uv.x * dir.y - uv.y * dir.x) * 20.0 + u_time * 0.8) * 0.5 + 0.5;

  // ── Pressure color ────────────────────────────────────────────────────────
  float pressure = clamp(u_state.w + (1.0 - u_state.z) * 0.3, 0.0, 1.0);
  vec3  color    = pressureColor(pressure);

  // ── Compose ──────────────────────────────────────────────────────────────
  color = mix(color * 0.3, color, fieldIntensity);
  color += vec3(flowVis * 0.08 * u_damping);

  // ── Damping zone — intentional transparency when λ → 0 ───────────────────
  float alpha = 0.6 + fieldIntensity * 0.4;
  alpha *= mix(0.3, 1.0, u_damping); // damp zones render semi-transparent

  gl_FragColor = vec4(color, alpha);
}
