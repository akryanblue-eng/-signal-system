import { useEffect, useRef, useState, useCallback } from 'react';
import { PerformanceRuntime } from '../../core/runtime/PerformanceRuntime';
import { EnvironmentManager, ENVIRONMENTS } from '../../core/runtime/Environment';
import { DEFAULT_PERFORMANCE_STATE } from '../../core/PerformanceState';
import type { PerformanceState } from '../../core/PerformanceState';
import type { Frame } from '../../replay/TraceBuffer';

export interface ControlValues {
  energy:    number;  // [0, 1]
  chaos:     number;  // [0, 1]
  stability: number;  // [0, 1]
  groove:    number;  // [0, 1]
}

export type RuntimeMode = 'live' | 'replaying' | 'forked';

export interface RuntimeDisplay {
  state:    PerformanceState;
  env:      string;
  trace:    Frame[];
  mode:     RuntimeMode;
  frame:    number;
}

const INITIAL_CTRL: ControlValues = { energy: 0.5, chaos: 0.2, stability: 0.5, groove: 0.5 };

// Map dominant slider → intent string; fired at most once per 500 ms.
function pickIntent(ctrl: ControlValues): string | null {
  const { energy, chaos, stability, groove } = ctrl;
  const max = Math.max(energy, chaos, stability, groove);
  if (max < 0.6) return null;
  if (chaos >= max)    return 'add chaos';
  if (energy >= max)   return 'add energy';
  if (stability >= max) return 'settle';
  return 'add groove';
}

function makeRuntime(initialState: PerformanceState): PerformanceRuntime {
  return new PerformanceRuntime(
    { ...initialState },
    { systems: [], environment: new EnvironmentManager(ENVIRONMENTS.cinematic, 20) },
  );
}

export function useRuntime() {
  const rtRef          = useRef<PerformanceRuntime>(makeRuntime(DEFAULT_PERFORMANCE_STATE));
  const ctrlRef        = useRef<ControlValues>(INITIAL_CTRL);
  const lastIntentTime = useRef(0);
  const rafRef         = useRef(0);
  const frameCount     = useRef(0);
  const replayFrames   = useRef<Frame[]>([]);
  const replayIdx      = useRef(0);
  const modeRef        = useRef<RuntimeMode>('live');

  const [display, setDisplay] = useState<RuntimeDisplay>({
    state: { ...DEFAULT_PERFORMANCE_STATE },
    env:   'cinematic',
    trace: [],
    mode:  'live',
    frame: 0,
  });

  // ── Live loop ──────────────────────────────────────────────────────────────

  useEffect(() => {
    let lastTime = performance.now();

    const tick = (t: number) => {
      const dt = Math.min((t - lastTime) / 1000, 0.05);
      lastTime = t;

      const mode = modeRef.current;

      if (mode === 'live' || mode === 'forked') {
        const rt   = rtRef.current;
        const ctrl = ctrlRef.current;
        const now  = performance.now();

        if (now - lastIntentTime.current > 500) {
          const intent = pickIntent(ctrl);
          if (intent) {
            rt.handleInput(intent);
            lastIntentTime.current = now;
          }
        }

        rt.tickStep(dt);
        frameCount.current++;

        if (frameCount.current % 2 === 0) {
          setDisplay({
            state: { ...rt.getState() },
            env:   rt.getEnvironment().get().name,
            trace: rt.getTrace().recent(200),
            mode,
            frame: rt.getState().frameIndex,
          });
        }
      } else if (mode === 'replaying') {
        const frames = replayFrames.current;
        const idx    = replayIdx.current;
        if (idx >= frames.length) {
          modeRef.current = 'live';
        } else {
          const f = frames[idx]!;
          replayIdx.current++;
          setDisplay({
            state: f.state,
            env:   f.env,
            trace: frames.slice(0, idx + 1),
            mode:  'replaying',
            frame: f.t,
          });
        }
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  // ── Controls ───────────────────────────────────────────────────────────────

  const setControl = useCallback((values: ControlValues) => {
    ctrlRef.current = values;
  }, []);

  const replay = useCallback(() => {
    replayFrames.current = rtRef.current.getTrace().getAll();
    replayIdx.current    = 0;
    modeRef.current      = 'replaying';
  }, []);

  const stopReplay = useCallback(() => {
    modeRef.current = 'live';
  }, []);

  /** Fork: restart the runtime from the state captured at frameIndex in the trace. */
  const fork = useCallback((traceFrameIndex: number) => {
    const frames = rtRef.current.getTrace().getAll();
    const target = frames[traceFrameIndex];
    if (!target) return;

    const envKey = Object.keys(ENVIRONMENTS).includes(target.env)
      ? (target.env as keyof typeof ENVIRONMENTS)
      : 'cinematic';

    rtRef.current = new PerformanceRuntime(
      { ...target.state },
      { systems: [], environment: new EnvironmentManager(ENVIRONMENTS[envKey], 20) },
    );
    modeRef.current = 'forked';
  }, []);

  const reset = useCallback(() => {
    rtRef.current   = makeRuntime(DEFAULT_PERFORMANCE_STATE);
    modeRef.current = 'live';
    frameCount.current = 0;
  }, []);

  const saveSession = useCallback(() => {
    const frames = rtRef.current.getTrace().getAll();
    const blob   = new Blob([JSON.stringify(frames, null, 2)], { type: 'application/json' });
    const url    = URL.createObjectURL(blob);
    const a      = Object.assign(document.createElement('a'), { href: url, download: `session-${Date.now()}.json` });
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  return { display, setControl, replay, stopReplay, fork, reset, saveSession };
}
