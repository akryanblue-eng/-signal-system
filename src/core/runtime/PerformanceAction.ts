export type PerformanceAction =
  | { type: 'CHAOS_SPIKE';       amount: number }
  | { type: 'TENSION_BUILD';     amount: number }
  | { type: 'TENSION_RELEASE' }
  | { type: 'GROOVE_LOCK' }
  | { type: 'DRIFT_INJECTION';   amount: number }
  | { type: 'ENERGY_PULSE';      amount: number }
  | { type: 'STABILITY_RESTORE'; amount: number };

export type Dispatch = (action: PerformanceAction) => void;
