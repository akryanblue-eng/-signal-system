// Requires: three (npm install three @types/three)
import type * as THREE_TYPES from 'three';

// GLSL inlined to avoid bundler configuration requirements at this stage.
// When a bundler with glsl-loader is configured, replace with:
//   import vert from './shaders/flow.vert.glsl?raw';
//   import frag from './shaders/flow.frag.glsl?raw';
const VERT = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const FRAG = /* glsl */ `
precision highp float;
uniform float u_time;
uniform vec2  u_resolution;
uniform vec4  u_state;
uniform float u_turbulence;
uniform float u_damping;
varying vec2  vUv;

vec3 pressureColor(float t) {
  t = clamp(t, 0.0, 1.0);
  if (t < 0.33) return mix(vec3(0.18,0.40,0.85), vec3(0.10,0.72,0.32), t / 0.33);
  if (t < 0.67) return mix(vec3(0.10,0.72,0.32), vec3(0.95,0.85,0.10), (t-0.33)/0.34);
  return           mix(vec3(0.95,0.85,0.10), vec3(0.90,0.12,0.12), (t-0.67)/0.33);
}

void main() {
  vec2  uv      = vUv;
  float drift   = u_state.x;
  float energy  = u_state.y;
  float stab    = u_state.z;
  float cumDrift = u_state.w;

  float flowX   = sin(uv.x * 10.0 + u_time + drift * 3.0);
  float flowY   = cos(uv.y *  8.0 + u_time + cumDrift * 2.0);
  float mag     = abs(flowX * flowY) * energy;
  float pressure = clamp(cumDrift + (1.0 - stab) * 0.3 + u_turbulence * 0.2, 0.0, 1.0);

  vec3  col   = pressureColor(pressure);
  col  = mix(col * 0.3, col, smoothstep(0.0, 1.0, mag));
  float alpha = mix(0.3, 1.0, u_damping) * (0.6 + mag * 0.4);
  gl_FragColor = vec4(col, alpha);
}`;

export interface FlowFieldUniforms {
  u_time:       { value: number };
  u_resolution: { value: { x: number; y: number } };
  u_state:      { value: { x: number; y: number; z: number; w: number } };
  u_turbulence: { value: number };
  u_damping:    { value: number };
}

/**
 * Wraps the flow field shader as a Three.js ShaderMaterial.
 *
 * Import THREE dynamically so this module can be imported without
 * Three.js being present at parse time (useful for test environments).
 */
export class FlowFieldMaterial {
  public uniforms: FlowFieldUniforms;
  public shader!: THREE_TYPES.ShaderMaterial;

  constructor(THREE: typeof THREE_TYPES) {
    this.uniforms = {
      u_time:       { value: 0 },
      u_resolution: { value: { x: 0, y: 0 } },
      u_state:      { value: { x: 0, y: 0.5, z: 0.7, w: 0 } },
      u_turbulence: { value: 0 },
      u_damping:    { value: 1 },
    };

    this.shader = new THREE.ShaderMaterial({
      vertexShader:   VERT,
      fragmentShader: FRAG,
      uniforms:       this.uniforms as unknown as Record<string, THREE_TYPES.IUniform>,
      transparent:    true,
    });
  }

  update(data: {
    state?:      { drift: number; energy: number; stability: number; cumulative_drift: number };
    turbulence?: number;
    damping?:    number;
  }): void {
    if (data.state) {
      this.uniforms.u_state.value = {
        x: data.state.drift,
        y: data.state.energy,
        z: data.state.stability,
        w: data.state.cumulative_drift,
      };
    }
    if (data.turbulence !== undefined) this.uniforms.u_turbulence.value = data.turbulence;
    if (data.damping    !== undefined) this.uniforms.u_damping.value    = data.damping;
  }

  tick(dt = 0.016): void {
    this.uniforms.u_time.value += dt;
  }
}
