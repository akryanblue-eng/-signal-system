// ─── Core types ───────────────────────────────────────────────────────────────
export type {
  LatentState, CanvasPoint, CanvasPixel, CanvasRegion, SteeringForce,
} from './core/types/latent';
export type { Attractor, AttractorContour }     from './core/types/attractor';
export type { FlowFieldCell, TrajectoryPoint }  from './core/types/flow';
export type { Artist, VenueSession }            from './core/types/venue';

// ─── Coordinate mapping ───────────────────────────────────────────────────────
export { PROJECTION_AXES, RAW_PROJECTION_BOUNDS, DEFAULT_BOUNDS } from './core/mapping/ProjectionAxes';
export { normalizeDimension, toCanvasPixel, fromCanvasPixel, pressureToHsl } from './core/mapping/normalization';
export { CoordinateMapper }  from './core/mapping/CoordinateMapper';
export type { NormalizationBounds } from './core/mapping/CoordinateMapper';

// ─── Manifold ─────────────────────────────────────────────────────────────────
export { ClusterEngine }     from './core/manifold/ClusterEngine';
export type { SpeciesNode }  from './core/manifold/ClusterEngine';
export type { ManifoldSnapshot } from './core/manifold/ManifoldState';
export { ManifoldRuntime, manifoldGovernor, step as manifoldStep } from './core/manifold/ManifoldRuntime';
export type { ManifoldState, ManifoldPolicy, ManifoldForce } from './core/manifold/ManifoldRuntime';

// ─── Steering ─────────────────────────────────────────────────────────────────
export { SteeringField }     from './core/steering/SteeringField';
export type { SteeringVector } from './core/steering/SteeringField';
export { DampingEngine }     from './core/steering/DampingEngine';

// ─── Kernel ───────────────────────────────────────────────────────────────────
export { PerformanceKernel } from './core/kernel/PerformanceKernel';
export type { KernelOutput, PerformanceMode } from './core/kernel/PerformanceKernel';

// ─── Engine layer ─────────────────────────────────────────────────────────────
export { FlowFieldEngine }        from './engine/FlowFieldEngine';
export type { Vector2, FlowCell, AttractorNode } from './engine/FlowFieldEngine';
export { MidiAttractorController } from './engine/MidiAttractorController';
export type { LiveAttractor, AttractorType } from './engine/MidiAttractorController';
export { SteeringFieldEngine }    from './engine/SteeringFieldEngine';
export type { FieldState }        from './engine/SteeringFieldEngine';
export { SignalToFlowMapper }     from './engine/SignalToFlowMapper';
export { FlowKernelBridge }       from './engine/Bridge';
export type { SceneUniforms }     from './engine/Bridge';
export { BidirectionalBrainLoop } from './engine/BidirectionalBrainLoop';
export type { PerformerFeedback, BrainLoopOutput } from './engine/BidirectionalBrainLoop';
export { SharedFieldEngine }      from './engine/SharedFieldEngine';
export type { PerformerState, PhaseCoupling, SharedFieldState } from './engine/SharedFieldEngine';

// ─── Math utilities ───────────────────────────────────────────────────────────
export { vec2Add, vec2Scale, vec2Magnitude, vec2Normalize, vec2Dot } from './math/vector';
export type { Vec2 } from './math/vector';

// ─── Visualization grid sampler (no browser deps) ────────────────────────────
export { FlowFieldEngine as GridSampler }   from './visualization/FlowFieldEngine';
export type { ForceFunction, DampingFunction } from './visualization/FlowFieldEngine';
export { generateFlowField }               from './visualization/generateFlowField';
export type { FieldCell }                  from './visualization/generateFlowField';

// ─── Runtime pipeline (EventBus → reducer → PerformanceRuntime) ─────────────
export { EventBus }                        from './core/runtime/EventBus';
export { performanceReducer }              from './core/runtime/performanceReducer';
export { PerformanceRuntime, ChaosSystem, GovernorSystem } from './core/runtime/PerformanceRuntime';
export type { PerformanceSystem }          from './core/runtime/PerformanceRuntime';
export type { PerformanceAction, Dispatch } from './core/runtime/PerformanceAction';
export { parseIntent, compileIntent, handleIntent } from './core/runtime/IntentCompiler';
export type { ParsedIntent, IntentTarget } from './core/runtime/IntentCompiler';

// ─── Observability layer ─────────────────────────────────────────────────────
export { SnapshotRecorder }                from './core/manifold/RuntimeSnapshot';
export type { RuntimeSnapshot }            from './core/manifold/RuntimeSnapshot';
export { TrajectoryBuffer }                from './core/manifold/TrajectoryBuffer';
export type { TrailPoint }                 from './core/manifold/TrajectoryBuffer';
export { blendSteeringState, forceAlignment } from './core/manifold/SteeringState';
export type { SteeringState }              from './core/manifold/SteeringState';
export { fromManifoldState, assessPerformanceState } from './core/PerformanceState';
export type { PerformanceState }           from './core/PerformanceState';

// ─── Chaos engine ─────────────────────────────────────────────────────────────
export { ChaosEngine, chaosForce }         from './engine/ChaosEngine';
export type { ChaosEvent, ChaosEventType, ActiveChaosEvent } from './engine/ChaosEngine';

// ─── Engine — MIDI injection + bidirectional brain ───────────────────────────
export { midiToForce, FlowFieldInjector }  from './engine/MidiForceInjector';
export type { MidiForceEvent, MidiForceType } from './engine/MidiForceInjector';
export { computeFieldFeedback, applyFeedbackToInjector } from './engine/FieldFeedback';
export type { FieldFeedbackSignal }        from './engine/FieldFeedback';
export { BidirectionalBrainRuntime }       from './engine/BidirectionalBrainRuntime';
export type { BrainRuntimeOutput }         from './engine/BidirectionalBrainRuntime';
export { MidiBrainBridge }                 from './engine/MidiBrainBridge';

// ─── Visualization — browser/Three.js required ───────────────────────────────
// FlowFieldScene, FlowFieldMaterial, and RuntimeInspector are NOT re-exported
// here because they require browser DOM / Three.js. Import them directly:
//   import { FlowFieldScene }    from '-signal-system/src/visualization/FlowFieldScene';
//   import { FlowFieldMaterial } from '-signal-system/src/visualization/FlowFieldMaterial';
//   import { RuntimeInspector }  from '-signal-system/src/ui/RuntimeInspector';
