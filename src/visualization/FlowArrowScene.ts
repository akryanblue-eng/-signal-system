// Requires: three (npm install three @types/three)
import type * as THREE_TYPES from 'three';

/**
 * Three.js scene that renders the flow field as ArrowHelper vectors.
 *
 * This scene is a pure visualization layer — it owns no physics state.
 * All updates flow in from ManifoldRuntime via bindRuntimeToScene().
 */
export class FlowArrowScene {
  public scene:       THREE_TYPES.Scene;
  public camera:      THREE_TYPES.PerspectiveCamera;
  public renderer:    THREE_TYPES.WebGLRenderer;
  public flowObjects: THREE_TYPES.ArrowHelper[] = [];

  constructor(canvas: HTMLCanvasElement, THREE: typeof THREE_TYPES) {
    this.scene    = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0a12);

    this.camera   = new THREE.PerspectiveCamera(
      75,
      canvas.clientWidth / canvas.clientHeight,
      0.1,
      1000,
    );
    this.camera.position.z = 8;

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);

    window.addEventListener('resize', () => {
      this.camera.aspect = canvas.clientWidth / canvas.clientHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    });
  }

  /** Remove all existing arrow objects and clear the tracking array. */
  clearField(): void {
    for (const obj of this.flowObjects) {
      this.scene.remove(obj);
      obj.dispose();
    }
    this.flowObjects = [];
  }

  /** Render the current scene — call this inside your animation loop. */
  render(): void {
    this.renderer.render(this.scene, this.camera);
  }

  dispose(): void {
    this.clearField();
    this.renderer.dispose();
  }
}
