import type { CanvasPoint } from './latent';

/** A named attractor basin in the 2D control canvas. */
export interface Attractor {
  id: string;
  label: string;
  center: CanvasPoint;
  influenceRadius: number; // normalized canvas units
  strength: number;        // [0, 1] — how strongly it pulls
  type: 'pocket' | 'burner' | 'reset';
}

/** Potential contour rings around an attractor for rendering. */
export interface AttractorContour {
  attractorId: string;
  radius: number;
  opacity: number;
}
