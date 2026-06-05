// Requires: three (npm install three @types/three)
import type * as THREE_TYPES from 'three';
import { FlowFieldMaterial } from './FlowFieldMaterial';
import type { SceneUniforms } from '../engine/Bridge';

/**
 * Orchestrates the Three.js scene for the flow field renderer.
 *
 * Architecture:
 *   CPU: PerformanceKernel → FlowKernelBridge → updateUniforms()
 *   GPU: PlaneGeometry + ShaderMaterial → WebGLRenderer
 *
 * Usage:
 *   const scene = new FlowFieldScene(container, THREE);
 *   scene.updateUniforms({ attractors: [...], state: {...} });
 *   // scene.animate() is called automatically in the constructor
 */
export class FlowFieldScene {
  private scene!:     THREE_TYPES.Scene;
  private camera!:    THREE_TYPES.PerspectiveCamera;
  private renderer!:  THREE_TYPES.WebGLRenderer;
  private material!:  FlowFieldMaterial;
  private animating = false;

  constructor(container: HTMLElement, THREE: typeof THREE_TYPES) {
    this.scene    = new THREE.Scene();
    this.camera   = new THREE.PerspectiveCamera(60, container.clientWidth / container.clientHeight, 0.1, 1000);
    this.camera.position.z = 1.5;

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(this.renderer.domElement);

    this.material = new FlowFieldMaterial(THREE);
    this.material.uniforms.u_resolution.value = {
      x: container.clientWidth,
      y: container.clientHeight,
    };

    const geometry = new THREE.PlaneGeometry(2, 2, 128, 128);
    const mesh     = new THREE.Mesh(geometry, this.material.shader);
    this.scene.add(mesh);

    window.addEventListener('resize', () => this.onResize(container, THREE));
    this.startAnimation();
  }

  /** Push kernel output into shader uniforms. */
  updateUniforms(data: SceneUniforms): void {
    const s = data.state;
    this.material.update({
      state: {
        drift:            s.drift,
        energy:           s.energy,
        stability:        s.stability,
        cumulative_drift: s.cumulative_drift,
      },
    });
  }

  /** Update turbulence and damping from the steering field. */
  updateFieldDynamics(turbulence: number, damping: number): void {
    this.material.update({ turbulence, damping });
  }

  dispose(): void {
    this.animating = false;
    this.renderer.dispose();
  }

  private startAnimation(): void {
    this.animating = true;
    const loop = (): void => {
      if (!this.animating) return;
      this.material.tick();
      this.renderer.render(this.scene, this.camera);
      requestAnimationFrame(loop);
    };
    loop();
  }

  private onResize(container: HTMLElement, THREE: typeof THREE_TYPES): void {
    this.camera.aspect = container.clientWidth / container.clientHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.material.uniforms.u_resolution.value = {
      x: container.clientWidth,
      y: container.clientHeight,
    };
  }
}
