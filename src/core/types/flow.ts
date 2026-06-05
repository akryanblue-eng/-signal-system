/** A single cell in the flow field grid. */
export interface FlowFieldCell {
  x: number;        // normalized position in control canvas
  y: number;        // normalized position in control canvas
  forceX: number;   // projected force along control axis
  forceY: number;   // projected force along vitality axis
  magnitude: number;
  damping: number;  // λ ∈ [0, 1] — 0 = hands-off zone, 1 = full steering
}

/** A recorded position sample in the trajectory trail. */
export interface TrajectoryPoint {
  x: number;
  y: number;
  timestamp: number;
  region: string;
}
