import type { PerformanceState } from '../PerformanceState';
import type { PerformanceAction, Dispatch } from './PerformanceAction';
import { EventBus } from './EventBus';
import { performanceReducer } from './performanceReducer';
import type { Style } from './Style';
import { STYLES, applyStyle } from './Style';
import { IntentMemoryStore, deriveStyle, smoothStyle } from './IntentMemory';
import { parseIntent, compileIntent } from './IntentCompiler';
import { gateActions, clampStyle } from './Constraints';
import { EnvironmentManager, mergeStyleWithBias, ENVIRONMENTS } from './Environment';
import type { StyleEnvironment } from './Environment';

// ─── System interface ──────────────────────────────────────────────────────────

/** A system reads state and queues actions — it never mutates state directly. */
export interface PerformanceSystem {
  tick(state: PerformanceState, dispatch: Dispatch): void;
}

// ─── Built-in systems ──────────────────────────────────────────────────────────

export class ChaosSystem implements PerformanceSystem {
  tick(state: PerformanceState, dispatch: Dispatch): void {
    if (state.tension > 0.65) {
      dispatch({ type: 'CHAOS_SPIKE', amount: state.tension * 0.08 });
    }
    if (state.stability < 0.35) {
      dispatch({ type: 'DRIFT_INJECTION', amount: 0.05 });
    }
  }
}

export class GovernorSystem implements PerformanceSystem {
  tick(state: PerformanceState, dispatch: Dispatch): void {
    if (state.chaos > 0.75) {
      dispatch({ type: 'TENSION_RELEASE' });
    }
    if (state.stability < 0.4) {
      dispatch({ type: 'GROOVE_LOCK' });
    }
  }
}

// ─── Options ───────────────────────────────────────────────────────────────────

export interface PerformanceRuntimeOptions {
  systems?:     PerformanceSystem[];
  memory?:      IntentMemoryStore;
  style?:       Style;
  environment?: EnvironmentManager;
}

// ─── Runtime ───────────────────────────────────────────────────────────────────

/**
 * Tick pipeline (single causal pass per frame):
 *
 *   handleInput(text)
 *     → compile + applyStyle(currentStyle) + gateActions
 *     → EventBus.dispatch
 *
 *   tickStep(dt):
 *     1. Advance frame/timestamp
 *     2. Systems read state and queue actions
 *     3. Flush queue → performanceReducer
 *     4. Record memory (auto-scored)
 *     5. deriveStyle(recent 100) → smoothStyle → mergeStyleWithBias → clampStyle
 *     6. environment.autoSelect (on cooldown)
 *
 * currentStyle already carries env bias — no extra threading needed in compilers.
 */
export class PerformanceRuntime {
  private state:        PerformanceState;
  private bus:          EventBus<PerformanceAction> = new EventBus();
  private systems:      PerformanceSystem[];
  private memory:       IntentMemoryStore;
  private currentStyle: Style;
  private environment:  EnvironmentManager;
  private running       = false;
  private lastTime      = 0;

  private pendingInput: {
    text:    string;
    actions: PerformanceAction[];
    before:  PerformanceState;
  } | null = null;

  constructor(
    initialState: PerformanceState,
    options: PerformanceRuntimeOptions = {},
  ) {
    this.state        = { ...initialState };
    this.systems      = options.systems     ?? [new ChaosSystem(), new GovernorSystem()];
    this.memory       = options.memory      ?? new IntentMemoryStore();
    this.environment  = options.environment ?? new EnvironmentManager(ENVIRONMENTS.cinematic);
    this.currentStyle = options.style       ?? { ...this.environment.get().style };
  }

  readonly dispatch: Dispatch = (action) => {
    this.bus.dispatch(action);
  };

  handleInput(text: string): void {
    const intent  = parseIntent(text);
    const raw     = compileIntent(intent);
    const styled  = applyStyle(raw, this.currentStyle);
    const gated   = gateActions(styled, this.state);
    for (const action of gated) this.dispatch(action);
    this.pendingInput = { text, actions: gated, before: this.state };
  }

  /** Switch environment manually (bypasses cooldown and auto-select). */
  switchEnvironment(env: StyleEnvironment): void {
    this.environment.switch(env);
  }

  tickStep(dt: number): PerformanceState {
    // 1. Advance time metadata
    this.state = {
      ...this.state,
      frameIndex: this.state.frameIndex + 1,
      timestamp:  this.state.timestamp  + dt * 1000,
    };

    // 2. Systems read + queue actions
    for (const sys of this.systems) {
      sys.tick(this.state, this.dispatch);
    }

    // 3. Flush → reducer
    for (const action of this.bus.flush()) {
      this.state = performanceReducer(this.state, action);
    }

    // 4. Record memory for pending input
    if (this.pendingInput) {
      this.memory.record(
        this.pendingInput.text,
        this.pendingInput.actions,
        this.pendingInput.before,
        this.state,
      );
      this.pendingInput = null;
    }

    // 5. Update style: learn → smooth → fold in env bias → clamp to env bounds
    const env          = this.environment.get();
    const derived      = deriveStyle(this.memory.recent(100));
    const smoothed     = smoothStyle(this.currentStyle, derived);
    const biased       = mergeStyleWithBias(smoothed, env.compilerBias);
    this.currentStyle  = clampStyle(biased, env.constraints);

    // 6. Auto-select environment from state + memory signals
    this.environment.autoSelect(this.state, this.memory.recent(20));

    return this.state;
  }

  getState():       PerformanceState    { return this.state; }
  getStyle():       Style               { return this.currentStyle; }
  getMemory():      IntentMemoryStore   { return this.memory; }
  getEnvironment(): EnvironmentManager  { return this.environment; }

  start(): void {
    if (this.running) return;
    this.running  = true;
    this.lastTime = performance.now();
    const loop = (t: number): void => {
      if (!this.running) return;
      const dt      = Math.min((t - this.lastTime) / 1000, 0.05);
      this.lastTime = t;
      this.tickStep(dt);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  stop(): void {
    this.running = false;
  }
}
