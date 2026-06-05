// Requires: three (npm install three @types/three)
import type * as THREE_TYPES from 'three';
import type { FlowArrowScene } from './FlowArrowScene';
import type { FieldCell } from './generateFlowField';

const ARROW_LENGTH  = 0.5;
const ARROW_HEAD    = 0.15; // headLength
const ARROW_WIDTH   = 0.06; // headWidth

/**
 * Map pressure [0, 1] to a hex color: blue → green → yellow → red.
 * Used to color arrows by their local field intensity.
 */
function pressureHex(pressure: number): number {
  const t = Math.min(Math.max(pressure, 0), 1);
  if (t < 0.33) {
    const s = t / 0.33;
    return rgb(Math.round(47  + (26  - 47)  * s),
               Math.round(102 + (184 - 102) * s),
               Math.round(217 + (82  - 217) * s));
  }
  if (t < 0.67) {
    const s = (t - 0.33) / 0.34;
    return rgb(Math.round(26  + (242 - 26)  * s),
               Math.round(184 + (217 - 184) * s),
               Math.round(82  + (26  - 82)  * s));
  }
  const s = (t - 0.67) / 0.33;
  return rgb(Math.round(242 + (230 - 242) * s),
             Math.round(217 + (31  - 217) * s),
             Math.round(26  + (31  - 26)  * s));
}

function rgb(r: number, g: number, b: number): number {
  return (r << 16) | (g << 8) | b;
}

/**
 * Replace all arrows in the scene with fresh ArrowHelpers derived from `field`.
 *
 * Arrow color encodes field cell intensity (magnitude of the direction vector
 * before normalization, which here equals 1 since generateFlowField pre-normalizes —
 * in practice, supply raw magnitude as `cell.pressure` for richer encoding).
 */
export function renderFlowField(
  scene: FlowArrowScene,
  field: FieldCell[],
  THREE: typeof THREE_TYPES,
  getPressure?: (cell: FieldCell) => number,
): void {
  scene.clearField();

  for (const cell of field) {
    const origin    = new THREE.Vector3(cell.pos[0], cell.pos[1], 0);
    const direction = new THREE.Vector3(cell.dir[0], cell.dir[1], 0).normalize();
    const pressure  = getPressure ? getPressure(cell) : 0.2;
    const color     = pressureHex(pressure);

    const arrow = new THREE.ArrowHelper(direction, origin, ARROW_LENGTH, color, ARROW_HEAD, ARROW_WIDTH);
    scene.scene.add(arrow);
    scene.flowObjects.push(arrow);
  }
}
